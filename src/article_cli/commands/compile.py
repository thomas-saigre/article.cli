"""
Document compilation command.
"""

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import Config
from ..git_manager import GitManager
from ..zotero import print_error, print_info


def add_parser(subparsers: Any) -> None:
    """Register the compile command parser."""
    parser = subparsers.add_parser(
        "compile", help="Compile LaTeX document using latexmk"
    )
    parser.add_argument(
        "tex_file",
        nargs="?",
        help="Document file to compile (.tex or .typ, auto-detected if not specified)",
    )
    parser.add_argument(
        "--engine",
        choices=["latexmk", "pdflatex", "xelatex", "lualatex", "typst"],
        default=None,
        help=(
            "Compilation engine. Defaults to project config or latexmk. "
            "Use typst for .typ files, xelatex/lualatex for custom fonts."
        ),
    )
    parser.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font path for Typst (can be specified multiple times)",
    )
    shell_escape_group = parser.add_mutually_exclusive_group()
    shell_escape_group.add_argument(
        "--shell-escape",
        dest="shell_escape",
        action="store_true",
        default=None,
        help="Enable shell escape (for code highlighting, etc.)",
    )
    shell_escape_group.add_argument(
        "--no-shell-escape",
        dest="shell_escape",
        action="store_false",
        help="Disable shell escape even if enabled in project config",
    )
    parser.add_argument(
        "--clean-first",
        action="store_true",
        help="Clean build files before compilation",
    )
    parser.add_argument(
        "--clean-after", action="store_true", help="Clean build files after compilation"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for changes and recompile automatically",
    )
    parser.add_argument("--output-dir", help="Output directory for compiled files")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the compile command."""
    try:
        latex_config = config.get_latex_config()
        documents_config = config.get_documents_config()

        engine = args.engine or latex_config.get("engine") or "latexmk"
        doc_file = args.tex_file or documents_config.get("main") or None

        if not doc_file:
            if engine == "typst":
                doc_file = _auto_detect_typ_file()
                if not doc_file:
                    doc_file = _auto_detect_tex_file()
            else:
                doc_file = _auto_detect_tex_file()
                if not doc_file:
                    doc_file = _auto_detect_typ_file()

            if not doc_file:
                print_error(
                    "No .tex or .typ file specified and none found in current directory"
                )
                return 1

        doc_path = Path(doc_file)
        if not doc_path.exists():
            print_error(f"Document file not found: {doc_file}")
            return 1

        if doc_path.suffix == ".typ" and engine != "typst":
            print_info("Detected Typst file, switching engine to typst")
            engine = "typst"
        elif doc_path.suffix == ".tex" and engine == "typst":
            print_error(f"Cannot use Typst engine with .tex file: {doc_file}")
            return 1

        if engine == "typst":
            from ..typst_compiler import TypstCompiler

            typst_compiler = TypstCompiler(config)
            output_dir = _resolve_typst_output_dir(args, config)

            success = typst_compiler.compile(
                typ_file=doc_file,
                output_dir=output_dir,
                font_paths=args.font_paths,
                watch=args.watch,
            )
        else:
            from ..latex_compiler import LaTeXCompiler

            latex_compiler = LaTeXCompiler(config)
            output_dir = _resolve_latex_output_dir(args, config)
            shell_escape = _resolve_shell_escape(args, latex_config)

            if args.clean_first:
                print_info("Cleaning build files before compilation...")
                git_manager = GitManager()
                git_manager.clean_latex_files(latex_config["clean_extensions"])

            success = latex_compiler.compile(
                tex_file=doc_file,
                engine=engine,
                shell_escape=shell_escape,
                output_dir=output_dir,
                watch=args.watch,
            )

            if args.clean_after and success:
                print_info("Cleaning build files after compilation...")
                git_manager = GitManager()
                git_manager.clean_latex_files(latex_config["clean_extensions"])

        return 0 if success else 1

    except Exception as e:
        print_error(f"Compilation failed: {e}")
        return 1


def _resolve_shell_escape(
    args: argparse.Namespace, latex_config: Dict[str, Any]
) -> bool:
    """Resolve shell-escape from CLI and configuration."""
    if args.shell_escape is not None:
        return bool(args.shell_escape)
    return bool(latex_config.get("shell_escape", False))


def _resolve_latex_output_dir(
    args: argparse.Namespace, config: Config
) -> Optional[str]:
    """Resolve LaTeX output directory from CLI and project configuration."""
    if args.output_dir is not None:
        return str(args.output_dir)

    workflow_config = config.get_workflow_config()
    latex_config = config.get_latex_config()
    output_dir = workflow_config.get("output_dir") or latex_config.get("build_dir")
    if output_dir and output_dir != ".":
        return str(output_dir)
    return None


def _resolve_typst_output_dir(
    args: argparse.Namespace, config: Config
) -> Optional[str]:
    """Resolve Typst output directory from CLI and project configuration."""
    if args.output_dir is not None:
        return str(args.output_dir)

    typst_config = config.get_typst_config()
    workflow_config = config.get_workflow_config()
    output_dir = typst_config.get("build_dir") or workflow_config.get("output_dir")
    return str(output_dir) if output_dir else None


def _auto_detect_tex_file() -> Optional[str]:
    """Auto-detect main .tex file in current directory."""
    current_dir = Path.cwd()
    tex_files = list(current_dir.glob("*.tex"))

    if not tex_files:
        return None

    if len(tex_files) == 1:
        return tex_files[0].name

    for pattern in ["main.tex", "article.tex", f"{current_dir.name}.tex"]:
        if (current_dir / pattern).exists():
            return pattern

    print_info(f"Multiple .tex files found, using: {tex_files[0].name}")
    return tex_files[0].name


def _auto_detect_typ_file() -> Optional[str]:
    """Auto-detect main .typ file in current directory."""
    current_dir = Path.cwd()
    typ_files = list(current_dir.glob("*.typ"))

    if not typ_files:
        return None

    if len(typ_files) == 1:
        return typ_files[0].name

    for pattern in [
        "main.typ",
        "presentation.typ",
        "presentation.template.typ",
        f"{current_dir.name}.typ",
    ]:
        if (current_dir / pattern).exists():
            return pattern

    print_info(f"Multiple .typ files found, using: {typ_files[0].name}")
    return typ_files[0].name
