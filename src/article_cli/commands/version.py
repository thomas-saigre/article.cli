"""
Version metadata command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..zotero import print_error


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
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the version command."""
    try:
        git_manager = GitManager()
        return 0 if git_manager.refresh_version_metadata(args.dry_run) else 1
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
