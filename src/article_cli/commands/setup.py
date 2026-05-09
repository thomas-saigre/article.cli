"""
Git hook setup command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..reporting import print_error
from ..services.git import GitService


def add_parser(subparsers: Any) -> None:
    """Register the setup command parser."""
    parser = subparsers.add_parser("setup", help="Setup git hooks for gitinfo2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report setup actions without creating hooks or metadata files",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the setup command."""
    try:
        service = GitService(manager_cls=GitManager)
        return 0 if service.setup_hooks(dry_run=getattr(args, "dry_run", False)) else 1
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
