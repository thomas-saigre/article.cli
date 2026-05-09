"""
Main CLI entry point for article-cli.

Command-specific parser and execution logic lives in article_cli.commands.
"""

import argparse
import sys
from pathlib import Path
from typing import Callable, List, Optional

from . import __version__
from .commands import COMMAND_MODULES
from .commands import bibtex as bibtex_command
from .commands import clean as clean_command
from .commands import compile as compile_command
from .commands import config as config_command
from .commands import doctor as doctor_command
from .commands import fonts as fonts_command
from .commands import init as init_command
from .commands import release as release_command
from .commands import setup as setup_command
from .commands import themes as themes_command
from .config import Config
from .reporting import print_error

CommandHandler = Callable[[argparse.Namespace, Config], int]


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="article-cli",
        description="CLI tool for managing LaTeX articles with git and Zotero integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Paper lifecycle
  %(prog)s init --title "My Article" --authors "John Doe,Jane Smith"
  %(prog)s setup --dry-run                # Preview setup actions
  %(prog)s setup                          # Install managed gitinfo2 hooks
  %(prog)s doctor                         # Diagnose repository readiness
  %(prog)s bib update --dry-run           # Preview Zotero bibliography update
  %(prog)s bib update --check             # Check checked-in bibliography freshness
  %(prog)s bib update                     # Update references from Zotero
  %(prog)s compile                        # Compile configured main document
  %(prog)s version                        # Refresh and report git metadata
  %(prog)s version --compile --check-pdf  # Refresh, compile, and inspect PDF text
  %(prog)s release v1 --dry-run           # Preview release tag creation
  %(prog)s release v1                     # Create checked local release tag

  # Common utilities
  %(prog)s compile --engine pdflatex      # Override configured engine
  %(prog)s compile --watch                # Watch and auto-recompile
  %(prog)s compile presentation.typ       # Compile Typst document
  %(prog)s clean                          # Clean build files
  %(prog)s list --count 10                # List 10 recent release tags
  %(prog)s delete v1                      # Delete release tag
  %(prog)s update-bibtex                  # Deprecated alias for bib update
  %(prog)s create v1                      # Deprecated alias for release
  %(prog)s config create                  # Create sample config file
  %(prog)s install-fonts --list           # List installed fonts
  %(prog)s install-theme --list           # List available themes

Environment variables:
  ZOTERO_API_KEY    : Your Zotero API key (required for bib update)
  ZOTERO_USER_ID    : Your Zotero user ID
  ZOTERO_GROUP_ID   : Your Zotero group ID
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--config", type=Path, help="Path to configuration file")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    for command_module in COMMAND_MODULES:
        command_module.add_parser(subparsers)

    return parser


def handle_init_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the init command."""
    return init_command.run(args, config)


def handle_setup_command(config: Config) -> int:
    """Compatibility wrapper for the setup command."""
    return setup_command.run(argparse.Namespace(), config)


def handle_clean_command(config: Config) -> int:
    """Compatibility wrapper for the clean command."""
    return clean_command.run(argparse.Namespace(), config)


def handle_compile_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the compile command."""
    return compile_command.run(args, config)


def handle_create_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the create command."""
    return release_command.run_create(args, config)


def handle_list_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the list command."""
    return release_command.run_list(args, config)


def handle_delete_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the delete command."""
    return release_command.run_delete(args, config)


def handle_update_bibtex_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the update-bibtex command."""
    return bibtex_command.run(args, config)


def handle_config_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the config command."""
    return config_command.run(args, config)


def handle_doctor_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the doctor command."""
    return doctor_command.run(args, config)


def handle_install_fonts_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the install-fonts command."""
    return fonts_command.run(args, config)


def handle_install_theme_command(args: argparse.Namespace, config: Config) -> int:
    """Compatibility wrapper for the install-theme command."""
    return themes_command.run(args, config)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for article-cli.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        quiet_config = args.command == "doctor" and bool(getattr(args, "json", False))
        config = Config(args.config, quiet=quiet_config)
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 1

    try:
        handler = getattr(args, "handler", None)
        if handler is None:
            print_error(f"Unknown command: {args.command}")
            return 1
        return _run_handler(handler, args, config)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1


def _run_handler(
    handler: CommandHandler, args: argparse.Namespace, config: Config
) -> int:
    """Run a command handler with a narrow type boundary for argparse defaults."""
    return handler(args, config)


if __name__ == "__main__":
    sys.exit(main())
