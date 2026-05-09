"""
Repository initialization command.
"""

import argparse
from typing import Any

from ..config import Config
from ..repository_setup import RepositorySetup
from ..zotero import print_error


def add_parser(subparsers: Any) -> None:
    """Register the init command parser."""
    parser = subparsers.add_parser(
        "init", help="Initialize repository with workflows and configuration"
    )
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument(
        "--authors",
        required=True,
        help='Comma-separated list of authors (e.g., "John Doe,Jane Smith")',
    )
    parser.add_argument(
        "--group-id",
        default="4678293",
        help="Zotero group ID (default: 4678293 for article.template)",
    )
    parser.add_argument(
        "--tex-file",
        help="Main .tex file (auto-detected if not specified)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--type",
        choices=[
            "article",
            "presentation",
            "poster",
            "typst-presentation",
            "typst-poster",
        ],
        default="article",
        help=(
            "Project type (default: article). Use 'presentation' for Beamer, "
            "'typst-presentation' for Typst slides."
        ),
    )
    parser.add_argument(
        "--theme",
        default="",
        help="Theme for presentations (e.g., 'numpex'). Works with both Beamer and Typst.",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=["169", "43", "1610"],
        default="169",
        help="Aspect ratio for presentations (default: 169 for 16:9).",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the init command."""
    try:
        authors = [a.strip() for a in args.authors.split(",")]

        repo_setup = RepositorySetup()
        return (
            0
            if repo_setup.init_repository(
                title=args.title,
                authors=authors,
                group_id=args.group_id,
                force=args.force,
                main_tex_file=args.tex_file,
                project_type=args.type,
                theme=args.theme,
                aspect_ratio=args.aspect_ratio,
            )
            else 1
        )
    except Exception as e:
        print_error(f"Failed to initialize repository: {e}")
        return 1
