"""
Compiler service.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Type

from ..config import Config
from ..git_manager import GitManager
from ..latex_compiler import LaTeXCompiler
from ..project_context import LATEX_ENGINES, ProjectContext, TYPST_ENGINE
from ..reporting import print_error, print_info
from ..typst_compiler import TypstCompiler


@dataclass(frozen=True)
class CompileOptions:
    """User-facing compile options."""

    document: Optional[str] = None
    engine: Optional[str] = None
    shell_escape: Optional[bool] = None
    output_dir: Optional[str] = None
    font_paths: Optional[List[str]] = None
    clean_first: bool = False
    clean_after: bool = False
    watch: bool = False


class CompilerService:
    """Resolve project policy and dispatch to the right compiler."""

    def __init__(
        self,
        config: Config,
        cwd: Optional[Path] = None,
        latex_compiler_cls: Type[LaTeXCompiler] = LaTeXCompiler,
        typst_compiler_cls: Type[TypstCompiler] = TypstCompiler,
        git_manager_cls: Type[GitManager] = GitManager,
    ) -> None:
        self.config = config
        self.cwd = cwd
        self.latex_compiler_cls = latex_compiler_cls
        self.typst_compiler_cls = typst_compiler_cls
        self.git_manager_cls = git_manager_cls

    def compile(self, options: CompileOptions) -> bool:
        """Compile the resolved document."""
        context = ProjectContext.resolve(
            self.config,
            cwd=self.cwd,
            document=options.document,
            engine=options.engine,
            output_dir=options.output_dir,
            shell_escape=options.shell_escape,
        )

        if context.document is None:
            print_error(
                "No .tex or .typ file specified and none found in current directory"
            )
            return False
        if not context.document.exists():
            print_error(f"Document file not found: {context.document}")
            return False
        if context.document.suffix == ".tex" and context.engine == TYPST_ENGINE:
            print_error(f"Cannot use Typst engine with .tex file: {context.document}")
            return False
        if context.document.suffix == ".typ" and context.engine != TYPST_ENGINE:
            print_info("Detected Typst file, switching engine to typst")

        if context.engine == TYPST_ENGINE:
            return self._compile_typst(context, options)

        if context.engine not in LATEX_ENGINES:
            print_error(f"Unknown engine: {context.engine}")
            return False
        return self._compile_latex(context, options)

    def _compile_typst(
        self,
        context: ProjectContext,
        options: CompileOptions,
    ) -> bool:
        """Compile a Typst document."""
        compiler = self.typst_compiler_cls(self.config)
        return bool(
            compiler.compile(
                typ_file=context.document_name or str(context.document),
                output_dir=context.output_dir_name,
                font_paths=options.font_paths,
                watch=options.watch,
            )
        )

    def _compile_latex(
        self,
        context: ProjectContext,
        options: CompileOptions,
    ) -> bool:
        """Compile a LaTeX document."""
        latex_config = self.config.get_latex_config()
        if options.clean_first:
            print_info("Cleaning build files before compilation...")
            self.git_manager_cls().clean_latex_files(latex_config["clean_extensions"])

        compiler = self.latex_compiler_cls(self.config)
        success = bool(
            compiler.compile(
                tex_file=context.document_name or str(context.document),
                engine=context.engine,
                shell_escape=context.shell_escape,
                output_dir=context.output_dir_name,
                watch=options.watch,
            )
        )

        if options.clean_after and success:
            print_info("Cleaning build files after compilation...")
            self.git_manager_cls().clean_latex_files(latex_config["clean_extensions"])

        return success
