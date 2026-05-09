"""
Transactional release service.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Sequence, Type

from ..command_runner import DEFAULT_RUNNER, CommandRunner
from ..config import Config
from ..git_hooks import gitinfo2_metadata_summary, refresh_gitinfo2_metadata
from ..git_manager import GitManager
from ..project_context import ProjectContext
from ..reporting import print_error, print_info, print_success, print_warning
from .bibliography import BibliographyService, BibliographyUpdateOptions
from .compiler import CompileOptions, CompilerService


@dataclass(frozen=True)
class ReleaseOptions:
    """User-facing release workflow options."""

    tag: str
    auto_push: bool = False
    dry_run: bool = False
    force: bool = False
    commit: bool = False
    compile_pdf: Optional[bool] = None
    check_pdf: Optional[bool] = None
    bibliography: Optional[str] = None
    github_release: Optional[bool] = None
    checksum: Optional[bool] = None
    allow_dirty: Optional[bool] = None
    tag_policy: Optional[str] = None
    document: Optional[str] = None
    engine: Optional[str] = None
    output_dir: Optional[str] = None
    shell_escape: Optional[bool] = None


@dataclass(frozen=True)
class ResolvedReleaseOptions:
    """Release options after config defaults are applied."""

    tag: str
    auto_push: bool
    dry_run: bool
    force: bool
    commit: bool
    compile_pdf: bool
    check_pdf: bool
    bibliography: str
    github_release: bool
    checksum: bool
    allow_dirty: bool
    tag_policy: str
    document: Optional[str]
    engine: Optional[str]
    output_dir: Optional[str]
    shell_escape: Optional[bool]


class ReleaseService:
    """Service boundary for tag-based paper releases."""

    def __init__(
        self,
        config: Optional[Config] = None,
        repo_root: Optional[Path] = None,
        manager_cls: Type[GitManager] = GitManager,
        compiler_service_cls: Type[CompilerService] = CompilerService,
        bibliography_service_cls: Type[BibliographyService] = BibliographyService,
        runner: CommandRunner = DEFAULT_RUNNER,
    ) -> None:
        self.config = config or Config(quiet=True)
        self.manager = (
            manager_cls(repo_root) if repo_root is not None else manager_cls()
        )
        self.compiler_service_cls = compiler_service_cls
        self.bibliography_service_cls = bibliography_service_cls
        self.runner = runner

    def create(
        self,
        version: str,
        auto_push: bool = False,
        dry_run: bool = False,
        **kwargs: object,
    ) -> bool:
        """Backward-compatible release entrypoint."""
        return self.release(
            ReleaseOptions(
                tag=version,
                auto_push=auto_push,
                dry_run=dry_run,
                force=bool(kwargs.get("force", False)),
                commit=bool(kwargs.get("commit", False)),
                compile_pdf=_optional_bool(kwargs.get("compile_pdf")),
                check_pdf=_optional_bool(kwargs.get("check_pdf")),
                bibliography=_optional_str(kwargs.get("bibliography")),
                github_release=_optional_bool(kwargs.get("github_release")),
                checksum=_optional_bool(kwargs.get("checksum")),
                allow_dirty=_optional_bool(kwargs.get("allow_dirty")),
                tag_policy=_optional_str(kwargs.get("tag_policy")),
                document=_optional_str(kwargs.get("document")),
                engine=_optional_str(kwargs.get("engine")),
                output_dir=_optional_str(kwargs.get("output_dir")),
                shell_escape=_optional_bool(kwargs.get("shell_escape")),
            )
        )

    def release(self, options: ReleaseOptions) -> bool:
        """Create a checked paper release."""
        resolved = self._resolve_options(options)
        if not self._validate_tag(resolved.tag, resolved.tag_policy):
            return False
        if not self._preflight(resolved):
            return False

        context = ProjectContext.resolve(
            self.config,
            cwd=self.manager.repo_root,
            document=resolved.document,
            engine=resolved.engine,
            output_dir=resolved.output_dir,
            shell_escape=resolved.shell_escape,
        )
        pdf_path = _absolute_pdf_path(context)

        if resolved.dry_run:
            self._print_dry_run(resolved, pdf_path)
            return True

        if resolved.bibliography in {"check", "update"}:
            if not self._run_bibliography(resolved.bibliography):
                return False

        if not self._refresh_metadata():
            return False

        if resolved.commit and not self._commit_metadata(resolved.tag):
            return False

        if resolved.compile_pdf and not self._compile(resolved):
            return False

        if resolved.compile_pdf and (pdf_path is None or not pdf_path.exists()):
            print_error("Release PDF was not produced before tagging.")
            return False

        created_tag = False
        try:
            self.manager.create_tag(resolved.tag, force=resolved.force)
            created_tag = True
            print_success(f"Created release tag: {resolved.tag}")

            if not self._refresh_metadata():
                self._print_rollback(resolved.tag)
                return False

            if resolved.compile_pdf and not self._compile(resolved):
                self._print_rollback(resolved.tag)
                return False

            if resolved.check_pdf and not self._check_pdf(pdf_path, resolved.tag):
                self._print_rollback(resolved.tag)
                return False

            checksum_path = None
            if resolved.checksum and pdf_path is not None:
                checksum_path = write_sha256(pdf_path)
                print_success(f"Wrote checksum: {checksum_path}")

            if resolved.github_release:
                assets = [
                    path for path in [pdf_path, checksum_path] if path is not None
                ]
                if not self._create_github_release(resolved.tag, assets):
                    self._print_rollback(resolved.tag)
                    return False

            if resolved.auto_push:
                self.manager.push_tag(resolved.tag)
                print_success(f"Pushed release tag: {resolved.tag}")
            else:
                print_info(f"Push with: git push origin {resolved.tag}")

            self._print_summary(resolved, pdf_path, checksum_path)
            return True

        except Exception as e:
            print_error(f"Release failed: {e}")
            if created_tag:
                self._print_rollback(resolved.tag)
            return False

    def list(self, count: int = 5) -> bool:
        """List release tags."""
        return self.manager.list_releases(count)

    def delete(self, version: str, remote: bool = False) -> bool:
        """Delete a release tag."""
        return self.manager.delete_release(version, remote)

    def _resolve_options(self, options: ReleaseOptions) -> ResolvedReleaseOptions:
        """Apply config defaults to release options."""
        release_config = self.config.get_release_config()
        return ResolvedReleaseOptions(
            tag=options.tag,
            auto_push=options.auto_push,
            dry_run=options.dry_run,
            force=options.force,
            commit=options.commit,
            compile_pdf=_config_bool(options.compile_pdf, release_config["compile"]),
            check_pdf=_config_bool(options.check_pdf, release_config["check_pdf"]),
            bibliography=str(options.bibliography or release_config["bibliography"]),
            github_release=_config_bool(
                options.github_release,
                release_config["github_release"],
            ),
            checksum=_config_bool(options.checksum, release_config["checksum"]),
            allow_dirty=_config_bool(
                options.allow_dirty, release_config["allow_dirty"]
            ),
            tag_policy=str(options.tag_policy or release_config["tag_policy"]),
            document=options.document,
            engine=options.engine,
            output_dir=options.output_dir,
            shell_escape=options.shell_escape,
        )

    def _validate_tag(self, tag: str, policy: str) -> bool:
        """Validate the release tag according to configured policy."""
        if validate_tag(tag, policy):
            return True
        print_error(f"Invalid release tag for {policy!r} policy: {tag}")
        if policy == "paper":
            print_info("Expected examples: v1, v1.0, v1.0.0, v1.0.0-rc.1")
        elif policy == "semver":
            print_info("Expected format: vX.Y.Z with optional prerelease/build suffix")
        return False

    def _preflight(self, options: ResolvedReleaseOptions) -> bool:
        """Run checks that must pass before creating a tag."""
        if options.bibliography not in {"off", "check", "update"}:
            print_error("Bibliography policy must be one of: off, check, update")
            return False

        if self.manager.tag_exists(options.tag) and not options.force:
            print_error(f"Tag already exists: {options.tag}")
            print_info("Use --force to move an existing local tag explicitly.")
            return False

        dirty_files = self.manager.dirty_files(ignore_gitinfo=True)
        if dirty_files and not options.allow_dirty:
            print_error("Tracked or untracked files are dirty.")
            for dirty_file in dirty_files:
                print_info(f"  {dirty_file}")
            print_info("Use --allow-dirty only for an intentional non-clean release.")
            return False

        return True

    def _run_bibliography(self, policy: str) -> bool:
        """Run bibliography check/update according to release policy."""
        args = SimpleNamespace(
            api_key=None,
            user_id=None,
            group_id=None,
            collection=None,
            output=None,
            local_file=None,
            merged_output=None,
        )
        options = BibliographyUpdateOptions(
            no_backup=policy == "check",
            check=policy == "check",
        )
        return self.bibliography_service_cls(self.config).update(args, options)

    def _refresh_metadata(self) -> bool:
        """Refresh gitinfo2 metadata and print the current summary."""
        if refresh_gitinfo2_metadata(self.manager.repo_root):
            summary = gitinfo2_metadata_summary(self.manager.repo_root)
            if summary:
                print_info(f"Version metadata: {summary}")
            return True
        print_error("Could not refresh gitinfo2 metadata.")
        return False

    def _commit_metadata(self, tag: str) -> bool:
        """Commit gitHeadLocal.gin only when explicitly requested."""
        metadata_path = self.manager.repo_root / "gitHeadLocal.gin"
        if not metadata_path.exists():
            print_warning("gitHeadLocal.gin does not exist; nothing to commit.")
            return True
        self.manager.commit_paths(
            ["gitHeadLocal.gin"],
            f"Update gitinfo2 metadata before release {tag}",
        )
        return True

    def _compile(self, options: ResolvedReleaseOptions) -> bool:
        """Compile the configured document."""
        compiler = self.compiler_service_cls(self.config, cwd=self.manager.repo_root)
        return compiler.compile(
            CompileOptions(
                document=options.document,
                engine=options.engine,
                output_dir=options.output_dir,
                shell_escape=options.shell_escape,
            )
        )

    def _check_pdf(self, pdf_path: Optional[Path], tag: str) -> bool:
        """Check that the generated PDF text contains the requested tag."""
        if pdf_path is None:
            print_error("No PDF path could be resolved for release verification.")
            return False
        return pdf_contains_text(pdf_path, tag, self.runner)

    def _create_github_release(self, tag: str, assets: Sequence[Path]) -> bool:
        """Create a GitHub release through gh when explicitly requested."""
        if shutil.which("gh") is None:
            print_error("gh is required for --github-release but was not found.")
            return False
        command = ["gh", "release", "create", tag, "--generate-notes"]
        command.extend(str(path) for path in assets if path.exists())
        result = self.runner.run(command, cwd=self.manager.repo_root)
        if result.returncode == 0:
            print_success(f"Created GitHub release: {tag}")
            return True
        print_error(result.stderr.strip() or "GitHub release creation failed")
        return False

    def _print_dry_run(
        self, options: ResolvedReleaseOptions, pdf_path: Optional[Path]
    ) -> None:
        """Print the release plan without modifying files."""
        print_info("Dry run: no tags, commits, builds, or release files were changed.")
        print_info(f"Would create tag: {options.tag}")
        self._print_git_diagnostics(label="Current")
        if options.force:
            print_info("Would move existing local tag because --force is set.")
        if options.bibliography != "off":
            print_info(f"Would run bibliography policy: {options.bibliography}")
        if options.compile_pdf:
            print_info("Would compile before and after tagging.")
        if options.check_pdf:
            print_info(f"Would verify PDF text contains: {options.tag}")
        if options.checksum and pdf_path is not None:
            print_info(f"Would write checksum for: {pdf_path}")
        if options.github_release:
            print_info("Would create a GitHub release with gh.")
        if options.auto_push:
            print_info(f"Would push tag: {options.tag}")

    def _print_summary(
        self,
        options: ResolvedReleaseOptions,
        pdf_path: Optional[Path],
        checksum_path: Optional[Path],
    ) -> None:
        """Print auditable release summary."""
        print_success(f"Release {options.tag} is ready.")
        print_info(f"Repository: {self.manager.repo_root}")
        self._print_git_diagnostics(label="Release")
        self._print_release_assets(pdf_path, checksum_path)

    def _print_rollback(self, tag: str) -> None:
        """Print rollback guidance for a local tag created by this command."""
        print_info(f"Rollback local tag with: git tag -d {tag}")

    def _print_git_diagnostics(self, label: str) -> None:
        """Print git state and dirty state without mutating the repository."""
        branch = self._git_output(["branch", "--show-current"])
        commit = self._git_output(["rev-parse", "--short", "HEAD"])
        describe = self._git_output(
            ["describe", "--tags", "--long", "--always", "--dirty=-*"]
        )
        exact_tag = self._git_output(["describe", "--tags", "--exact-match"])

        if branch or commit or describe:
            parts = []
            if branch:
                parts.append(f"branch {branch}")
            if commit:
                parts.append(f"commit {commit}")
            if describe:
                parts.append(f"describe {describe}")
            print_info(f"{label} git state: {'; '.join(parts)}")
        if exact_tag:
            print_info(f"{label} tag: {exact_tag}")

        dirty_files = self._dirty_files()
        if not dirty_files:
            print_info(f"{label} dirty files: none")
            return

        print_warning(f"{label} dirty files: {len(dirty_files)}")
        for dirty_file in dirty_files[:5]:
            print_info(f"  {dirty_file}")
        if len(dirty_files) > 5:
            print_info(f"  ... and {len(dirty_files) - 5} more")

    def _print_release_assets(
        self,
        pdf_path: Optional[Path],
        checksum_path: Optional[Path],
    ) -> None:
        """Print release asset paths and verifiable metadata."""
        assets = [path for path in [pdf_path, checksum_path] if path is not None]
        if not assets:
            print_info("Release assets: none")
            return

        print_info("Release assets:")
        if pdf_path is not None:
            print_info(f"  PDF: {pdf_path}")
            self._print_pdf_metadata(pdf_path)
        if checksum_path is not None:
            print_info(f"  Checksum: {checksum_path}")
            digest = self._checksum_digest(checksum_path)
            if digest:
                print_info(f"  SHA256: {digest}")

    def _print_pdf_metadata(self, pdf_path: Path) -> None:
        """Print basic PDF metadata useful for release checks."""
        if not pdf_path.exists():
            print_warning(f"  PDF missing: {pdf_path}")
            return

        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print_info(f"  PDF size: {size_mb:.2f} MB")
        pages = self._pdf_page_count(pdf_path)
        if pages is not None:
            print_info(f"  PDF pages: {pages}")

    def _pdf_page_count(self, pdf_path: Path) -> Optional[str]:
        """Return PDF page count through pdfinfo when available."""
        if shutil.which("pdfinfo") is None:
            return None
        try:
            result = self.runner.run(["pdfinfo", str(pdf_path)], timeout=10)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        stdout = str(result.stdout or "")
        for line in stdout.splitlines():
            if line.startswith("Pages:"):
                page_count = line.split(":", 1)[1].strip()
                return page_count or None
        return None

    def _checksum_digest(self, checksum_path: Path) -> Optional[str]:
        """Return the digest recorded in a sha256 sidecar file."""
        if not checksum_path.exists():
            return None
        first_line = checksum_path.read_text(errors="replace").splitlines()[0:1]
        if not first_line:
            return None
        digest = first_line[0].split()[0]
        return digest or None

    def _git_output(self, args: Sequence[str]) -> Optional[str]:
        """Run a git command through the manager when supported."""
        git = getattr(self.manager, "git", None)
        if git is None:
            return None
        try:
            result = git(list(args))
        except Exception:
            return None
        if result.returncode != 0:
            return None
        output = str(result.stdout or "").strip()
        return output or None

    def _dirty_files(self) -> Sequence[str]:
        """Return dirty files through the manager when supported."""
        dirty_files = getattr(self.manager, "dirty_files", None)
        if dirty_files is None:
            return []
        try:
            return [str(path) for path in dirty_files(ignore_gitinfo=True)]
        except Exception:
            return ["<could not inspect git status>"]


def validate_tag(tag: str, policy: str = "paper") -> bool:
    """Validate tag names for paper/software release policies."""
    import re

    patterns = {
        "paper": r"^v\d+(?:\.\d+){0,2}(?:[-._]?(?:alpha|beta|rc|pre|preview)\.?\d*)?$",
        "semver": (
            r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
            r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
        ),
        "loose": r"^\S+$",
    }
    pattern = patterns.get(policy)
    return bool(pattern and re.match(pattern, tag))


def pdf_contains_text(pdf_path: Path, text: str, runner: CommandRunner) -> bool:
    """Return whether extracted PDF text contains a requested string."""
    if not pdf_path.exists():
        print_error(f"Expected PDF is missing: {pdf_path}")
        return False
    if shutil.which("pdftotext") is None:
        print_error("pdftotext is required for PDF version verification.")
        return False

    result = runner.run(["pdftotext", str(pdf_path), "-"])
    if result.returncode != 0:
        print_error(result.stderr.strip() or "Could not extract PDF text")
        return False
    if text not in result.stdout:
        print_error(f"PDF text does not contain release tag {text}.")
        print_info("Rebuild the PDF after tagging, or disable with --no-pdf-check.")
        return False

    print_success(f"PDF text contains release tag {text}")
    return True


def write_sha256(path: Path) -> Path:
    """Write a sha256 sidecar file and return its path."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum_path = path.with_name(path.name + ".sha256")
    checksum_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return checksum_path


def _absolute_pdf_path(context: ProjectContext) -> Optional[Path]:
    """Return expected PDF path as an absolute path."""
    pdf_path = context.expected_pdf_path()
    if pdf_path is None:
        return None
    if pdf_path.is_absolute():
        return pdf_path
    return (context.project_root / pdf_path).resolve()


def _config_bool(value: Optional[bool], default: object) -> bool:
    """Resolve optional boolean CLI value against config default."""
    return bool(default) if value is None else bool(value)


def _optional_bool(value: object) -> Optional[bool]:
    """Coerce a compatibility keyword into an optional boolean."""
    return None if value is None else bool(value)


def _optional_str(value: object) -> Optional[str]:
    """Coerce a compatibility keyword into an optional string."""
    return None if value is None else str(value)
