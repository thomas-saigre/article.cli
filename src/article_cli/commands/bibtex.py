"""
Zotero BibTeX update command.
"""

import argparse
from typing import Any

from ..config import Config
from ..zotero import ZoteroBibTexUpdater, print_error


def add_parser(subparsers: Any) -> None:
    """Register the update-bibtex command parser."""
    parser = subparsers.add_parser("update-bibtex", help="Update BibTeX from Zotero")
    parser.add_argument("--api-key", help="Zotero API key")
    parser.add_argument("--user-id", help="Zotero user ID")
    parser.add_argument("--group-id", help="Zotero group ID")
    parser.add_argument("--output", default=None, help="Output BibTeX file")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the update-bibtex command."""
    try:
        zotero_config = config.validate_zotero_config(args)

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
