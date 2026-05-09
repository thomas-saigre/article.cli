"""
Document compilation command.
"""

import argparse
from typing import Any

from ..config import Config
from ..reporting import print_error
from ..services.compiler import CompileOptions, CompilerService


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
        service = CompilerService(config)
        success = service.compile(
            CompileOptions(
                document=args.tex_file,
                engine=args.engine,
                shell_escape=args.shell_escape,
                output_dir=args.output_dir,
                font_paths=args.font_paths,
                clean_first=args.clean_first,
                clean_after=args.clean_after,
                watch=args.watch,
            )
        )
        return 0 if success else 1

    except Exception as e:
        print_error(f"Compilation failed: {e}")
        return 1
