"""
Zotero BibTeX update command.
"""

import argparse
from typing import Any

from ..config import Config
from ..reporting import print_error
from ..services.bibliography import BibliographyService, BibliographyUpdateOptions
from ..zotero import ZoteroBibTexUpdater


def add_parser(subparsers: Any) -> None:
    """Register bibliography command parsers."""
    bib_parser = subparsers.add_parser(
        "bib",
        help="Manage bibliography data",
        description="Manage bibliography data for the paper lifecycle.",
    )
    bib_subparsers = bib_parser.add_subparsers(
        dest="bib_command", help="Bibliography command"
    )
    bib_subparsers.required = True

    update_parser = bib_subparsers.add_parser(
        "update",
        help="Update BibTeX from Zotero",
        description="Update BibTeX references from Zotero.",
    )
    _add_update_arguments(update_parser)
    update_parser.set_defaults(handler=run)

    alias_parser = subparsers.add_parser(
        "update-bibtex",
        help="Deprecated alias for 'bib update'",
        description="Deprecated alias for 'article-cli bib update'.",
    )
    _add_update_arguments(alias_parser)
    alias_parser.set_defaults(handler=run)


def _add_update_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared BibTeX update arguments."""
    parser.add_argument("--api-key", help="Zotero API key")
    parser.add_argument("--user-id", help="Zotero user ID")
    parser.add_argument("--group-id", help="Zotero group ID")
    parser.add_argument("--output", default=None, help="Output BibTeX file")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and report the planned update without writing files",
    )


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the update-bibtex command."""
    try:
        service = BibliographyService(config, updater_cls=ZoteroBibTexUpdater)
        success = service.update(
            args,
            BibliographyUpdateOptions(
                no_backup=bool(getattr(args, "no_backup", False)),
                dry_run=bool(getattr(args, "dry_run", False)),
            ),
        )
        return 0 if success else 1

    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
