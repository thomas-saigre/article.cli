"""
LaTeX build cleanup command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..zotero import print_error


def add_parser(subparsers: Any) -> None:
    """Register the clean command parser."""
    parser = subparsers.add_parser("clean", help="Clean LaTeX build files")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the clean command."""
    try:
        git_manager = GitManager()
        latex_config = config.get_latex_config()
        return (
            0 if git_manager.clean_latex_files(latex_config["clean_extensions"]) else 1
        )
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
