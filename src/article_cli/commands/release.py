"""
Release tag commands.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..reporting import print_error, print_warning
from ..services.release import ReleaseOptions, ReleaseService


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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Move an existing local tag explicitly",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit gitHeadLocal.gin before tagging",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow release with dirty files other than gitHeadLocal.gin",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Do not compile before and after tagging",
    )
    parser.add_argument(
        "--no-pdf-check",
        action="store_true",
        help="Do not check that the PDF text contains the release tag",
    )
    parser.add_argument(
        "--bib",
        choices=["off", "check", "update"],
        help="Bibliography policy for the release",
    )
    parser.add_argument(
        "--github-release",
        action="store_true",
        help="Create a GitHub release with gh after local checks pass",
    )
    parser.add_argument(
        "--no-checksum",
        action="store_true",
        help="Do not write a sha256 checksum sidecar for the PDF",
    )
    parser.add_argument(
        "--tag-policy",
        choices=["paper", "semver", "loose"],
        help="Tag validation policy",
    )
    parser.add_argument("--document", help="Document to compile for release")
    parser.add_argument("--engine", help="Compilation engine override")
    parser.add_argument("--output-dir", help="Compilation output directory")
    parser.add_argument(
        "--shell-escape",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override shell-escape for release compilation",
    )


def run_release(args: argparse.Namespace, config: Config) -> int:
    """Handle the release command."""
    try:
        service = ReleaseService(config, manager_cls=GitManager)
        auto_push = getattr(args, "push", False)
        return (
            0
            if service.release(
                ReleaseOptions(
                    tag=args.version,
                    auto_push=auto_push,
                    dry_run=getattr(args, "dry_run", False),
                    force=getattr(args, "force", False),
                    commit=getattr(args, "commit", False),
                    allow_dirty=True if getattr(args, "allow_dirty", False) else None,
                    compile_pdf=False if getattr(args, "no_compile", False) else None,
                    check_pdf=False if getattr(args, "no_pdf_check", False) else None,
                    bibliography=getattr(args, "bib", None),
                    github_release=(
                        True if getattr(args, "github_release", False) else None
                    ),
                    checksum=False if getattr(args, "no_checksum", False) else None,
                    tag_policy=getattr(args, "tag_policy", None),
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
