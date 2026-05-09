"""
LaTeX build cleanup command.
"""

import argparse
from typing import Any

from ..config import Config
from ..git_manager import GitManager
from ..reporting import print_error
from ..services.git import GitService


def add_parser(subparsers: Any) -> None:
    """Register the clean command parser."""
    parser = subparsers.add_parser("clean", help="Clean LaTeX build files")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the clean command."""
    try:
        service = GitService(manager_cls=GitManager)
        latex_config = config.get_latex_config()
        return 0 if service.clean_latex_files(latex_config["clean_extensions"]) else 1
    except (RuntimeError, ValueError) as e:
        print_error(str(e))
        return 1
