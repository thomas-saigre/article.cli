"""
Release tag commands.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..reporting import print_error, print_warning
from ..services.release import ReleaseService


def add_parser(subparsers: Any) -> None:
    """Register release-related command parsers."""
    release_parser = subparsers.add_parser(
        "release",
        help="Create a release tag",
        description="Create a release tag for the current paper state.",
    )
    _add_release_arguments(release_parser)
    release_parser.set_defaults(handler=run_release)

    create_parser = subparsers.add_parser(
        "create",
        help="Deprecated alias for 'release'",
        description="Deprecated alias for 'article-cli release'.",
    )
    _add_release_arguments(create_parser)
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


def _add_release_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared release arguments."""
    parser.add_argument("version", help="Version tag (e.g., v1.0.0)")
    parser.add_argument(
        "--push", action="store_true", help="Automatically push the release"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report the release plan without creating a tag",
    )


def run_release(args: argparse.Namespace, config: Config) -> int:
    """Handle the release command."""
    try:
        service = ReleaseService(manager_cls=GitManager)
        git_config = config.get_git_config()
        auto_push = getattr(args, "push", False) or git_config.get("auto_push", False)
        return (
            0
            if service.create(
                args.version,
                auto_push=auto_push,
                dry_run=getattr(args, "dry_run", False),
            )
            else 1
        )
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1


def run_create(args: argparse.Namespace, config: Config) -> int:
    """Handle the deprecated create command."""
    print_warning("'create' is deprecated; use 'article-cli release <tag>'.")
    return run_release(args, config)


def run_list(args: argparse.Namespace, config: Config) -> int:
    """Handle the list command."""
    try:
        service = ReleaseService(manager_cls=GitManager)
        return 0 if service.list(args.count) else 1
    except ValueError as e:
        print_error(str(e))
        return 1


def run_delete(args: argparse.Namespace, config: Config) -> int:
    """Handle the delete command."""
    try:
        service = ReleaseService(manager_cls=GitManager)
        return 0 if service.delete(args.version, args.remote) else 1
    except ValueError as e:
        print_error(str(e))
        return 1
