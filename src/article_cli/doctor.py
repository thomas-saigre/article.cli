"""
Read-only project diagnostics for article-cli.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .git_hooks import (
    MANAGED_HOOK_START,
    render_gitinfo2_metadata,
)


@dataclass
class DoctorCheck:
    """Single diagnostic check."""

    category: str
    name: str
    status: str
    message: str
    next_command: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        data: Dict[str, Any] = {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }
        if self.next_command:
            data["next_command"] = self.next_command
        if self.details:
            data["details"] = self.details
        return data


@dataclass
class DoctorReport:
    """Complete doctor report."""

    context: Dict[str, Any]
    checks: List[DoctorCheck]

    @property
    def error_count(self) -> int:
        """Number of blocking errors."""
        return sum(1 for check in self.checks if check.status == "error")

    @property
    def warning_count(self) -> int:
        """Number of warnings."""
        return sum(1 for check in self.checks if check.status == "warning")

    @property
    def ok(self) -> bool:
        """Whether no blocking errors were found."""
        return self.error_count == 0

    @property
    def next_commands(self) -> List[str]:
        """Deduplicated list of suggested next commands."""
        commands = []
        for check in self.checks:
            if check.next_command and check.next_command not in commands:
                commands.append(check.next_command)
        return commands

    def to_dict(self) -> Dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        return {
            "ok": self.ok,
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
            "context": self.context,
            "checks": [check.to_dict() for check in self.checks],
            "next_commands": self.next_commands,
        }


class DoctorService:
    """Run read-only diagnostics for an article repository."""

    def __init__(self, config: Config, cwd: Optional[Path] = None):
        self.config = config
        self.cwd = (cwd or Path.cwd()).resolve()
        self.context: Dict[str, Any] = {"cwd": str(self.cwd)}
        self.checks: List[DoctorCheck] = []
        self.repo_root: Optional[Path] = None
        self.hooks_path: Optional[Path] = None
        self.main_document: Optional[Path] = None
        self.engine: str = "latexmk"
        self.output_dir: Optional[Path] = None
        self.dirty_tracked_files: List[str] = []

    def run(
        self,
        document: Optional[str] = None,
        engine: Optional[str] = None,
        output_dir: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> DoctorReport:
        """Run all diagnostics."""
        self._check_git()
        self._resolve_project_context(document, engine, output_dir)
        self._check_git_metadata(tag)
        self._check_build_readiness()
        self._check_bibliography()
        self._check_workflow()
        self._check_release_readiness(tag)
        return DoctorReport(context=self.context, checks=self.checks)

    def _check_git(self) -> None:
        """Resolve and check git repository state."""
        result = self._git(["rev-parse", "--show-toplevel"], cwd=self.cwd)
        if result is None or result.returncode != 0:
            self._add(
                "git",
                "repository",
                "error",
                "Current directory is not inside a Git repository.",
                next_command="git init",
            )
            self.context["git_root"] = None
            return

        self.repo_root = Path(result.stdout.strip()).resolve()
        self.context["repository_root"] = str(self.repo_root)
        self.context["git_root"] = str(self.repo_root)
        self._add("git", "repository", "ok", "Git repository found.")

        hooks_result = self._git(["rev-parse", "--git-path", "hooks"])
        if hooks_result and hooks_result.returncode == 0:
            self.hooks_path = self._resolve_git_path(hooks_result.stdout.strip())
            self.context["git_hooks_path"] = str(self.hooks_path)
            self._add("git", "hooks-path", "ok", "Git hooks path resolved.")
        else:
            self._add(
                "git",
                "hooks-path",
                "error",
                "Could not resolve Git hooks path.",
                next_command="article-cli setup",
            )

        branch = self._git_output(["symbolic-ref", "--quiet", "--short", "HEAD"])
        commit = self._git_output(["rev-parse", "--short", "HEAD"])
        describe = self._git_output(
            ["describe", "--tags", "--long", "--always", "--dirty=-*"]
        )
        self.context["current_branch"] = branch or "DETACHED"
        self.context["current_commit"] = commit
        self.context["git_describe"] = describe

        status = self._git(
            [
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--",
                ".",
                ":(exclude)gitHeadLocal.gin",
            ]
        )
        if status is None or status.returncode != 0:
            self._add("git", "working-tree", "warning", "Could not inspect git status.")
            return

        self.dirty_tracked_files = [
            line.strip() for line in status.stdout.splitlines() if line.strip()
        ]
        self.context["dirty_tracked_files"] = self.dirty_tracked_files
        if self.dirty_tracked_files:
            self._add(
                "git",
                "working-tree",
                "warning",
                "Tracked files are modified, ignoring gitHeadLocal.gin.",
                details={"files": self.dirty_tracked_files},
            )
        else:
            self._add(
                "git",
                "working-tree",
                "ok",
                "No dirty tracked files other than gitHeadLocal.gin.",
            )

    def _resolve_project_context(
        self,
        document: Optional[str],
        engine: Optional[str],
        output_dir: Optional[str],
    ) -> None:
        """Resolve document, engine, config, project type, and output path."""
        project_root = self.repo_root or self.cwd
        config_file = self.config.loaded_config_file
        project_config = self.config.get_project_config()
        latex_config = self.config.get_latex_config()
        documents_config = self.config.get_documents_config()
        workflow_config = self.config.get_workflow_config()
        typst_config = self.config.get_typst_config()

        self.context["config_file"] = str(config_file) if config_file else None
        self.context["project_type"] = project_config.get("project_type", "article")

        document_name = document or documents_config.get("main") or ""
        if not document_name:
            document_name = self._auto_detect_document(project_root) or ""

        if document_name:
            doc_path = Path(document_name)
            if not doc_path.is_absolute():
                doc_path = project_root / doc_path
            self.main_document = doc_path.resolve()
            self.context["main_document"] = str(self.main_document)
        else:
            self.context["main_document"] = None

        explicit_engine = engine is not None
        self.engine = engine or str(latex_config.get("engine") or "latexmk")
        if (
            self.main_document
            and self.main_document.suffix == ".typ"
            and not explicit_engine
        ):
            self.engine = "typst"
        self.context["engine"] = self.engine

        resolved_output = output_dir
        if not resolved_output:
            if self.engine == "typst":
                resolved_output = typst_config.get("build_dir") or workflow_config.get(
                    "output_dir"
                )
            else:
                resolved_output = workflow_config.get("output_dir") or latex_config.get(
                    "build_dir"
                )

        if resolved_output and resolved_output != ".":
            output_path = Path(str(resolved_output))
            if not output_path.is_absolute():
                output_path = project_root / output_path
            self.output_dir = output_path.resolve()
            self.context["output_directory"] = str(self.output_dir)
        else:
            self.output_dir = None
            self.context["output_directory"] = "."

    def _check_git_metadata(self, tag: Optional[str]) -> None:
        """Check hooks and gitinfo2 metadata without modifying files."""
        if self.repo_root is None:
            return

        source_hook = self.repo_root / "hooks" / "post-commit"
        if source_hook.exists():
            self._add("git", "hook-source", "ok", "Repository hook source exists.")
        else:
            self._add(
                "git",
                "hook-source",
                "warning",
                "Repository hook source hooks/post-commit is missing.",
                next_command="article-cli setup",
            )

        if self.hooks_path is None:
            return

        missing_hooks = []
        for hook_name in ["post-commit", "post-checkout", "post-merge"]:
            hook_path = self.hooks_path / hook_name
            if not hook_path.exists():
                missing_hooks.append(hook_name)
                continue
            if not os.access(hook_path, os.X_OK):
                self._add(
                    "git",
                    f"installed-hook:{hook_name}",
                    "warning",
                    f"Installed hook {hook_name} is not executable.",
                    next_command="article-cli setup",
                )
                continue
            content = hook_path.read_text(errors="replace")
            if MANAGED_HOOK_START not in content and "gitHeadInfo.gin" not in content:
                self._add(
                    "git",
                    f"installed-hook:{hook_name}",
                    "warning",
                    f"Installed hook {hook_name} does not appear to refresh gitinfo2.",
                    next_command="article-cli setup",
                )
            else:
                self._add(
                    "git",
                    f"installed-hook:{hook_name}",
                    "ok",
                    f"Installed hook {hook_name} is executable.",
                )

        if missing_hooks:
            self._add(
                "git",
                "installed-hooks",
                "warning",
                "One or more gitinfo2 hooks are missing.",
                next_command="article-cli setup",
                details={"missing": missing_hooks},
            )

        metadata_path = self.repo_root / "gitHeadLocal.gin"
        if not metadata_path.exists():
            self._add(
                "git",
                "gitHeadLocal",
                "warning",
                "gitHeadLocal.gin is missing.",
                next_command="article-cli compile",
            )
            return

        expected_metadata = render_gitinfo2_metadata(self.repo_root)
        if expected_metadata is None:
            self._add(
                "git",
                "gitHeadLocal",
                "warning",
                "Could not render current gitinfo2 metadata.",
                next_command="article-cli compile",
            )
            return

        current_metadata = metadata_path.read_text(errors="replace").strip()
        if current_metadata == expected_metadata.strip():
            self._add(
                "git",
                "gitHeadLocal",
                "ok",
                "gitHeadLocal.gin matches the current git state.",
            )
        else:
            status = "error" if tag else "warning"
            self._add(
                "git",
                "gitHeadLocal",
                status,
                "gitHeadLocal.gin does not match the current git state.",
                next_command="article-cli compile",
            )

    def _check_build_readiness(self) -> None:
        """Check document and toolchain readiness."""
        if self.main_document is None:
            self._add(
                "build",
                "main-document",
                "error",
                "No main .tex or .typ document was configured or detected.",
                next_command="article-cli init --title TITLE --authors AUTHOR",
            )
            return

        if self.main_document.exists():
            self._add("build", "main-document", "ok", "Main document exists.")
        else:
            self._add(
                "build",
                "main-document",
                "error",
                f"Main document does not exist: {self.main_document}",
            )
            return

        if self.main_document.suffix == ".typ" and self.engine != "typst":
            self._add(
                "build",
                "engine",
                "error",
                "A Typst document requires the typst engine.",
            )
        elif self.main_document.suffix == ".tex" and self.engine == "typst":
            self._add(
                "build",
                "engine",
                "error",
                "A LaTeX document cannot be compiled with the typst engine.",
            )
        else:
            self._add(
                "build",
                "engine",
                "ok",
                f"Selected engine: {self.engine}.",
            )

        required_tools = self._required_tools()
        for tool in required_tools:
            self._check_tool(tool, required=True)

        if self.engine != "typst":
            for tool in ["bibtex", "biber"]:
                self._check_tool(tool, required=False)

        self._check_output_directory()

    def _check_bibliography(self) -> None:
        """Check Zotero and BibTeX configuration."""
        zotero_config = self.config.get_zotero_config()
        output_file = zotero_config.get("output_file") or "references.bib"
        project_root = self.repo_root or self.cwd
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = project_root / output_path

        self.context["bibliography_output"] = str(output_path)
        if output_path.exists():
            self._add("bibliography", "output-file", "ok", "Bibliography file exists.")
        else:
            self._add(
                "bibliography",
                "output-file",
                "warning",
                f"Bibliography file does not exist: {output_file}.",
                next_command="article-cli update-bibtex",
            )

        if zotero_config.get("api_key"):
            self._add("bibliography", "zotero-api-key", "ok", "Zotero API key is set.")
        else:
            self._add(
                "bibliography",
                "zotero-api-key",
                "warning",
                "Zotero API key is not set.",
            )

        if zotero_config.get("user_id") or zotero_config.get("group_id"):
            self._add(
                "bibliography",
                "zotero-library",
                "ok",
                "Zotero user or group id is configured.",
            )
        else:
            self._add(
                "bibliography",
                "zotero-library",
                "warning",
                "Neither Zotero user id nor group id is configured.",
            )

        collection_id = self.config.get("zotero", "collection_id")
        self.context["zotero_collection_id"] = collection_id

        local_files = [
            path.name
            for path in [
                project_root / "local_references.bib",
                project_root / "references.local.bib",
            ]
            if path.exists()
        ]
        if local_files:
            self._add(
                "bibliography",
                "local-references",
                "ok",
                "Local bibliography preservation file detected.",
                details={"files": local_files},
            )
        else:
            self._add(
                "bibliography",
                "local-references",
                "info",
                "No local bibliography preservation file detected.",
            )

    def _check_workflow(self) -> None:
        """Check generated GitHub Actions workflow readiness."""
        project_root = self.repo_root or self.cwd
        workflow_path = project_root / ".github" / "workflows" / "latex.yml"
        self.context["workflow"] = str(workflow_path)

        if not workflow_path.exists():
            self._add(
                "workflow",
                "latex-yml",
                "warning",
                ".github/workflows/latex.yml is missing.",
                next_command="article-cli init --title TITLE --authors AUTHOR",
            )
            return

        self._add("workflow", "latex-yml", "ok", "GitHub Actions workflow exists.")
        raw_workflow = workflow_path.read_text(errors="replace")

        try:
            import yaml  # type: ignore[import-untyped]

            yaml.safe_load(raw_workflow)
            self._add("workflow", "yaml-parse", "ok", "Workflow YAML parses.")
        except Exception as e:
            self._add(
                "workflow",
                "yaml-parse",
                "error",
                f"Workflow YAML does not parse: {e}",
            )

        if self.main_document and self.main_document.name in raw_workflow:
            self._add(
                "workflow",
                "main-document",
                "ok",
                "Workflow references the main document name.",
            )
        elif self.main_document:
            self._add(
                "workflow",
                "main-document",
                "warning",
                "Workflow does not reference the resolved main document name.",
            )

        if "setup-uv" in raw_workflow or re.search(r"\buv\b", raw_workflow):
            self._add("workflow", "package-manager", "ok", "Workflow uses uv.")
        else:
            self._add(
                "workflow",
                "package-manager",
                "warning",
                "Workflow does not appear to use uv.",
            )

        release_automation = bool(self.config.get("release", "automation", False))
        has_release_trigger = (
            "tags:" in raw_workflow or "action-gh-release" in raw_workflow
        )
        if release_automation and not has_release_trigger:
            self._add(
                "workflow",
                "release-trigger",
                "warning",
                "Release automation is enabled but no release trigger was detected.",
            )
        elif has_release_trigger:
            self._add(
                "workflow",
                "release-trigger",
                "ok",
                "Workflow contains release trigger or release action.",
            )
        else:
            self._add(
                "workflow",
                "release-trigger",
                "info",
                "Release automation is not enabled in project config.",
            )

    def _check_release_readiness(self, tag: Optional[str]) -> None:
        """Check lightweight release readiness signals."""
        if self.repo_root is None:
            return

        if tag:
            tag_result = self._git(["rev-parse", "--verify", f"refs/tags/{tag}"])
            if tag_result and tag_result.returncode == 0:
                self._add(
                    "release",
                    "tag",
                    "error",
                    f"Tag already exists: {tag}.",
                )
            else:
                self._add("release", "tag", "ok", f"Tag is available: {tag}.")

            if self.dirty_tracked_files:
                self._add(
                    "release",
                    "working-tree",
                    "error",
                    "Tracked files must be clean before release.",
                    details={"files": self.dirty_tracked_files},
                )

        pdf_path = self._expected_pdf_path()
        if pdf_path is None:
            return
        self.context["expected_pdf"] = str(pdf_path)

        if pdf_path.exists():
            self._add("release", "pdf", "ok", "Expected PDF exists.")
            self._check_pdf_version(pdf_path, tag)
        else:
            self._add(
                "release",
                "pdf",
                "error" if tag else "warning",
                f"Expected PDF is missing: {pdf_path.name}.",
                next_command="article-cli compile",
            )

    def _check_pdf_version(self, pdf_path: Path, tag: Optional[str]) -> None:
        """Try to inspect PDF text for a requested tag."""
        if not tag:
            return
        if shutil.which("pdftotext") is None:
            self._add(
                "release",
                "pdf-version",
                "warning",
                "pdftotext is unavailable; PDF version string was not checked.",
            )
            return

        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            cwd=self.repo_root or self.cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self._add(
                "release",
                "pdf-version",
                "warning",
                "Could not extract text from PDF for version checking.",
            )
            return

        if tag in result.stdout:
            self._add(
                "release",
                "pdf-version",
                "ok",
                f"PDF text contains requested tag {tag}.",
            )
        else:
            self._add(
                "release",
                "pdf-version",
                "warning",
                f"PDF text does not contain requested tag {tag}.",
                next_command="article-cli compile",
            )

    def _required_tools(self) -> List[str]:
        """Return required tools for the selected engine."""
        if self.engine == "typst":
            return ["typst"]
        if self.engine in {"pdflatex", "xelatex", "lualatex"}:
            return [self.engine]
        return ["latexmk"]

    def _check_tool(self, tool: str, required: bool) -> None:
        """Check whether a command-line tool exists."""
        if shutil.which(tool):
            self._add("build", f"tool:{tool}", "ok", f"Tool available: {tool}.")
            return

        self._add(
            "build",
            f"tool:{tool}",
            "error" if required else "warning",
            f"Tool not found: {tool}.",
        )

    def _check_output_directory(self) -> None:
        """Check whether output directory exists or can be created."""
        if self.output_dir is None:
            self._add(
                "build",
                "output-directory",
                "ok",
                "Output directory is the project root.",
            )
            return

        if self.output_dir.exists() and self.output_dir.is_dir():
            self._add("build", "output-directory", "ok", "Output directory exists.")
            return

        if self.output_dir.exists() and not self.output_dir.is_dir():
            self._add(
                "build",
                "output-directory",
                "error",
                "Configured output path exists but is not a directory.",
            )
            return

        parent = self.output_dir.parent
        if parent.exists() and os.access(parent, os.W_OK):
            self._add(
                "build",
                "output-directory",
                "ok",
                "Output directory does not exist yet but can be created.",
            )
        else:
            self._add(
                "build",
                "output-directory",
                "error",
                "Output directory parent is missing or not writable.",
            )

    def _expected_pdf_path(self) -> Optional[Path]:
        """Return expected PDF path for the resolved main document."""
        if self.main_document is None:
            return None
        pdf_name = self.main_document.with_suffix(".pdf").name
        if self.output_dir is not None:
            return self.output_dir / pdf_name
        return self.main_document.with_suffix(".pdf")

    def _auto_detect_document(self, project_root: Path) -> Optional[str]:
        """Auto-detect a main .tex or .typ file."""
        for patterns in [
            ["main.tex", "article.tex", f"{project_root.name}.tex"],
            ["main.typ"],
        ]:
            for pattern in patterns:
                if (project_root / pattern).exists():
                    return pattern

        tex_files = sorted(project_root.glob("*.tex"))
        if tex_files:
            return tex_files[0].name
        typ_files = sorted(project_root.glob("*.typ"))
        if typ_files:
            return typ_files[0].name
        return None

    def _git(
        self, args: List[str], cwd: Optional[Path] = None
    ) -> Optional[subprocess.CompletedProcess[str]]:
        """Run git and return the completed process."""
        try:
            return subprocess.run(
                ["git", *args],
                cwd=cwd or self.repo_root or self.cwd,
                capture_output=True,
                text=True,
                check=False,
            )
        except (FileNotFoundError, OSError):
            return None

    def _git_output(self, args: List[str]) -> Optional[str]:
        """Run git and return stripped stdout on success."""
        result = self._git(args)
        if result is None or result.returncode != 0:
            return None
        output = result.stdout.strip()
        return output or None

    def _resolve_git_path(self, path_text: str) -> Path:
        """Resolve a git metadata path relative to the repository root."""
        path = Path(path_text)
        if not path.is_absolute():
            path = (self.repo_root or self.cwd) / path
        return path.resolve()

    def _add(
        self,
        category: str,
        name: str,
        status: str,
        message: str,
        next_command: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a diagnostic check."""
        self.checks.append(
            DoctorCheck(
                category=category,
                name=name,
                status=status,
                message=message,
                next_command=next_command,
                details=details or {},
            )
        )


def print_doctor_report(report: DoctorReport) -> None:
    """Print a human-readable doctor report."""
    print("article-cli doctor")
    print("\nContext:")
    for key in sorted(report.context):
        value = report.context[key]
        if value is not None:
            print(f"  {key}: {value}")

    print("\nChecks:")
    for check in report.checks:
        label = _status_label(check.status)
        print(f"  {label} {check.category}.{check.name}: {check.message}")
        if check.next_command:
            print(f"      next: {check.next_command}")

    print(
        f"\nSummary: {report.error_count} error(s), "
        f"{report.warning_count} warning(s)"
    )
    if report.next_commands:
        print("\nSuggested next commands:")
        for command in report.next_commands:
            print(f"  - {command}")


def report_to_json(report: DoctorReport) -> str:
    """Serialize a doctor report as stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def _status_label(status: str) -> str:
    """Return a short ASCII label for a check status."""
    labels = {
        "ok": "[OK]",
        "warning": "[WARN]",
        "error": "[ERROR]",
        "info": "[INFO]",
    }
    return labels.get(status, "[INFO]")
