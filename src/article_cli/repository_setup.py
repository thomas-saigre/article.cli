"""
Repository setup module for article-cli

Provides functionality to initialize LaTeX article repositories with:
- GitHub Actions workflows
- Python project configuration
- README documentation
- Git hooks and configuration
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union

from .git_hooks import ensure_gitinfo2_hook_source
from .template_renderer import TEMPLATE_VERSION, TemplateRenderer
from .reporting import print_error, print_info, print_success

ARTICLE_CLI_MIN_VERSION = "2.0.1"
ARTICLE_TEMPLATES = {
    ("article", "default"): "article/main.tex.j2",
    ("article", "lncs"): "article/lncs.tex.j2",
    ("article", "ieee"): "article/ieee.tex.j2",
    ("typst-article", "default"): "article/main.typ.j2",
    ("typst-article", "lncs"): "article/lncs.typ.j2",
}


@dataclass(frozen=True)
class TemplateValue:
    """Pre-rendered scalar value for templates that need quoted syntax."""

    name: str


@dataclass(frozen=True)
class WorkflowDocument:
    """Additional document metadata for generated workflows."""

    name: str
    base: str
    pdf: str


class RepositorySetup:
    """Handles complete repository initialization for LaTeX article projects"""

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize repository setup

        Args:
            repo_path: Path to repository (defaults to current directory)
        """
        self.repo_path = repo_path or Path.cwd()
        self.renderer = TemplateRenderer()

    def init_repository(
        self,
        title: str,
        authors: List[str],
        group_id: str = "4678293",
        force: bool = False,
        main_tex_file: Optional[str] = None,
        project_type: str = "article",
        theme: str = "",
        aspect_ratio: str = "169",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
        style: str = "default",
        template: str = "",
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_github_runner: str = "ubuntu-24.04",
        ci_self_hosted_label: str = "self-texlive",
        ci_self_hosted_org: str = "",
        ci_release_policy: str = "github",
        ci_artifact_includes: Optional[List[str]] = None,
    ) -> bool:
        """
        Initialize a complete LaTeX repository (article, presentation, or poster)

        Creates:
        - GitHub Actions workflow for automated PDF compilation
        - pyproject.toml with article-cli configuration
        - README.md with documentation
        - .gitignore with LaTeX-specific patterns
        - .vscode/settings.json with LaTeX Workshop configuration
        - LTeX dictionary files for spell checking
        - hooks/post-commit for gitinfo2 integration
        - main.tex or main.typ if no source file exists

        Args:
            title: Document title
            authors: List of author names
            group_id: Zotero group ID
            force: Overwrite existing files if True
            main_tex_file: Main .tex filename (auto-detected if None, created if missing)
            project_type: Type of project ("article", "typst-article", "presentation", "poster")
            theme: Beamer theme for presentations (e.g., "numpex", "metropolis")
            aspect_ratio: Aspect ratio for presentations ("169", "43", "1610")
            additional_documents: List of additional .tex files to compile (e.g., ["poster.tex"])
            output_dir: Output directory for compiled files (e.g., "build")
            fonts_dir: Directory containing custom fonts for XeLaTeX
            install_fonts: Whether to install custom fonts in CI
            style: Built-in document style for generated article templates
            template: Local Jinja2 template path for custom article styles
            ci_bibliography: CI bibliography policy (off, check, update, required)
            ci_runner_policy: CI runner policy (github, self-hosted, self-hosted-auto)
            ci_github_runner: GitHub-hosted runner label
            ci_self_hosted_label: Self-hosted runner label
            ci_self_hosted_org: Organization for opt-in self-hosted runner discovery
            ci_release_policy: CI release policy (github or off)
            ci_artifact_includes: Extra artifact path globs

        Returns:
            True if successful, False otherwise
        """
        ci_artifact_includes = ci_artifact_includes or []
        print_info(f"Initializing {project_type} repository at: {self.repo_path}")

        # Detect or validate main .tex file, create if missing
        tex_file = self._detect_or_create_tex_file(
            main_tex_file,
            title,
            authors,
            force,
            project_type,
            theme,
            aspect_ratio,
            style,
            template,
        )
        if not tex_file:
            print_error("Failed to detect or create main .tex file")
            return False

        project_name = self.repo_path.name
        print_info(f"Project name: {project_name}")
        print_info(f"Project type: {project_type}")
        print_info(f"Main tex file: {tex_file}")
        print_info(f"Title: {title}")
        print_info(f"Authors: {', '.join(authors)}")
        if project_type == "presentation" and theme:
            print_info(f"Beamer theme: {theme}")
        if additional_documents:
            print_info(f"Additional documents: {', '.join(additional_documents)}")
        if output_dir:
            print_info(f"Output directory: {output_dir}")
        if fonts_dir:
            print_info(f"Fonts directory: {fonts_dir}")
        if style:
            print_info(f"Document style: {style}")
        if template:
            print_info(f"Custom template: {template}")

        try:
            # Create directory structure
            self._create_directories()

            # Create GitHub Actions workflows
            if not self._create_workflow(
                project_name=project_name,
                tex_file=tex_file,
                force=force,
                project_type=project_type,
                additional_documents=additional_documents,
                output_dir=output_dir,
                fonts_dir=fonts_dir,
                install_fonts=install_fonts,
                ci_bibliography=ci_bibliography,
                ci_runner_policy=ci_runner_policy,
                ci_github_runner=ci_github_runner,
                ci_self_hosted_label=ci_self_hosted_label,
                ci_self_hosted_org=ci_self_hosted_org,
                ci_release_policy=ci_release_policy,
                ci_artifact_includes=ci_artifact_includes,
            ):
                return False

            # Create pyproject.toml
            if not self._create_pyproject(
                project_name,
                title,
                authors,
                group_id,
                force,
                project_type,
                theme,
                aspect_ratio,
                additional_documents,
                output_dir,
                fonts_dir,
                install_fonts,
                style,
                template,
                tex_file,
                ci_bibliography,
                ci_runner_policy,
                ci_github_runner,
                ci_self_hosted_label,
                ci_self_hosted_org,
                ci_release_policy,
                ci_artifact_includes,
            ):
                return False

            # Create README
            if not self._create_readme(
                project_name,
                title,
                authors,
                tex_file,
                force,
                project_type,
                style,
                ci_bibliography,
                ci_runner_policy,
                ci_release_policy,
            ):
                return False

            # Create .gitignore if needed
            self._create_gitignore(force)

            # Create VS Code configuration
            self._create_vscode_settings(force, project_type)

            # Create git hooks directory and post-commit hook
            self._create_git_hooks(force)

            print_success(
                f"\n✅ {project_type.capitalize()} repository initialization complete!"
            )
            print_info("\nNext steps:")
            print_info("  1. Review and edit pyproject.toml")
            print_info("  2. Add ZOTERO_API_KEY secret to GitHub repository")
            print_info("  3. Run: article-cli setup")
            print_info("  4. Run: article-cli bib update")
            print_info("  5. Commit and push changes")

            return True

        except Exception as e:
            print_error(f"Failed to initialize repository: {e}")
            return False

    def _detect_or_create_tex_file(
        self,
        specified: Optional[str],
        title: str,
        authors: List[str],
        force: bool,
        project_type: str = "article",
        theme: str = "",
        aspect_ratio: str = "169",
        style: str = "default",
        template: str = "",
    ) -> Optional[str]:
        """
        Detect main .tex/.typ file in repository or create one if missing

        Args:
            specified: User-specified filename (takes priority)
            title: Document title (for creating new file)
            authors: List of author names (for creating new file)
            force: Overwrite existing file if True
            project_type: Type of project ("article", "typst-article", "presentation", "poster", "typst-presentation")
            theme: Beamer/Typst theme for presentations
            aspect_ratio: Aspect ratio for presentations
            style: Built-in document style for generated article templates
            template: Local Jinja2 template path for custom article styles

        Returns:
            Main document filename or None on failure
        """
        # Handle Typst project types
        is_typst = project_type.startswith("typst-")
        file_ext = ".typ" if is_typst else ".tex"

        if specified:
            doc_path = self.repo_path / specified
            if doc_path.exists():
                return specified
            # Specified file doesn't exist - create it
            if self._create_tex_file(
                specified,
                title,
                authors,
                force,
                project_type,
                theme,
                aspect_ratio,
                style,
                template,
            ):
                return specified
            return None

        # Auto-detect files
        doc_files = list(self.repo_path.glob(f"*{file_ext}"))

        if not doc_files:
            # No files found - create default based on project type
            if project_type in ("presentation", "typst-presentation"):
                default_name = f"presentation{file_ext}"
            elif project_type in ("poster", "typst-poster"):
                default_name = f"poster{file_ext}"
            else:
                default_name = f"main{file_ext}"
            print_info(f"No {file_ext} file found, creating {default_name}")
            if self._create_tex_file(
                default_name,
                title,
                authors,
                force,
                project_type,
                theme,
                aspect_ratio,
                style,
                template,
            ):
                return default_name
            return None

        if len(doc_files) == 1:
            return doc_files[0].name

        # Multiple files - prefer common patterns
        patterns = [
            f"main{file_ext}",
            f"article{file_ext}",
            f"presentation{file_ext}",
            f"poster{file_ext}",
            f"{self.repo_path.name}{file_ext}",
        ]
        for pattern in patterns:
            if (self.repo_path / pattern).exists():
                return pattern

        # Return first file found
        print_info(
            f"Multiple {file_ext} files found, using: {doc_files[0].name} "
            "(use --tex-file to specify different file)"
        )
        return doc_files[0].name

    def _create_tex_file(
        self,
        filename: str,
        title: str,
        authors: List[str],
        force: bool,
        project_type: str = "article",
        theme: str = "",
        aspect_ratio: str = "169",
        style: str = "default",
        template: str = "",
    ) -> bool:
        """
        Create a LaTeX or Typst file based on project type

        Args:
            filename: Name of the file to create (.tex or .typ)
            title: Document title
            authors: List of author names
            force: Overwrite if exists
            project_type: Type of project ("article", "typst-article", "presentation", "poster", "typst-presentation")
            theme: Beamer/Typst theme for presentations
            aspect_ratio: Aspect ratio for presentations
            style: Built-in document style for generated article templates
            template: Local Jinja2 template path for custom article styles

        Returns:
            True if successful
        """
        doc_path = self.repo_path / filename

        if doc_path.exists() and not force:
            print_info(f"{filename} already exists (use --force to overwrite)")
            return True

        # Determine if this is a Typst project
        is_typst = project_type.startswith("typst-") or filename.endswith(".typ")

        if is_typst:
            if project_type in (
                "typst-presentation",
                "presentation",
            ) and filename.endswith(".typ"):
                doc_content = self._get_typst_presentation_template(
                    title, authors, theme
                )
            elif project_type in ("typst-poster", "poster") and filename.endswith(
                ".typ"
            ):
                doc_content = self._get_typst_poster_template(title, authors)
            elif project_type == "typst-article" or filename.endswith(".typ"):
                doc_content = self._get_typst_article_template(
                    title, authors, style, template
                )
            else:
                doc_content = self._get_typst_presentation_template(
                    title, authors, theme
                )
        else:
            # Format authors for LaTeX
            authors_latex = self._coerce_latex_authors(authors)

            if project_type == "presentation":
                doc_content = self._get_presentation_template(
                    title, authors_latex, theme, aspect_ratio
                )
            elif project_type == "poster":
                doc_content = self._get_poster_template(title, authors_latex)
            else:
                doc_content = self._get_article_template(
                    title, authors_latex, style, template
                )

        doc_path.write_text(doc_content, encoding="utf-8")
        print_success(f"Created: {doc_path.relative_to(self.repo_path)}")
        return True

    @staticmethod
    def _toml_string(value: str) -> str:
        """Return a TOML-compatible quoted string."""
        return json.dumps(value)

    @staticmethod
    def _coerce_latex_authors(authors: Union[str, Sequence[str]]) -> str:
        """Normalize author input for LaTeX templates."""
        if isinstance(authors, str):
            return authors
        return " \\and ".join(authors)

    @staticmethod
    def _coerce_author_list(authors: Union[str, Sequence[str]]) -> List[str]:
        """Normalize author input for Typst templates."""
        if isinstance(authors, str):
            authors = authors.replace("\\and", ",")
            return [
                author.strip().strip('"')
                for author in authors.split(",")
                if author.strip()
            ]
        return list(authors)

    def _article_template_context(
        self, title: str, authors: Union[str, Sequence[str]], style: str
    ) -> dict:
        """Build context shared by built-in and user article templates."""
        author_list = self._coerce_author_list(authors)
        return {
            "title": title,
            "authors": author_list,
            "authors_latex": self._coerce_latex_authors(authors),
            "authors_display": ", ".join(author_list),
            "authors_bibtex": " and ".join(author_list),
            "style": style,
            "template_version": TEMPLATE_VERSION,
        }

    def _render_article_style(
        self,
        project_type: str,
        title: str,
        authors: Union[str, Sequence[str]],
        style: str,
        template: str,
    ) -> str:
        """Render a built-in or user-supplied article template."""
        context = self._article_template_context(title, authors, style)
        if template:
            return self.renderer.render_path(Path(template), context)

        style_key = style or "default"
        template_name = ARTICLE_TEMPLATES.get((project_type, style_key))
        if template_name is None:
            supported = sorted(
                name for kind, name in ARTICLE_TEMPLATES if kind == project_type
            )
            raise ValueError(
                f"Unsupported style '{style_key}' for {project_type}. "
                f"Built-in styles: {', '.join(supported)}. "
                "Use --template to provide a custom Jinja2 template."
            )
        return self.renderer.render(template_name, context)

    @staticmethod
    def _document_base(filename: str) -> str:
        """Return a stable output base name for a source document."""
        return Path(filename).stem

    def _workflow_documents(self, documents: Sequence[str]) -> List[WorkflowDocument]:
        """Build typed workflow metadata for additional LaTeX documents."""
        return [
            WorkflowDocument(
                name=doc,
                base=self._document_base(doc),
                pdf=f"{self._document_base(doc)}.pdf",
            )
            for doc in documents
        ]

    def _get_article_template(
        self,
        title: str,
        authors_latex: Union[str, Sequence[str]],
        style: str = "default",
        template: str = "",
    ) -> str:
        """Get article template content."""
        return self._render_article_style(
            "article", title, authors_latex, style, template
        )

    def _get_typst_article_template(
        self,
        title: str,
        authors_typst: Union[str, Sequence[str]],
        style: str = "default",
        template: str = "",
    ) -> str:
        """Get Typst article template content."""
        return self._render_article_style(
            "typst-article", title, authors_typst, style, template
        )

    def _get_presentation_template(
        self,
        title: str,
        authors_latex: Union[str, Sequence[str]],
        theme: str,
        aspect_ratio: str,
    ) -> str:
        """Get Beamer presentation template content."""
        theme_line = f"\\usetheme{{{theme}}}" if theme else "% \\usetheme{default}"
        return self.renderer.render(
            "presentation/beamer.tex.j2",
            {
                "title": title,
                "authors_latex": self._coerce_latex_authors(authors_latex),
                "theme_line": theme_line,
                "aspect_ratio": aspect_ratio,
            },
        )

    def _get_poster_template(
        self, title: str, authors_latex: Union[str, Sequence[str]]
    ) -> str:
        """Get poster template content."""
        return self.renderer.render(
            "poster/poster.tex.j2",
            {
                "title": title,
                "authors_latex": self._coerce_latex_authors(authors_latex),
            },
        )

    def _get_typst_presentation_template(
        self, title: str, authors_typst: Union[str, Sequence[str]], theme: str
    ) -> str:
        """Get Typst presentation template content."""
        authors = self._coerce_author_list(authors_typst)
        return self.renderer.render(
            "presentation/typst.typ.j2",
            {
                "title": title,
                "authors": authors,
                "authors_display": ", ".join(authors),
                "theme": theme,
                "has_theme": bool(theme),
            },
        )

    def _get_typst_poster_template(
        self, title: str, authors_typst: Union[str, Sequence[str]]
    ) -> str:
        """Get Typst poster template content."""
        authors = self._coerce_author_list(authors_typst)
        return self.renderer.render(
            "poster/poster.typ.j2",
            {
                "title": title,
                "authors_display": ", ".join(authors),
            },
        )

    def _create_directories(self) -> None:
        """Create necessary directory structure"""
        directories = [
            self.repo_path / ".github" / "workflows",
            self.repo_path / ".vscode",
            self.repo_path / "hooks",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print_info(f"Created directory: {directory.relative_to(self.repo_path)}")

    def _create_workflow(
        self,
        project_name: str,
        tex_file: str,
        force: bool,
        project_type: str = "article",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
        style: str = "default",
        template: str = "",
        main_document: str = "",
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_github_runner: str = "ubuntu-24.04",
        ci_self_hosted_label: str = "self-texlive",
        ci_self_hosted_org: str = "",
        ci_release_policy: str = "github",
        ci_artifact_includes: Optional[List[str]] = None,
    ) -> bool:
        """
        Create GitHub Actions workflow file

        Args:
            project_name: Name of the project
            tex_file: Main .tex filename
            force: Overwrite if exists
            project_type: Type of project for workflow customization
            additional_documents: List of additional .tex files to compile
            output_dir: Output directory for compiled files (e.g., "build")
            fonts_dir: Directory containing custom fonts
            install_fonts: Whether to install fonts in CI
            ci_bibliography: CI bibliography policy
            ci_runner_policy: CI runner policy
            ci_github_runner: GitHub-hosted runner label
            ci_self_hosted_label: Self-hosted runner label
            ci_self_hosted_org: Organization for self-hosted auto-discovery
            ci_release_policy: CI release policy
            ci_artifact_includes: Extra artifact path globs

        Returns:
            True if successful
        """
        workflow_path = self.repo_path / ".github" / "workflows" / "latex.yml"

        if workflow_path.exists() and not force:
            print_info(
                f"Workflow already exists: {workflow_path.name} (use --force to overwrite)"
            )
            return True

        workflow_content = self._get_workflow_template(
            project_name,
            tex_file,
            project_type,
            additional_documents or [],
            output_dir,
            fonts_dir,
            install_fonts,
            ci_bibliography,
            ci_runner_policy,
            ci_github_runner,
            ci_self_hosted_label,
            ci_self_hosted_org,
            ci_release_policy,
            ci_artifact_includes or [],
        )

        workflow_path.write_text(workflow_content, encoding="utf-8")
        print_success(f"Created workflow: {workflow_path.relative_to(self.repo_path)}")
        return True

    def _get_workflow_template(
        self,
        project_name: str,
        source_file: str,
        project_type: str = "article",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_github_runner: str = "ubuntu-24.04",
        ci_self_hosted_label: str = "self-texlive",
        ci_self_hosted_org: str = "",
        ci_release_policy: str = "github",
        ci_artifact_includes: Optional[List[str]] = None,
    ) -> str:
        """
        Get GitHub Actions workflow template.

        Args:
            project_name: Name of the project
            source_file: Main source document file
            project_type: Type of project ("article", "presentation", "poster")
            additional_documents: List of additional .tex files to compile
            output_dir: Output directory for compiled files
            fonts_dir: Directory containing custom fonts
            install_fonts: Whether to install fonts in CI
            ci_bibliography: CI bibliography policy
            ci_runner_policy: CI runner policy
            ci_github_runner: GitHub-hosted runner label
            ci_self_hosted_label: Self-hosted runner label
            ci_self_hosted_org: Organization for self-hosted auto-discovery
            ci_release_policy: CI release policy
            ci_artifact_includes: Extra artifact path globs

        Returns:
            Workflow YAML content
        """
        additional_documents = additional_documents or []
        ci_artifact_includes = ci_artifact_includes or []
        workflow_documents = self._workflow_documents(additional_documents)
        is_typst = project_type.startswith("typst-") or source_file.endswith(".typ")
        use_xelatex = project_type in ["presentation", "poster"]
        outdir_arg = f"-outdir={output_dir}" if output_dir else ""
        source_base = self._document_base(source_file)

        return self.renderer.render(
            "github/latex.yml.j2",
            {
                "project_name": project_name,
                "project_type": project_type,
                "source_base": source_base,
                "source_file": source_file,
                "tex_base": source_base,
                "tex_file": source_file,
                "is_typst": is_typst,
                "additional_documents": workflow_documents,
                "additional_documents_label": (
                    ", ".join(additional_documents) if additional_documents else "none"
                ),
                "output_dir": output_dir,
                "output_dir_label": output_dir if output_dir else "root",
                "fonts_dir": fonts_dir,
                "install_fonts": install_fonts,
                "runner_policy": ci_runner_policy,
                "github_runner": ci_github_runner,
                "self_hosted_label": ci_self_hosted_label,
                "self_hosted_org": ci_self_hosted_org,
                "bibliography_policy": ci_bibliography,
                "release_policy": ci_release_policy,
                "artifact_includes": ci_artifact_includes,
                "latex_engine_label": (
                    "Typst" if is_typst else "XeLaTeX" if use_xelatex else "pdfLaTeX"
                ),
                "latexmk_args": "-xelatex" if use_xelatex else "-pdf",
                "latexmk_use_xelatex": "true" if use_xelatex else "false",
                "outdir_arg": outdir_arg,
                "pdf_location": f"{output_dir}/" if output_dir else "",
                "article_cli_min_version": ARTICLE_CLI_MIN_VERSION,
                "template_version": TEMPLATE_VERSION,
            },
        )

    def _create_pyproject(
        self,
        project_name: str,
        title: str,
        authors: List[str],
        group_id: str,
        force: bool,
        project_type: str = "article",
        theme: str = "",
        aspect_ratio: str = "169",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
        style: str = "default",
        template: str = "",
        main_document: str = "",
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_github_runner: str = "ubuntu-24.04",
        ci_self_hosted_label: str = "self-texlive",
        ci_self_hosted_org: str = "",
        ci_release_policy: str = "github",
        ci_artifact_includes: Optional[List[str]] = None,
    ) -> bool:
        """
        Create pyproject.toml file.

        Args:
            project_name: Name of the project
            title: Document title
            authors: List of author names
            group_id: Zotero group ID
            force: Overwrite if exists
            project_type: Type of project
            theme: Beamer theme for presentations
            aspect_ratio: Aspect ratio for presentations
            additional_documents: List of additional .tex files to compile
            output_dir: Output directory for compiled files
            fonts_dir: Directory containing custom fonts
            install_fonts: Whether to install fonts in CI
            style: Built-in document style
            template: Local custom template path
            main_document: Main document written to project config
            ci_bibliography: CI bibliography policy
            ci_runner_policy: CI runner policy
            ci_github_runner: GitHub-hosted runner label
            ci_self_hosted_label: Self-hosted runner label
            ci_self_hosted_org: Organization for self-hosted auto-discovery
            ci_release_policy: CI release policy
            ci_artifact_includes: Extra artifact path globs

        Returns:
            True if successful
        """
        pyproject_path = self.repo_path / "pyproject.toml"

        if pyproject_path.exists() and not force:
            print_info("pyproject.toml already exists (use --force to overwrite)")
            return True

        additional_documents = additional_documents or []
        ci_artifact_includes = ci_artifact_includes or []
        if project_type.startswith("typst-"):
            default_engine = "typst"
        elif project_type in ["presentation", "poster"]:
            default_engine = "xelatex"
        else:
            default_engine = "latexmk"
        content = self.renderer.render(
            "project/pyproject.toml.j2",
            {
                "project_type_title": project_type.capitalize(),
                "project_type": project_type,
                "style_toml": self._toml_string(style or "default"),
                "custom_template": bool(template),
                "template_toml": self._toml_string(template),
                "project_name_toml": self._toml_string(project_name),
                "title_toml": self._toml_string(title),
                "author_entries": [
                    TemplateValue(self._toml_string(author)) for author in authors
                ],
                "article_cli_min_version": ARTICLE_CLI_MIN_VERSION,
                "template_version": TEMPLATE_VERSION,
                "group_id_toml": self._toml_string(group_id),
                "default_engine": default_engine,
                "theme_toml": self._toml_string(theme),
                "aspect_ratio": aspect_ratio,
                "main_document_toml": self._toml_string(
                    main_document or f"{self.repo_path.name}.tex"
                ),
                "additional_documents": additional_documents,
                "additional_document_entries": [
                    TemplateValue(self._toml_string(doc))
                    for doc in additional_documents
                ],
                "output_dir": output_dir,
                "output_dir_toml": self._toml_string(output_dir),
                "fonts_dir": fonts_dir,
                "fonts_dir_toml": self._toml_string(fonts_dir),
                "install_fonts": install_fonts,
                "runner_policy_toml": self._toml_string(ci_runner_policy),
                "github_runner_toml": self._toml_string(ci_github_runner),
                "self_hosted_label_toml": self._toml_string(ci_self_hosted_label),
                "self_hosted_org_toml": self._toml_string(ci_self_hosted_org),
                "bibliography_policy_toml": self._toml_string(ci_bibliography),
                "release_policy_toml": self._toml_string(ci_release_policy),
                "artifact_include_entries": [
                    TemplateValue(self._toml_string(path))
                    for path in ci_artifact_includes
                ],
            },
        )

        pyproject_path.write_text(content, encoding="utf-8")
        print_success(f"Created: {pyproject_path.relative_to(self.repo_path)}")
        return True

    def _create_readme(
        self,
        project_name: str,
        title: str,
        authors: List[str],
        tex_file: str,
        force: bool,
        project_type: str = "article",
        style: str = "default",
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_release_policy: str = "github",
    ) -> bool:
        """
        Create README.md file.

        Args:
            project_name: Name of the project
            title: Document title
            authors: List of author names
            tex_file: Main .tex filename
            force: Overwrite if exists
            project_type: Type of project
            style: Built-in or custom document style
            ci_bibliography: CI bibliography policy
            ci_runner_policy: CI runner policy
            ci_release_policy: CI release policy

        Returns:
            True if successful
        """
        readme_path = self.repo_path / "README.md"

        if readme_path.exists() and not force:
            print_info("README.md already exists (use --force to overwrite)")
            return True

        if project_type == "typst-article":
            build_cmd = f"typst compile {tex_file}"
            doc_type = "Typst article"
        elif project_type == "typst-presentation":
            build_cmd = f"typst compile {tex_file}"
            doc_type = "Typst presentation"
        elif project_type == "typst-poster":
            build_cmd = f"typst compile {tex_file}"
            doc_type = "Typst poster"
        elif project_type == "presentation":
            build_cmd = f"latexmk -xelatex {tex_file}"
            doc_type = "presentation"
        elif project_type == "poster":
            build_cmd = f"latexmk -xelatex {tex_file}"
            doc_type = "poster"
        else:
            build_cmd = f"latexmk -pdf {tex_file}"
            doc_type = "article"

        content = self.renderer.render(
            "project/README.md.j2",
            {
                "project_name": project_name,
                "title": title,
                "authors": authors,
                "tex_file": tex_file,
                "build_cmd": build_cmd,
                "doc_type": doc_type,
                "style": style or "default",
                "ci_bibliography": ci_bibliography,
                "ci_runner_policy": ci_runner_policy,
                "ci_release_policy": ci_release_policy,
                "citation_key": project_name.replace("-", "_"),
                "authors_bibtex": " and ".join(authors),
            },
        )
        readme_path.write_text(content, encoding="utf-8")
        print_success(f"Created: {readme_path.relative_to(self.repo_path)}")
        return True

    def _create_gitignore(self, force: bool) -> bool:
        """
        Create or update .gitignore file with LaTeX-specific entries.

        Args:
            force: Overwrite if exists

        Returns:
            True if successful
        """
        gitignore_path = self.repo_path / ".gitignore"
        latex_ignores = self.renderer.render("project/gitignore.j2", {})

        if gitignore_path.exists() and not force:
            existing = gitignore_path.read_text(encoding="utf-8")
            if "LaTeX build files" not in existing:
                separator = "" if existing.endswith("\n") else "\n"
                gitignore_path.write_text(
                    existing + separator + latex_ignores,
                    encoding="utf-8",
                )
                print_info("Updated .gitignore with LaTeX entries")
            else:
                print_info(".gitignore already contains LaTeX entries")
        else:
            gitignore_path.write_text(latex_ignores, encoding="utf-8")
            print_success(f"Created: {gitignore_path.relative_to(self.repo_path)}")

        return True

    def _create_vscode_settings(
        self, force: bool, project_type: str = "article"
    ) -> bool:
        """
        Create VS Code settings for LaTeX Workshop.

        Args:
            force: Overwrite if exists
            project_type: Type of project (article, presentation, poster)

        Returns:
            True if successful
        """
        vscode_settings_path = self.repo_path / ".vscode" / "settings.json"

        if vscode_settings_path.exists() and not force:
            print_info(
                ".vscode/settings.json already exists (use --force to overwrite)"
            )
            return True

        vscode_settings_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.renderer.render(
            "project/vscode-settings.json.j2",
            {
                "is_typst": project_type.startswith("typst-"),
                "use_xelatex": project_type in ("presentation", "poster"),
            },
        )
        vscode_settings_path.write_text(content, encoding="utf-8")
        print_success(f"Created: {vscode_settings_path.relative_to(self.repo_path)}")

        self._create_ltex_files(force)
        return True

    def _create_ltex_files(self, force: bool) -> bool:
        """
        Create LTeX dictionary and false positives files

        Args:
            force: Overwrite if exists

        Returns:
            True if successful
        """
        # Dictionary file with common LaTeX/math terms
        dictionary_path = self.repo_path / ".vscode" / "ltex.dictionary.en-US.txt"
        if not dictionary_path.exists() or force:
            dictionary_content = """PDEs
PDE
Galerkin
Sobolev
coercivity
pointwise
functionals
parametrical
"""
            dictionary_path.write_text(dictionary_content, encoding="utf-8")
            print_info(f"Created: {dictionary_path.relative_to(self.repo_path)}")

        # Hidden false positives file (empty initially)
        false_positives_path = (
            self.repo_path / ".vscode" / "ltex.hiddenFalsePositives.en-US.txt"
        )
        if not false_positives_path.exists() or force:
            false_positives_path.write_text("", encoding="utf-8")
            print_info(f"Created: {false_positives_path.relative_to(self.repo_path)}")

        return True

    def _create_git_hooks(self, force: bool) -> bool:
        """
        Create git hooks directory with post-commit hook for gitinfo2

        Args:
            force: Overwrite if exists

        Returns:
            True if successful
        """
        ensure_gitinfo2_hook_source(self.repo_path, force)
        return True
