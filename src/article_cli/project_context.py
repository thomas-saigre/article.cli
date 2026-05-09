"""
Shared project context resolution for article-cli commands and services.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config

LATEX_ENGINES = {"latexmk", "pdflatex", "xelatex", "lualatex"}
TYPST_ENGINE = "typst"


@dataclass(frozen=True)
class ProjectContext:
    """Resolved project state shared across commands."""

    config: Config
    cwd: Path
    project_root: Path
    project_type: str
    document: Optional[Path]
    engine: str
    output_dir: Optional[Path]
    shell_escape: bool

    @classmethod
    def resolve(
        cls,
        config: Config,
        cwd: Optional[Path] = None,
        document: Optional[str] = None,
        engine: Optional[str] = None,
        output_dir: Optional[str] = None,
        shell_escape: Optional[bool] = None,
    ) -> "ProjectContext":
        """Resolve document, engine, and output policy from CLI and config."""
        resolved_cwd = (cwd or Path.cwd()).resolve()
        root = _resolve_project_root(resolved_cwd)
        project_config = config.get_project_config()
        latex_config = config.get_latex_config()
        documents_config = config.get_documents_config()

        resolved_engine = engine or latex_config.get("engine") or "latexmk"
        document_name = document or documents_config.get("main") or None
        resolved_document = _resolve_document(
            root,
            document_name,
            resolved_engine,
            cwd=resolved_cwd,
            prefer_cwd=document is not None,
        )

        if resolved_document and resolved_document.suffix == ".typ":
            resolved_engine = TYPST_ENGINE
        elif (
            resolved_document
            and resolved_document.suffix == ".tex"
            and (resolved_engine == TYPST_ENGINE)
        ):
            # Keep the invalid combination visible for validation.
            resolved_engine = TYPST_ENGINE

        resolved_output = _resolve_output_dir(
            config,
            resolved_engine,
            output_dir,
        )
        resolved_shell_escape = (
            bool(shell_escape)
            if shell_escape is not None
            else bool(latex_config.get("shell_escape", False))
        )

        return cls(
            config=config,
            cwd=resolved_cwd,
            project_root=root,
            project_type=str(project_config.get("project_type", "article")),
            document=resolved_document,
            engine=str(resolved_engine),
            output_dir=resolved_output,
            shell_escape=resolved_shell_escape,
        )

    @property
    def is_typst(self) -> bool:
        """Whether the resolved compilation engine is Typst."""
        return self.engine == TYPST_ENGINE

    @property
    def document_name(self) -> Optional[str]:
        """Return the document path as a string for compiler APIs."""
        if self.document is None:
            return None
        try:
            return str(self.document.relative_to(self.cwd))
        except ValueError:
            try:
                return str(self.document.relative_to(self.project_root))
            except ValueError:
                return str(self.document)

    @property
    def output_dir_name(self) -> Optional[str]:
        """Return the output directory as a string for compiler APIs."""
        return str(self.output_dir) if self.output_dir else None

    def expected_pdf_path(self) -> Optional[Path]:
        """Return the expected PDF path for the resolved document."""
        if self.document is None:
            return None
        pdf_name = self.document.with_suffix(".pdf").name
        if self.output_dir is not None:
            return self.output_dir / pdf_name
        return self.document.with_suffix(".pdf")

    def as_doctor_context(self) -> Dict[str, Any]:
        """Return stable context fields for doctor JSON output."""
        return {
            "project_type": self.project_type,
            "main_document": str(self.document) if self.document else None,
            "engine": self.engine,
            "output_directory": str(self.output_dir) if self.output_dir else ".",
        }


def _resolve_project_root(cwd: Path) -> Path:
    """Resolve the git project root, falling back to the working directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, OSError):
        pass
    return cwd.resolve()


def _resolve_document(
    root: Path,
    document: Optional[str],
    engine: str,
    cwd: Path,
    prefer_cwd: bool = False,
) -> Optional[Path]:
    """Resolve a configured, explicit, or auto-detected source document."""
    if document:
        path = Path(document)
        if path.is_absolute():
            return path
        if prefer_cwd:
            cwd_candidate = (cwd / path).resolve()
            root_candidate = (root / path).resolve()
            if cwd_candidate.exists() or not root_candidate.exists():
                return cwd_candidate
            return root_candidate
        return (root / path).resolve()

    if engine == TYPST_ENGINE:
        return _auto_detect_typ_file(root) or _auto_detect_tex_file(root)
    return _auto_detect_tex_file(root) or _auto_detect_typ_file(root)


def _auto_detect_tex_file(root: Path) -> Optional[Path]:
    """Auto-detect the main LaTeX file in a project."""
    tex_files = sorted(root.glob("*.tex"))
    if not tex_files:
        return None
    if len(tex_files) == 1:
        return tex_files[0]
    for pattern in ["main.tex", "article.tex", f"{root.name}.tex"]:
        candidate = root / pattern
        if candidate.exists():
            return candidate
    return tex_files[0]


def _auto_detect_typ_file(root: Path) -> Optional[Path]:
    """Auto-detect the main Typst file in a project."""
    typ_files = sorted(root.glob("*.typ"))
    if not typ_files:
        return None
    if len(typ_files) == 1:
        return typ_files[0]
    for pattern in [
        "main.typ",
        "article.typ",
        "presentation.typ",
        "presentation.template.typ",
        f"{root.name}.typ",
    ]:
        candidate = root / pattern
        if candidate.exists():
            return candidate
    return typ_files[0]


def _resolve_output_dir(
    config: Config,
    engine: str,
    output_dir: Optional[str],
) -> Optional[Path]:
    """Resolve output directory from CLI and project configuration."""
    if output_dir is not None:
        return Path(output_dir)

    workflow_config = config.get_workflow_config()
    if engine == TYPST_ENGINE:
        typst_config = config.get_typst_config()
        configured = typst_config.get("build_dir") or workflow_config.get("output_dir")
    else:
        latex_config = config.get_latex_config()
        configured = workflow_config.get("output_dir") or latex_config.get("build_dir")

    if configured and configured != ".":
        return Path(str(configured))
    return None
