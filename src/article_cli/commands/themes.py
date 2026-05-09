"""
Theme installation command.
"""

import argparse
from pathlib import Path
from typing import Any

from ..config import Config
from ..zotero import print_error, print_info


def add_parser(subparsers: Any) -> None:
    """Register the install-theme command parser."""
    parser = subparsers.add_parser(
        "install-theme", help="Download and install Beamer themes for presentations"
    )
    parser.add_argument(
        "theme_name",
        nargs="?",
        help="Name of theme to install (e.g., 'numpex')",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory to install theme (default: current directory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download theme even if already installed",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_themes",
        help="List available themes instead of installing",
    )
    parser.add_argument(
        "--url",
        help="Custom URL to download theme from (use with theme_name)",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the install-theme command."""
    try:
        from ..themes import ThemeInstaller

        themes_config = config.get_themes_config()
        themes_dir = args.dir if args.dir else Path(themes_config.get("directory", "."))
        sources = themes_config.get("sources", {})

        installer = ThemeInstaller(themes_dir=themes_dir, sources=sources)

        if args.list_themes:
            available = installer.list_available()
            installed = installer.list_installed()

            print_info("Available themes:")
            for theme in available:
                name = theme["name"]
                desc = theme.get("description", "")
                engine = theme.get("engine", "pdflatex")
                fonts = (
                    " (requires custom fonts)" if theme.get("requires_fonts") else ""
                )
                installed_marker = (
                    " [installed]" if any(i["name"] == name for i in installed) else ""
                )
                print(f"  - {name}: {desc}")
                print(f"      Engine: {engine}{fonts}{installed_marker}")

            return 0

        if not args.theme_name:
            print_error("Theme name is required. Use --list to see available themes.")
            return 1

        if args.url:
            success = installer.install_from_url(
                name=args.theme_name,
                url=args.url,
                force=args.force,
            )
        else:
            success = installer.install_theme(
                name=args.theme_name,
                force=args.force,
            )

        return 0 if success else 1

    except Exception as e:
        print_error(f"Theme installation failed: {e}")
        return 1
