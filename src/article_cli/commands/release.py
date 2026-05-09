"""
Release tag commands.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..zotero import print_error


def add_parser(subparsers: Any) -> None:
    """Register release-related command parsers."""
    create_parser = subparsers.add_parser("create", help="Create a new release")
    create_parser.add_argument("version", help="Version tag (e.g., v1.0.0)")
    create_parser.add_argument(
        "--push", action="store_true", help="Automatically push the release"
    )
    create_parser.set_defaults(handler=run_create)

    list_parser = subparsers.add_parser("list", help="List releases")
    list_parser.add_argument(
        "--count", type=int, default=5, help="Number of releases to show"
    )
    list_parser.set_defaults(handler=run_list)

    delete_parser = subparsers.add_parser("delete", help="Delete a release")
    delete_parser.add_argument("version", help="Version tag to delete")
    delete_parser.add_argument(
        "--remote", action="store_true", help="Also delete from remote"
    )
    delete_parser.set_defaults(handler=run_delete)


def run_create(args: argparse.Namespace, config: Config) -> int:
    """Handle the create command."""
    try:
        git_manager = GitManager()
        git_config = config.get_git_config()
        auto_push = args.push or git_config.get("auto_push", False)
        return 0 if git_manager.create_release(args.version, auto_push) else 1
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1


def run_list(args: argparse.Namespace, config: Config) -> int:
    """Handle the list command."""
    try:
        git_manager = GitManager()
        return 0 if git_manager.list_releases(args.count) else 1
    except ValueError as e:
        print_error(str(e))
        return 1


def run_delete(args: argparse.Namespace, config: Config) -> int:
    """Handle the delete command."""
    try:
        git_manager = GitManager()
        return 0 if git_manager.delete_release(args.version, args.remote) else 1
    except ValueError as e:
        print_error(str(e))
        return 1
