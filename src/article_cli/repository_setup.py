"""
Repository setup module for article-cli

Provides functionality to initialize LaTeX article repositories with:
- GitHub Actions workflows
- Python project configuration
- README documentation
- Git hooks and configuration
"""

from pathlib import Path
from typing import List, Optional

from .git_hooks import ensure_gitinfo2_hook_source
from .zotero import print_error, print_info, print_success


class RepositorySetup:
    """Handles complete repository initialization for LaTeX article projects"""

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize repository setup

        Args:
            repo_path: Path to repository (defaults to current directory)
        """
        self.repo_path = repo_path or Path.cwd()

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
        - main.tex if no .tex file exists (or presentation/poster template)

        Args:
            title: Document title
            authors: List of author names
            group_id: Zotero group ID
            force: Overwrite existing files if True
            main_tex_file: Main .tex filename (auto-detected if None, created if missing)
            project_type: Type of project ("article", "presentation", "poster")
            theme: Beamer theme for presentations (e.g., "numpex", "metropolis")
            aspect_ratio: Aspect ratio for presentations ("169", "43", "1610")
            additional_documents: List of additional .tex files to compile (e.g., ["poster.tex"])
            output_dir: Output directory for compiled files (e.g., "build")
            fonts_dir: Directory containing custom fonts for XeLaTeX
            install_fonts: Whether to install custom fonts in CI

        Returns:
            True if successful, False otherwise
        """
        print_info(f"Initializing {project_type} repository at: {self.repo_path}")

        # Detect or validate main .tex file, create if missing
        tex_file = self._detect_or_create_tex_file(
            main_tex_file, title, authors, force, project_type, theme, aspect_ratio
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

        try:
            # Create directory structure
            self._create_directories()

            # Create GitHub Actions workflows
            if not self._create_workflow(
                project_name,
                tex_file,
                force,
                project_type,
                additional_documents,
                output_dir,
                fonts_dir,
                install_fonts,
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
            ):
                return False

            # Create README
            if not self._create_readme(
                project_name, title, authors, tex_file, force, project_type
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
            print_info("  4. Run: article-cli update-bibtex")
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
    ) -> Optional[str]:
        """
        Detect main .tex/.typ file in repository or create one if missing

        Args:
            specified: User-specified filename (takes priority)
            title: Document title (for creating new file)
            authors: List of author names (for creating new file)
            force: Overwrite existing file if True
            project_type: Type of project ("article", "presentation", "poster", "typst-presentation")
            theme: Beamer/Typst theme for presentations
            aspect_ratio: Aspect ratio for presentations

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
                specified, title, authors, force, project_type, theme, aspect_ratio
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
                default_name, title, authors, force, project_type, theme, aspect_ratio
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
    ) -> bool:
        """
        Create a LaTeX or Typst file based on project type

        Args:
            filename: Name of the file to create (.tex or .typ)
            title: Document title
            authors: List of author names
            force: Overwrite if exists
            project_type: Type of project ("article", "presentation", "poster", "typst-presentation")
            theme: Beamer/Typst theme for presentations
            aspect_ratio: Aspect ratio for presentations

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
            # Format authors for Typst
            authors_typst = ", ".join([f'"{author}"' for author in authors])

            if project_type in (
                "typst-presentation",
                "presentation",
            ) and filename.endswith(".typ"):
                doc_content = self._get_typst_presentation_template(
                    title, authors_typst, theme
                )
            elif project_type in ("typst-poster", "poster") and filename.endswith(
                ".typ"
            ):
                doc_content = self._get_typst_poster_template(title, authors_typst)
            else:
                doc_content = self._get_typst_presentation_template(
                    title, authors_typst, theme
                )
        else:
            # Format authors for LaTeX
            authors_latex = " \\\\and ".join(authors)

            if project_type == "presentation":
                doc_content = self._get_presentation_template(
                    title, authors_latex, theme, aspect_ratio
                )
            elif project_type == "poster":
                doc_content = self._get_poster_template(title, authors_latex)
            else:
                doc_content = self._get_article_template(title, authors_latex)

        doc_path.write_text(doc_content)
        print_success(f"Created: {doc_path.relative_to(self.repo_path)}")
        return True

    def _get_article_template(self, title: str, authors_latex: str) -> str:
        """Get article template content"""
        return f"""\\documentclass[a4paper,11pt]{{article}}

% Essential packages
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{amsmath,amssymb,amsthm}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}
\\usepackage[margin=1in]{{geometry}}

% Bibliography
\\usepackage[style=numeric,sorting=none]{{biblatex}}
\\addbibresource{{references.bib}}

% Git version information
\\usepackage{{gitinfo2}}

% Title and authors
\\title{{{title}}}
\\author{{{authors_latex}}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
    Your abstract goes here.
\\end{{abstract}}

\\section{{Introduction}}

Your introduction goes here.

\\section{{Methodology}}

Your methodology goes here.

\\section{{Results}}

Your results go here.

\\section{{Conclusion}}

Your conclusion goes here.

% Print bibliography
\\printbibliography

% Git information (optional - appears in footer)
\\vfill
\\hrule
\\small
\\noindent Git version: \\gitAbbrevHash{{}} (\\gitAuthorIsoDate) \\\\
Branch: \\gitBranch

\\end{{document}}
"""

    def _get_presentation_template(
        self, title: str, authors_latex: str, theme: str, aspect_ratio: str
    ) -> str:
        """Get Beamer presentation template content"""
        theme_line = f"\\usetheme{{{theme}}}" if theme else "% \\usetheme{default}"

        return f"""\\documentclass[aspectratio={aspect_ratio}]{{beamer}}

% Theme configuration
{theme_line}

% Essential packages
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
\\pgfplotsset{{compat=newest}}
\\usepackage{{booktabs}}
\\usepackage{{hyperref}}

% Bibliography (optional)
% \\usepackage[style=numeric,sorting=none]{{biblatex}}
% \\addbibresource{{references.bib}}

% Git version information
\\usepackage{{gitinfo2}}

% Title and authors
\\title{{{title}}}
\\author{{{authors_latex}}}
\\date{{\\today}}
\\institute{{Your Institution}}

\\begin{{document}}

\\maketitle

\\begin{{frame}}{{Outline}}
  \\tableofcontents
\\end{{frame}}

\\section{{Introduction}}

\\begin{{frame}}{{Introduction}}
  \\begin{{itemize}}
    \\item First point
    \\item Second point
    \\item Third point
  \\end{{itemize}}
\\end{{frame}}

\\section{{Main Content}}

\\begin{{frame}}{{Main Content}}
  Your main content goes here.
\\end{{frame}}

\\section{{Conclusion}}

\\begin{{frame}}{{Conclusion}}
  \\begin{{itemize}}
    \\item Summary point 1
    \\item Summary point 2
  \\end{{itemize}}
\\end{{frame}}

\\begin{{frame}}{{Questions?}}
  \\centering
  \\Large Thank you for your attention!

  \\vspace{{1cm}}
  \\small
  Git version: \\gitAbbrevHash{{}} (\\gitAuthorIsoDate)
\\end{{frame}}

\\end{{document}}
"""

    def _get_poster_template(self, title: str, authors_latex: str) -> str:
        """Get poster template content"""
        return f"""\\documentclass[a0paper,portrait]{{tikzposter}}

% Essential packages
\\usepackage{{amsmath,amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}

% Git version information
\\usepackage{{gitinfo2}}

% Title and authors
\\title{{{title}}}
\\author{{{authors_latex}}}
\\institute{{Your Institution}}
\\date{{\\today}}

% Theme
\\usetheme{{Default}}

\\begin{{document}}

\\maketitle

\\begin{{columns}}
  \\column{{0.5}}

  \\block{{Introduction}}{{
    Your introduction goes here.
  }}

  \\block{{Methods}}{{
    Your methods description goes here.
  }}

  \\column{{0.5}}

  \\block{{Results}}{{
    Your results go here.
  }}

  \\block{{Conclusions}}{{
    Your conclusions go here.
  }}

\\end{{columns}}

\\block{{References}}{{
  Your references go here.
}}

\\note[targetoffsetx=0cm, targetoffsety=-8cm, width=0.4\\textwidth]{{
  Git version: \\gitAbbrevHash{{}} (\\gitAuthorIsoDate)
}}

\\end{{document}}
"""

    def _get_typst_presentation_template(
        self, title: str, authors_typst: str, theme: str
    ) -> str:
        """Get Typst presentation template content"""
        if theme:
            theme_import = f'#import "{theme}.typ": *'
            theme_show = f"#show: {theme}-theme.with("
        else:
            theme_import = "// No theme specified - using basic Typst presentation"
            theme_show = '#set page(paper: "presentation-16-9")\n#set text(size: 24pt)\n\n// Document metadata\n#let title = '

        if theme:
            return f"""{theme_import}

{theme_show}
  title: "{title}",
  author: [{authors_typst}],
  date: datetime.today().display("[month repr:long] [day], [year]"),
  institution: "Your Institution",
)

// Title slide is automatically generated by the theme

#slide(title: "Outline")[
  #outline()
]

= Introduction

#slide(title: "Introduction")[
  - First point
  - Second point
  - Third point
]

= Main Content

#slide(title: "Main Content")[
  Your main content goes here.
]

= Conclusion

#slide(title: "Conclusion")[
  - Summary point 1
  - Summary point 2
]

#slide(title: "Questions?")[
  #align(center)[
    #text(size: 36pt)[Thank you for your attention!]
  ]
]
"""
        else:
            return f"""// Typst Presentation
// Title: {title}
// Authors: {authors_typst}

#set page(paper: "presentation-16-9", margin: 2cm)
#set text(font: "Helvetica Neue", size: 24pt)

// Title slide
#page[
  #align(center + horizon)[
    #text(size: 48pt, weight: "bold")[{title}]

    #v(1cm)

    #text(size: 28pt)[{authors_typst.replace('"', '')}]

    #v(0.5cm)

    Your Institution

    #v(0.5cm)

    #datetime.today().display("[month repr:long] [day], [year]")
  ]
]

// Introduction
#page[
  #text(size: 36pt, weight: "bold")[Introduction]

  #v(1cm)

  - First point
  - Second point
  - Third point
]

// Main Content
#page[
  #text(size: 36pt, weight: "bold")[Main Content]

  #v(1cm)

  Your main content goes here.
]

// Conclusion
#page[
  #text(size: 36pt, weight: "bold")[Conclusion]

  #v(1cm)

  - Summary point 1
  - Summary point 2
]

// Questions
#page[
  #align(center + horizon)[
    #text(size: 48pt)[Questions?]

    #v(1cm)

    Thank you for your attention!
  ]
]
"""

    def _get_typst_poster_template(self, title: str, authors_typst: str) -> str:
        """Get Typst poster template content"""
        return f"""// Typst Poster
// Title: {title}
// Authors: {authors_typst}

#set page(paper: "a0", margin: 2cm)
#set text(font: "Helvetica Neue", size: 24pt)

// Header
#align(center)[
  #text(size: 72pt, weight: "bold")[{title}]

  #v(1cm)

  #text(size: 36pt)[{authors_typst.replace('"', '')}]

  #text(size: 28pt)[Your Institution]
]

#v(2cm)

#columns(3, gutter: 2cm)[
  // Column 1
  #block(
    fill: rgb("#f0f0f0"),
    inset: 1cm,
    radius: 10pt,
    width: 100%,
  )[
    #text(size: 36pt, weight: "bold")[Introduction]

    #v(0.5cm)

    Your introduction goes here.
  ]

  #v(1cm)

  #block(
    fill: rgb("#f0f0f0"),
    inset: 1cm,
    radius: 10pt,
    width: 100%,
  )[
    #text(size: 36pt, weight: "bold")[Methods]

    #v(0.5cm)

    Your methods description goes here.
  ]

  #colbreak()

  // Column 2
  #block(
    fill: rgb("#f0f0f0"),
    inset: 1cm,
    radius: 10pt,
    width: 100%,
  )[
    #text(size: 36pt, weight: "bold")[Results]

    #v(0.5cm)

    Your results go here.
  ]

  #colbreak()

  // Column 3
  #block(
    fill: rgb("#f0f0f0"),
    inset: 1cm,
    radius: 10pt,
    width: 100%,
  )[
    #text(size: 36pt, weight: "bold")[Conclusions]

    #v(0.5cm)

    Your conclusions go here.
  ]

  #v(1cm)

  #block(
    fill: rgb("#e8f4ea"),
    inset: 1cm,
    radius: 10pt,
    width: 100%,
  )[
    #text(size: 36pt, weight: "bold")[References]

    #v(0.5cm)

    Your references go here.
  ]
]
"""

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

        Returns:
            True if successful
        """
        workflow_path = self.repo_path / ".github" / "workflows" / "latex.yml"

        if workflow_path.exists() and not force:
            print_info(
                f"Workflow already exists: {workflow_path.name} (use --force to overwrite)"
            )
            return True

        # Extract base name (without .tex extension)
        tex_base = tex_file.replace(".tex", "")

        workflow_content = self._get_workflow_template(
            project_name,
            tex_base,
            project_type,
            additional_documents or [],
            output_dir,
            fonts_dir,
            install_fonts,
        )

        workflow_path.write_text(workflow_content)
        print_success(f"Created workflow: {workflow_path.relative_to(self.repo_path)}")
        return True

    def _get_workflow_template(
        self,
        project_name: str,
        tex_base: str,
        project_type: str = "article",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
    ) -> str:
        """
        Get GitHub Actions workflow template

        Args:
            project_name: Name of the project
            tex_base: Base name of .tex file (without extension)
            project_type: Type of project ("article", "presentation", "poster")
            additional_documents: List of additional .tex files to compile
            output_dir: Output directory for compiled files
            fonts_dir: Directory containing custom fonts
            install_fonts: Whether to install fonts in CI

        Returns:
            Workflow YAML content
        """
        additional_documents = additional_documents or []

        # Determine LaTeX engine based on project type
        use_xelatex = project_type in ["presentation", "poster"]
        latexmk_args = "-xelatex" if use_xelatex else "-pdf"

        # Build output directory arguments
        outdir_arg = f"-outdir={output_dir}" if output_dir else ""
        pdf_location = f"{output_dir}/" if output_dir else ""

        # Build output directory echo line (avoid backslash issues in f-strings)
        output_dir_echo = (
            f'echo "- **Output Directory**: `{output_dir}`" >> $GITHUB_STEP_SUMMARY'
            if output_dir
            else ""
        )

        # Build font installation step (only for presentations with custom fonts)
        font_install_step = ""
        if install_fonts and fonts_dir:
            # Build strings separately to avoid backslash issues in f-strings
            backtick = "`"
            triple_backtick = "```"
            find_cmd = (
                "find "
                + fonts_dir
                + ' -type f \\( -name "*.ttf" -o -name "*.otf" -o -name "*.woff" -o -name "*.woff2" \\) -exec cp {} ~/.local/share/fonts/ \\;'
            )
            font_install_step = f"""
      - name: Install custom fonts
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔤 Font Installation" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          # Create user fonts directory
          mkdir -p ~/.local/share/fonts
          
          # Copy fonts from repository
          if [ -d "{fonts_dir}" ]; then
            {find_cmd}
            
            # Update font cache
            fc-cache -f -v
            
            echo "✅ **Fonts Installed Successfully**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "Installed fonts from {backtick}{fonts_dir}/{backtick}:" >> $GITHUB_STEP_SUMMARY
            echo "{triple_backtick}" >> $GITHUB_STEP_SUMMARY
            ls -la ~/.local/share/fonts/ >> $GITHUB_STEP_SUMMARY
            echo "{triple_backtick}" >> $GITHUB_STEP_SUMMARY
          else
            echo "⚠️ **Warning**: Font directory {backtick}{fonts_dir}{backtick} not found" >> $GITHUB_STEP_SUMMARY
          fi
"""

        # Build additional document compilation steps
        additional_compile_steps = ""
        additional_artifact_files = ""
        additional_release_files = ""

        for doc in additional_documents:
            doc_base = doc.replace(".tex", "")
            additional_compile_steps += f"""
      - name: Compile additional document ({doc})
        uses: xu-cheng/latex-action@v3
        if: ${{{{{{ needs.workflow-setup.outputs.runner == 'ubuntu-latest' }}}}}}
        with:
          root_file: {doc}
          latexmk_shell_escape: true
          {f'args: "{outdir_arg}"' if outdir_arg else ''}

      - name: Compile additional document ({doc}) - Self-hosted
        if: ${{{{{{ needs.workflow-setup.outputs.runner == 'self-texlive' }}}}}}
        run: |
          latexmk -shell-escape {latexmk_args} {outdir_arg} -file-line-error -interaction=nonstopmode {doc}
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Additional Document: {doc}" >> $GITHUB_STEP_SUMMARY
          echo "- **Compiled**: ✅" >> $GITHUB_STEP_SUMMARY
"""
            # Add to artifact and release files
            additional_artifact_files += f"\n            ./{pdf_location}{doc_base}.pdf"
            additional_release_files += f"\n            artifact/{doc_base}.pdf"

        return f"""name: Compile LaTeX and Release PDF

# This workflow uses article-cli for:
# - Git hooks setup (article-cli setup)
# - Bibliography updates from Zotero (article-cli update-bibtex)
# - LaTeX build file cleanup (article-cli clean)
#
# Project type: {project_type}
# LaTeX engine: {'XeLaTeX' if use_xelatex else 'pdfLaTeX'}
# Output directory: {output_dir if output_dir else 'root'}
# Additional documents: {', '.join(additional_documents) if additional_documents else 'none'}

on:
  push:
    tags:
      - 'v*'
    branches:
      - 'main'
  pull_request:
    branches:
      - 'main'

jobs:
  workflow-setup:
    name: Workflow Setup
    runs-on: ubuntu-24.04
    outputs:
      runner: ${{{{ steps.texlive_runner.outputs.runner }}}}
      prefix: ${{{{ steps.doc_prefix.outputs.prefix }}}}
      prefixwithref: ${{{{ steps.doc_prefix.outputs.prefixwithref }}}}
      pdf: ${{{{ steps.doc_prefix.outputs.pdf }}}}
      tex: ${{{{ steps.doc_prefix.outputs.tex }}}}
    steps:
      - name: Get TeXLive Runner
        id: texlive_runner
        run: |
          if ! [ -z "$GH_TOKEN" ]; then
            runners=$(gh api -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" /orgs/feelpp/actions/runners)
            texlive=$(echo $runners | jq --arg label "self-texlive" '[.runners[] | any(.labels[]; .name == $label) and .status == "online"] | any')
            if [ "$texlive" = "false" ]; then
               echo "runner=ubuntu-latest" >> "$GITHUB_OUTPUT"
            else
                echo "runner=self-texlive" >> "$GITHUB_OUTPUT"
            fi
          else
            echo "runner=ubuntu-latest" >> "$GITHUB_OUTPUT"
          fi
        env:
          GH_TOKEN: ${{{{ secrets.TOKEN_RUNNER }}}}

      - name: Get Document Prefix
        id: doc_prefix
        run: |
          prefix=$(echo "${{{{ github.repository }}}}" | cut -d'/' -f2)
          echo "prefix=$prefix" >> "$GITHUB_OUTPUT"
          
          # Handle different event types for naming
          if [[ "${{{{ github.event_name }}}}" == "pull_request" ]]; then
            # For pull requests, use pr-NUMBER format
            prefixwithref=$(echo "$prefix")-pr-${{{{ github.event.number }}}}
          else
            # For tags and branches, use the ref name
            prefixwithref=$(echo "$prefix")-${{{{ github.ref_name }}}}
          fi
          
          echo "prefixwithref=$prefixwithref" >> "$GITHUB_OUTPUT"
          echo "pdf=$prefixwithref.pdf" >> "$GITHUB_OUTPUT"
          echo "tex={tex_base}.tex" >> "$GITHUB_OUTPUT"
      -
        name: Show Outputs
        run: |
          echo "runner=${{{{ steps.texlive_runner.outputs.runner }}}}"
          echo "prefix=${{{{ steps.doc_prefix.outputs.prefix }}}}"
          echo "prefixwithref=${{{{ steps.doc_prefix.outputs.prefixwithref }}}}"
          echo "pdf=${{{{ steps.doc_prefix.outputs.pdf }}}}"
          echo "tex=${{{{ steps.doc_prefix.outputs.tex }}}}"


  build_latex:
    needs: workflow-setup
    runs-on: ${{{{ needs.workflow-setup.outputs.runner }}}}
    name: Build LaTeX Artifact
    env:
      VERSION: ${{{{ github.ref_name }}}}
    steps:
      - name: Set up Git repository
        uses: actions/checkout@v4
        with:
          clean: true

      - name: Set up Python and uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"
          enable-cache: false

      - name: Set up Python
        run: uv python install 3.11

      - name: Create virtual environment and install article-cli
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## ⚡ Fast Python Setup with UV" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "Setting up isolated Python environment..." >> $GITHUB_STEP_SUMMARY

          start_time=$(date +%s)
          uv venv .venv --python 3.11
          echo "VIRTUAL_ENV=${{PWD}}/.venv" >> $GITHUB_ENV
          echo "${{PWD}}/.venv/bin" >> $GITHUB_PATH
          uv pip install "article-cli>=1.5.0"
          end_time=$(date +%s)
          duration=$((end_time - start_time))

          echo "✅ **Environment Setup Complete**" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Tool**: UV (fast Python package installer)" >> $GITHUB_STEP_SUMMARY
          echo "- **Python**: 3.11 (isolated virtual environment)" >> $GITHUB_STEP_SUMMARY
          echo "- **Package**: article-cli>=1.5.0" >> $GITHUB_STEP_SUMMARY
          echo "- **Duration**: ${{duration}}s" >> $GITHUB_STEP_SUMMARY
          echo "- **Cache**: Enabled for faster subsequent runs" >> $GITHUB_STEP_SUMMARY

      - name: Install hooks and setup
        run: |
          article-cli setup
          
          # Add git status to summary
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔧 Git Setup" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Event**: ${{{{ github.event_name }}}}" >> $GITHUB_STEP_SUMMARY
          echo "- **Ref**: ${{{{ github.ref }}}}" >> $GITHUB_STEP_SUMMARY
          echo "- **SHA**: ${{{{ github.sha }}}}" >> $GITHUB_STEP_SUMMARY
          
          # For pull requests, stay on the current commit; for branches/tags, checkout the ref
          if [[ "${{{{ github.event_name }}}}" == "pull_request" ]]; then
            echo "- **Action**: Staying on PR merge commit" >> $GITHUB_STEP_SUMMARY
            echo "- **PDF Name**: ${{{{ needs.workflow-setup.outputs.pdf }}}} (pr-${{{{ github.event.number }}}} format)" >> $GITHUB_STEP_SUMMARY
            echo "Pull request detected - staying on current commit ${{{{ github.sha }}}}"
          else
            echo "- **Action**: Checking out ${{{{ github.ref }}}}" >> $GITHUB_STEP_SUMMARY
            echo "- **PDF Name**: ${{{{ needs.workflow-setup.outputs.pdf }}}} (ref-based format)" >> $GITHUB_STEP_SUMMARY
            echo "Checking out ${{{{ github.ref }}}}"
            git checkout ${{{{ github.ref }}}}
          fi

      - name: Show article-cli configuration
        run: |
          article-cli --version
          article-cli config show
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔧 Environment Configuration" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Python Environment:" >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
          echo "UV Version: $(uv --version)" >> $GITHUB_STEP_SUMMARY
          echo "Python Version: $(python --version)" >> $GITHUB_STEP_SUMMARY
          echo "Virtual Environment: $VIRTUAL_ENV" >> $GITHUB_STEP_SUMMARY
          echo "Article CLI: $(article-cli --version)" >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Configuration Details:" >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
          article-cli config show >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY

      - name: Run article-cli doctor diagnostics
        continue-on-error: true
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🩺 article-cli Doctor" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "Running read-only repository diagnostics. This step is non-blocking; build and artifact checks remain authoritative." >> $GITHUB_STEP_SUMMARY

          set +e
          article-cli doctor --json > article-cli-doctor.json
          doctor_status=$?
          set -e

          python -m json.tool article-cli-doctor.json > /tmp/article-cli-doctor.pretty.json
          errors=$(python -c 'import json; print(json.load(open("article-cli-doctor.json"))["summary"]["errors"])')
          warnings=$(python -c 'import json; print(json.load(open("article-cli-doctor.json"))["summary"]["warnings"])')

          echo "- **Exit code**: $doctor_status" >> $GITHUB_STEP_SUMMARY
          echo "- **Errors**: $errors" >> $GITHUB_STEP_SUMMARY
          echo "- **Warnings**: $warnings" >> $GITHUB_STEP_SUMMARY
          echo "- **JSON artifact**: \\`article-cli-doctor.json\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "<details><summary>Doctor JSON</summary>" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`json" >> $GITHUB_STEP_SUMMARY
          cat /tmp/article-cli-doctor.pretty.json >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
          echo "</details>" >> $GITHUB_STEP_SUMMARY

      - name: Update bibliography from Zotero
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 📚 Bibliography Update" >> $GITHUB_STEP_SUMMARY
          echo "Updating bibliography from Zotero group using isolated virtual environment..." >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY

          if article-cli update-bibtex; then
            echo "✅ **Bibliography Updated Successfully**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "- **Environment**: Isolated venv with uv" >> $GITHUB_STEP_SUMMARY
            echo "- **Source**: Zotero Group (configured in pyproject.toml)" >> $GITHUB_STEP_SUMMARY
            echo "- **Output**: references.bib" >> $GITHUB_STEP_SUMMARY
            echo "- **Backup**: references.bib.backup" >> $GITHUB_STEP_SUMMARY
            if [ -f references.bib ]; then
              entries=$(grep -c "^@" references.bib || echo "0")
              echo "- **Total entries**: $entries" >> $GITHUB_STEP_SUMMARY
            fi
          else
            echo "❌ **Bibliography Update Failed**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "Please check Zotero API key and group permissions." >> $GITHUB_STEP_SUMMARY
            exit 1
          fi
        env:
          ZOTERO_API_KEY: ${{{{ secrets.ZOTERO_API_KEY }}}}
{font_install_step}
      - name: Create output directory
        if: ${{{{ '{output_dir}' != '' }}}}
        run: mkdir -p {output_dir}

      - name: Compile LaTeX document
        uses: xu-cheng/latex-action@v3
        if: ${{{{ needs.workflow-setup.outputs.runner == 'ubuntu-latest' }}}}
        with:
          root_file: ${{{{ needs.workflow-setup.outputs.tex }}}}
          latexmk_shell_escape: true
          latexmk_use_xelatex: {'true' if use_xelatex else 'false'}
          {f'args: "{outdir_arg}"' if outdir_arg else ''}
          post_compile: "article-cli clean"

      - name: Generate compilation summary (Ubuntu)
        if: ${{{{ needs.workflow-setup.outputs.runner == 'ubuntu-latest' }}}}
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔨 LaTeX Compilation (Ubuntu)" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Engine**: latexmk {'with XeLaTeX' if use_xelatex else 'with pdfLaTeX'} (shell-escape enabled)" >> $GITHUB_STEP_SUMMARY
          echo "- **Runner**: ubuntu-latest (xu-cheng/latex-action@v3)" >> $GITHUB_STEP_SUMMARY
          echo "- **Source**: `${{{{ needs.workflow-setup.outputs.tex }}}}`" >> $GITHUB_STEP_SUMMARY
          {output_dir_echo}
          echo "- **Clean-up**: article-cli clean (from isolated venv)" >> $GITHUB_STEP_SUMMARY

      - name: Compile LaTeX document
        if: ${{{{ needs.workflow-setup.outputs.runner == 'self-texlive' }}}}
        run: |
          latexmk -shell-escape {latexmk_args} {outdir_arg} -file-line-error -interaction=nonstopmode ${{{{ needs.workflow-setup.outputs.tex }}}}
          article-cli clean
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔨 LaTeX Compilation (Self-hosted)" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Engine**: latexmk {'with XeLaTeX' if use_xelatex else 'with pdfLaTeX'} (shell-escape enabled)" >> $GITHUB_STEP_SUMMARY
          echo "- **Runner**: self-texlive (self-hosted)" >> $GITHUB_STEP_SUMMARY
          echo "- **Source**: `${{{{ needs.workflow-setup.outputs.tex }}}}`" >> $GITHUB_STEP_SUMMARY
          {output_dir_echo}
          echo "- **Clean-up**: article-cli clean (from isolated venv)" >> $GITHUB_STEP_SUMMARY
{additional_compile_steps}
      - name: Rename PDF
        run: |
          mv {pdf_location}{tex_base}.pdf ${{{{ needs.workflow-setup.outputs.pdf }}}}
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 📄 LaTeX Compilation Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          if [ -f "${{{{ needs.workflow-setup.outputs.pdf }}}}" ]; then
            file_size=$(du -h "${{{{ needs.workflow-setup.outputs.pdf }}}}" | cut -f1)
            echo "✅ **PDF Generated Successfully**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "- **File**: \\`${{{{ needs.workflow-setup.outputs.pdf }}}}\\`" >> $GITHUB_STEP_SUMMARY
            echo "- **Size**: $file_size" >> $GITHUB_STEP_SUMMARY
            echo "- **Runner**: ${{{{ needs.workflow-setup.outputs.runner }}}}" >> $GITHUB_STEP_SUMMARY
            echo "- **Source**: \\`${{{{ needs.workflow-setup.outputs.tex }}}}\\`" >> $GITHUB_STEP_SUMMARY
          else
            echo "❌ **PDF Generation Failed**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "Expected file: \\`${{{{ needs.workflow-setup.outputs.pdf }}}}\\`" >> $GITHUB_STEP_SUMMARY
          fi

      - name: Upload Artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{{{ needs.workflow-setup.outputs.pdf }}}}
          path: ${{{{ needs.workflow-setup.outputs.pdf }}}}
      - name: Upload Full Artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{{{ needs.workflow-setup.outputs.prefixwithref }}}}
          path: |
            ./*.tex
            ./*.bib
            ./*.sty
            ./*.cls
            ./*.gin
            ./*.bbl
            ./*.tikz
            ./article-cli-doctor.json
            ./${{{{ needs.workflow-setup.outputs.pdf }}}}{additional_artifact_files}
            ./README.md
            ./fig-*
            ./data/*
            {f'./{fonts_dir}/*' if fonts_dir else ''}
            !./.git*
            !./.github*
            !./.vscode*
            !./.idea*
            !./.DS_Store*
            !./.gitignore*

      - name: Generate build summary
        if: always()
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 📦 Artifact Upload" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Artifact Name**: \\`${{{{ needs.workflow-setup.outputs.prefixwithref }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Included Files:" >> $GITHUB_STEP_SUMMARY
          echo "- LaTeX source files (*.tex, *.sty, *.cls)" >> $GITHUB_STEP_SUMMARY
          echo "- Bibliography files (*.bib)" >> $GITHUB_STEP_SUMMARY
          echo "- Generated PDF: \\`${{{{ needs.workflow-setup.outputs.pdf }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "- Git info files (*.gin)" >> $GITHUB_STEP_SUMMARY
          echo "- Figures and data files" >> $GITHUB_STEP_SUMMARY

  check:
      needs: [build_latex,workflow-setup]
      runs-on: ${{{{ needs.workflow-setup.outputs.runner }}}}
      name: Check LaTeX Artifact
      steps:
      -
        name: Download Artifact
        uses: actions/download-artifact@v4
        with:
          name: ${{{{ needs.workflow-setup.outputs.prefixwithref }}}}
          path: ${{{{ github.workspace }}}}/artifact
      -
        name: Set up Python and uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"
          enable-cache: false
      -
        name: Set up Python
        run: uv python install 3.11
      -
        name: Create virtual environment and install article-cli
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## ⚡ Check Environment Setup" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY

          start_time=$(date +%s)
          uv venv .venv --python 3.11
          echo "VIRTUAL_ENV=${{PWD}}/.venv" >> $GITHUB_ENV
          echo "${{PWD}}/.venv/bin" >> $GITHUB_PATH
          uv pip install "article-cli>=1.5.0"
          end_time=$(date +%s)
          duration=$((end_time - start_time))

          echo "✅ **Check Environment Ready**" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Setup time**: ${{duration}}s (with uv cache)" >> $GITHUB_STEP_SUMMARY
          echo "- **Environment**: Isolated from build job" >> $GITHUB_STEP_SUMMARY
          echo "- **Purpose**: Artifact verification" >> $GITHUB_STEP_SUMMARY
      -
        name: List Artifact
        run: |
          ls -R ${{{{ github.workspace }}}}
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🔍 Artifact Check" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Artifact**: \\`${{{{ needs.workflow-setup.outputs.prefixwithref }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Artifact Contents:" >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
          ls -la ${{{{ github.workspace }}}}/artifact/ >> $GITHUB_STEP_SUMMARY
          echo "\\`\\`\\`" >> $GITHUB_STEP_SUMMARY
      -
        name: Check compilation of LaTeX document from artifact
        if: ${{{{ needs.workflow-setup.outputs.runner == 'ubuntu-latest' }}}}
        uses: xu-cheng/latex-action@v3
        with:
          root_file: ${{{{ needs.workflow-setup.outputs.tex }}}}
          latexmk_shell_escape: true
          latexmk_use_xelatex: {'true' if use_xelatex else 'false'}
          working_directory: ${{{{ github.workspace }}}}/artifact
      -
        name: Generate artifact verification summary (Ubuntu)
        if: ${{{{ needs.workflow-setup.outputs.runner == 'ubuntu-latest' }}}}
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "✅ **Artifact Verification Completed (Ubuntu)**" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **LaTeX compilation from artifact**: Success" >> $GITHUB_STEP_SUMMARY
          echo "- **Runner**: ${{{{ needs.workflow-setup.outputs.runner }}}}" >> $GITHUB_STEP_SUMMARY
          echo "- **Clean-up**: Not needed (artifact already cleaned)" >> $GITHUB_STEP_SUMMARY
      -
        name: Check compilation of LaTeX document from artifact
        if: ${{{{ needs.workflow-setup.outputs.runner == 'self-texlive' }}}}
        run: |
          latexmk -shell-escape {latexmk_args} -file-line-error -interaction=nonstopmode ${{{{ needs.workflow-setup.outputs.tex }}}}
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "✅ **Artifact Verification Completed**" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **LaTeX compilation from artifact**: Success" >> $GITHUB_STEP_SUMMARY
          echo "- **Runner**: ${{{{ needs.workflow-setup.outputs.runner }}}}" >> $GITHUB_STEP_SUMMARY
          echo "- **Clean-up**: Not needed (artifact already cleaned)" >> $GITHUB_STEP_SUMMARY
        working-directory: ${{{{ github.workspace }}}}/artifact

  release:
    needs: [workflow-setup,build_latex, check]
    runs-on: ${{{{ needs.workflow-setup.outputs.runner }}}}
    name: Create Release
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - name: Download Artifact
        uses: actions/download-artifact@v4
        with:
          name: ${{{{ needs.workflow-setup.outputs.prefixwithref }}}}
          path: ${{{{ github.workspace }}}}/artifact

      - name: Archive Article
        run: |
          temp_dir=$(mktemp -d)
          tar -czvf "${{temp_dir}}/${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz" -C artifact ./
          mv "${{temp_dir}}/${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz" ./
          rm -rf "$temp_dir"

          # Generate release summary
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🚀 Release Preparation" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Tag**: \\`${{{{ github.ref_name }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Release Assets:" >> $GITHUB_STEP_SUMMARY

          if [ -f "artifact/${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.pdf" ]; then
            pdf_size=$(du -h "artifact/${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.pdf" | cut -f1)
            echo "- 📄 **PDF**: \\`${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.pdf\\` ($pdf_size)" >> $GITHUB_STEP_SUMMARY
          fi

          if [ -f "${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz" ]; then
            archive_size=$(du -h "${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz" | cut -f1)
            echo "- 📦 **Archive**: \\`${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz\\` ($archive_size)" >> $GITHUB_STEP_SUMMARY
          fi

      - name: Create Release
        id: create_release
        uses: softprops/action-gh-release@v2
        with:
          draft: false
          prerelease: ${{{{ contains(github.ref, 'alpha') || contains(github.ref, 'beta') || contains(github.ref, 'rc') || contains(github.ref, 'preview') }}}}
          name: Release ${{{{ github.ref_name }}}}
          generate_release_notes: true
          tag_name: ${{{{ github.ref }}}}
          token: ${{{{ secrets.GITHUB_TOKEN }}}}
          files: |
            artifact/${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.pdf{additional_release_files}
            ${{{{ needs.workflow-setup.outputs.prefixwithref }}}}.tar.gz

      - name: Generate release summary
        if: always()
        run: |
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## 🎉 Release Created" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          if [ "${{{{ steps.create_release.outcome }}}}" = "success" ]; then
            echo "✅ **Release Published Successfully**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "- **Release**: [${{{{ github.ref_name }}}}](${{{{ steps.create_release.outputs.url }}}})" >> $GITHUB_STEP_SUMMARY
            echo "- **Type**: ${{{{ contains(github.ref, 'alpha') && 'Pre-release' || contains(github.ref, 'beta') && 'Pre-release' || contains(github.ref, 'rc') && 'Pre-release' || contains(github.ref, 'preview') && 'Pre-release' || 'Stable Release' }}}}" >> $GITHUB_STEP_SUMMARY
            echo "- **Assets**: PDF + Source Archive" >> $GITHUB_STEP_SUMMARY
            echo "- **Notes**: Auto-generated from commits" >> $GITHUB_STEP_SUMMARY
          else
            echo "❌ **Release Creation Failed**" >> $GITHUB_STEP_SUMMARY
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "Please check the workflow logs for details." >> $GITHUB_STEP_SUMMARY
          fi
"""

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
    ) -> bool:
        """
        Create pyproject.toml file

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

        Returns:
            True if successful
        """
        pyproject_path = self.repo_path / "pyproject.toml"

        if pyproject_path.exists() and not force:
            print_info("pyproject.toml already exists (use --force to overwrite)")
            return True

        # Format authors for TOML
        authors_toml = ",\n    ".join([f'{{name = "{author}"}}' for author in authors])

        # Determine default engine based on project type
        default_engine = (
            "xelatex" if project_type in ["presentation", "poster"] else "latexmk"
        )

        # Build project type specific config
        project_type_config = f"""
[tool.article-cli.project]
type = "{project_type}"
"""

        if project_type == "presentation":
            project_type_config += f"""
[tool.article-cli.presentation]
theme = "{theme}"
aspect_ratio = "{aspect_ratio}"
color_theme = ""
font_theme = ""
"""
        elif project_type == "poster":
            project_type_config += """
[tool.article-cli.poster]
size = "a0"
orientation = "portrait"
columns = 3
"""

        # Build documents configuration
        documents_config = ""
        if additional_documents:
            additional_list = ", ".join([f'"{doc}"' for doc in additional_documents])
            documents_config = f"""
[tool.article-cli.documents]
# main = "{self.repo_path.name}.tex"  # Uncomment to specify main document
additional = [{additional_list}]
"""

        # Build workflow configuration
        workflow_config = ""
        if output_dir or fonts_dir or install_fonts:
            workflow_config = """
[tool.article-cli.workflow]
"""
            if output_dir:
                workflow_config += f'output_dir = "{output_dir}"\n'
            if fonts_dir:
                workflow_config += f'fonts_dir = "{fonts_dir}"\n'
            if install_fonts:
                workflow_config += f"install_fonts = true\n"

        pyproject_content = f"""# {project_type.capitalize()} Repository Dependency Management
# This file manages dependencies for the LaTeX {project_type} project

[project]
name = "{project_name}"
version = "0.1.0"
description = "{title}"
authors = [
    {authors_toml},
]
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "article-cli>=1.5.0",
    # Add other dependencies your project might need:
    # "matplotlib>=3.5.0",
    # "numpy>=1.20.0",
    # "pandas>=1.3.0",
]

# Configuration for article-cli (embedded in pyproject.toml)
[tool.article-cli.zotero]
group_id = "{group_id}"  # Zotero group ID for this project
# api_key = "your_api_key_here"  # Uncomment and add your API key or use ZOTERO_API_KEY env variable
output_file = "references.bib"

[tool.article-cli.git]
auto_push = false
default_branch = "main"

[tool.article-cli.latex]
clean_extensions = [
    ".aux", ".bbl", ".blg", ".log", ".out", ".pyg",
    ".fls", ".synctex.gz", ".toc", ".fdb_latexmk",
    ".idx", ".ilg", ".ind", ".lof", ".lot", ".nav", ".snm", ".vrb"
]
engine = "{default_engine}"
{project_type_config}{documents_config}{workflow_config}"""

        pyproject_path.write_text(pyproject_content)
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
    ) -> bool:
        """
        Create README.md file

        Args:
            project_name: Name of the project
            title: Document title
            authors: List of author names
            tex_file: Main .tex filename
            force: Overwrite if exists
            project_type: Type of project

        Returns:
            True if successful
        """
        readme_path = self.repo_path / "README.md"

        if readme_path.exists() and not force:
            print_info("README.md already exists (use --force to overwrite)")
            return True

        authors_list = "\n".join([f"- {author}" for author in authors])

        # Determine build command based on project type
        if project_type == "presentation":
            build_cmd = f"latexmk -xelatex {tex_file}"
            doc_type = "presentation"
        elif project_type == "poster":
            build_cmd = f"latexmk -xelatex {tex_file}"
            doc_type = "poster"
        else:
            build_cmd = f"latexmk -pdf {tex_file}"
            doc_type = "article"

        readme_content = f"""# {title}

## Authors

{authors_list}

## Overview

This repository contains the LaTeX source for the {doc_type} "{title}".

## Prerequisites

- Python 3.8+ (for bibliography management)
- LaTeX distribution (TeX Live recommended)
- Git with gitinfo2 package

## Setup

1. **Install article-cli**:
   ```bash
   uv tool install article-cli
   ```

2. **Setup git hooks**:
   ```bash
   article-cli setup
   ```

3. **Configure Zotero** (for bibliography management):
   
   Add your Zotero API key as a secret in GitHub:
   - Go to Repository Settings → Secrets → Actions
   - Add `ZOTERO_API_KEY` with your API key

   Or set it locally:
   ```bash
   export ZOTERO_API_KEY="your_api_key_here"
   ```

4. **Update bibliography**:
   ```bash
   article-cli update-bibtex
   ```

## Building the Document

### Local Build

```bash
{build_cmd}
```

Or using article-cli:
```bash
article-cli compile {tex_file}
```

### Clean Build Files

```bash
article-cli clean
```

## CI/CD

This repository uses GitHub Actions for automated PDF compilation:

- **On push to main**: Compiles and uploads PDF artifact
- **On pull request**: Compiles and verifies the document
- **On tag push (v*)**: Creates a GitHub release with PDF

## Project Structure

```
.
├── {tex_file}              # Main LaTeX document
├── references.bib          # Bibliography (managed via Zotero)
├── pyproject.toml          # Project configuration
├── README.md               # This file
└── .github/
    └── workflows/
        └── latex.yml       # CI/CD pipeline
```

## article-cli Commands

```bash
# Setup repository
article-cli setup

# Update bibliography from Zotero
article-cli update-bibtex

# Clean LaTeX build files
article-cli clean

# Create a release
article-cli create v1.0.0

# List releases
article-cli list

# Show configuration
article-cli config show
```

## Development Workflow

1. Make changes to LaTeX source files
2. Update bibliography if needed: `article-cli update-bibtex`
3. Build locally: `latexmk -pdf {tex_file}`
4. Commit and push changes
5. Create a release tag for publication: `article-cli create v1.0.0 --push`

## License

[Specify your license here]

## Citation

```bibtex
@article{{{project_name},
  title = {{{title}}},
  author = {{{', '.join(authors)}}},
  year = {{2025}},
  url = {{https://github.com/feelpp/{project_name}}}
}}
```
"""

        readme_path.write_text(readme_content)
        print_success(f"Created: {readme_path.relative_to(self.repo_path)}")
        return True

    def _create_gitignore(self, force: bool) -> bool:
        """
        Create or update .gitignore file with LaTeX-specific entries

        Args:
            force: Overwrite if exists

        Returns:
            True if successful
        """
        gitignore_path = self.repo_path / ".gitignore"

        latex_ignores = """
# LaTeX build files
*.aux
*.bbl
*.blg
*.log
*.out
*.toc
*.fdb_latexmk
*.fls
*.synctex.gz
*.pdf
*.dvi
*.ps
*.idx
*.ilg
*.ind
*.lof
*.lot

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.pytest_cache/
.mypy_cache/

# Editor
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# article-cli
.article-cli.toml.backup
references.bib.backup
"""

        if gitignore_path.exists() and not force:
            # Append if not already present
            existing = gitignore_path.read_text()
            if "LaTeX build files" not in existing:
                with open(gitignore_path, "a") as f:
                    f.write(latex_ignores)
                print_info("Updated .gitignore with LaTeX entries")
            else:
                print_info(".gitignore already contains LaTeX entries")
        else:
            gitignore_path.write_text(latex_ignores.lstrip())
            print_success(f"Created: {gitignore_path.relative_to(self.repo_path)}")

        return True

    def _create_vscode_settings(
        self, force: bool, project_type: str = "article"
    ) -> bool:
        """
        Create VS Code settings for LaTeX Workshop

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

        # Use XeLaTeX for presentations and posters
        if project_type in ("presentation", "poster"):
            settings_content = """{
    "latex-workshop.latex.recipes": [
        {
            "name": "latexmk-xelatex",
            "tools": [
                "latexmk-xelatex-shell-escape"
            ]
        },
        {
            "name": "latexmk-lualatex",
            "tools": [
                "latexmk-lualatex-shell-escape"
            ]
        },
        {
            "name": "xelatex-shell-escape-recipe",
            "tools": [
                "xelatex-shell-escape"
            ]
        }
    ],
    "latex-workshop.latex.tools": [
        {
            "name": "latexmk-xelatex-shell-escape",
            "command": "latexmk",
            "args": [
                "--shell-escape",
                "-xelatex",
                "-interaction=nonstopmode",
                "-synctex=1",
                "%DOC%"
            ],
            "env": {}
        },
        {
            "name": "latexmk-lualatex-shell-escape",
            "command": "latexmk",
            "args": [
                "--shell-escape",
                "-lualatex",
                "-interaction=nonstopmode",
                "-synctex=1",
                "%DOC%"
            ],
            "env": {}
        },
        {
            "name": "xelatex-shell-escape",
            "command": "xelatex",
            "args": [
                "--shell-escape",
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
                "%DOC%"
            ]
        }
    ],
    "latex-workshop.latex.autoBuild.run": "onSave",
    "latex-workshop.latex.autoBuild.enabled": true,
    "latex-workshop.latex.build.showOutput": "always",
    "latex-workshop.latex.outDir": "%DIR%",
    "latex-workshop.latex.clean.subfolder.enabled": true,
    "latex-workshop.message.badbox.show": "none",
    "workbench.editor.pinnedTabsOnSeparateRow": true,
    "ltex.latex.commands": {
        "\\\\author{}": "ignore",
        "\\\\IfFileExists{}{}": "ignore",
        "\\\\todo{}": "ignore",
        "\\\\todo[]{}": "ignore",
        "\\\\ts{}": "ignore",
        "\\\\cp{}": "ignore",
        "\\\\pgfmathprintnumber{}": "dummy",
        "\\\\feelpp{}": "dummy",
        "\\\\pgfplotstableread[]{}": "ignore",
        "\\\\xpatchcmd{}{}{}{}{}": "ignore"
    },
    "ltex.enabled": true,
    "ltex.language": "en-US"
}
"""
        else:
            settings_content = """{
    "latex-workshop.latex.recipes": [
        {
            "name": "latexmk-pdf",
            "tools": [
                "latexmk-shell-escape"
            ]
        },
        {
            "name": "pdflatex-shell-escape-recipe",
            "tools": [
                "pdflatex-shell-escape"
            ]
        }
    ],
    "latex-workshop.latex.tools": [
        {
            "name": "latexmk-shell-escape",
            "command": "latexmk",
            "args": [
                "--shell-escape",
                "-pdf",
                "-interaction=nonstopmode",
                "-synctex=1",
                "%DOC%"
            ],
            "env": {}
        },
        {
            "name": "pdflatex-shell-escape",
            "command": "pdflatex",
            "args": [
                "--shell-escape",
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
                "%DOC%"
            ]
        }
    ],
    "latex-workshop.latex.autoBuild.run": "onSave",
    "latex-workshop.latex.autoBuild.enabled": true,
    "latex-workshop.latex.build.showOutput": "always",
    "latex-workshop.latex.outDir": "%DIR%",
    "latex-workshop.latex.clean.subfolder.enabled": true,
    "latex-workshop.message.badbox.show": "none",
    "workbench.editor.pinnedTabsOnSeparateRow": true,
    "ltex.latex.commands": {
        "\\\\author{}": "ignore",
        "\\\\IfFileExists{}{}": "ignore",
        "\\\\todo{}": "ignore",
        "\\\\todo[]{}": "ignore",
        "\\\\ts{}": "ignore",
        "\\\\cp{}": "ignore",
        "\\\\pgfmathprintnumber{}": "dummy",
        "\\\\feelpp{}": "dummy",
        "\\\\pgfplotstableread[]{}": "ignore",
        "\\\\xpatchcmd{}{}{}{}{}": "ignore"
    },
    "ltex.enabled": true,
    "ltex.language": "en-US"
}
"""

        vscode_settings_path.write_text(settings_content)
        print_success(f"Created: {vscode_settings_path.relative_to(self.repo_path)}")

        # Create ltex dictionary files
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
            dictionary_path.write_text(dictionary_content)
            print_info(f"Created: {dictionary_path.relative_to(self.repo_path)}")

        # Hidden false positives file (empty initially)
        false_positives_path = (
            self.repo_path / ".vscode" / "ltex.hiddenFalsePositives.en-US.txt"
        )
        if not false_positives_path.exists() or force:
            false_positives_path.write_text("")
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
