"""
Version metadata command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..reporting import print_error
from ..services.gitinfo import GitInfoService, VersionOptions


def add_parser(subparsers: Any) -> None:
    """Register the version command parser."""
    parser = subparsers.add_parser(
        "version",
        help="Refresh and report git version metadata",
        description=(
            "Refresh gitinfo2 metadata and report the current git version state "
            "without creating a tag."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the current git version state without refreshing files",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile the document after refreshing version metadata",
    )
    parser.add_argument(
        "--check-pdf",
        action="store_true",
        help="Check that the PDF text contains the current git description",
    )
    parser.add_argument(
        "--tag",
        help="Expected version string to check in the PDF instead of git describe",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Write a sha256 checksum sidecar for the resolved PDF",
    )
    parser.add_argument("--document", help="Document to compile or inspect")
    parser.add_argument("--engine", help="Compilation engine override")
    parser.add_argument("--output-dir", help="Compilation output directory")
    parser.add_argument(
        "--shell-escape",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override shell-escape for version compilation",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the version command."""
    try:
        service = GitInfoService(config, manager_cls=GitManager)
        return (
            0
            if service.refresh(
                VersionOptions(
                    dry_run=getattr(args, "dry_run", False),
                    compile_pdf=getattr(args, "compile", False),
                    check_pdf=getattr(args, "check_pdf", False),
                    checksum=getattr(args, "checksum", False),
                    tag=getattr(args, "tag", None),
                    document=getattr(args, "document", None),
                    engine=getattr(args, "engine", None),
                    output_dir=getattr(args, "output_dir", None),
                    shell_escape=getattr(args, "shell_escape", None),
                )
            )
            else 1
        )
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
