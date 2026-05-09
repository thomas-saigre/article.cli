"""
Zotero BibTeX update command.
"""

import argparse
from typing import Any

from ..config import Config
from ..zotero import ZoteroBibTexUpdater, print_error, print_info, print_success


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
        zotero_config = config.validate_zotero_config(args)
        dry_run = bool(getattr(args, "dry_run", False))

        if dry_run:
            library = (
                f"group {zotero_config['group_id']}"
                if zotero_config["group_id"]
                else f"user {zotero_config['user_id']}"
            )
            print_info("Dry run: no bibliography files were changed.")
            print_info(f"Would update bibliography from Zotero {library}.")
            print_info(f"Would write: {zotero_config['output_file']}")
            if not getattr(args, "no_backup", False):
                print_info("Would create a backup if the output file exists.")
            print_success("Bibliography update dry run completed")
            return 0

        updater = ZoteroBibTexUpdater(
            api_key=zotero_config["api_key"],
            user_id=zotero_config["user_id"],
            group_id=zotero_config["group_id"],
            output_file=zotero_config["output_file"],
        )

        return 0 if updater.update(backup=not args.no_backup) else 1

    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
