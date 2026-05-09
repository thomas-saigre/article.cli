"""
Git hook setup command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..zotero import print_error


def add_parser(subparsers: Any) -> None:
    """Register the setup command parser."""
    parser = subparsers.add_parser("setup", help="Setup git hooks for gitinfo2")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the setup command."""
    try:
        git_manager = GitManager()
        return 0 if git_manager.setup_hooks() else 1
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
