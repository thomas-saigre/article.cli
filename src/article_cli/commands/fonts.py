"""
Font installation command.
"""

import argparse
from pathlib import Path
from typing import Any

from ..config import Config
from ..zotero import print_error, print_info


def add_parser(subparsers: Any) -> None:
    """Register the install-fonts command parser."""
    parser = subparsers.add_parser(
        "install-fonts", help="Download and install fonts for XeLaTeX projects"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory to install fonts (default: fonts/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download fonts even if already installed",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_fonts",
        help="List installed fonts instead of installing",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the install-fonts command."""
    try:
        from ..fonts import FontInstaller

        fonts_config = config.get_fonts_config()
        fonts_dir = (
            args.dir if args.dir else Path(fonts_config.get("directory", "fonts"))
        )

        if args.list_fonts:
            installer = FontInstaller(fonts_dir=fonts_dir)
            installed = installer.list_installed()

            if not installed:
                print_info(f"No fonts installed in {fonts_dir}")
                return 0

            print_info(f"Installed fonts in {fonts_dir}:")
            for font_name in installed:
                font_files = installer.get_font_files(font_name)
                print(f"  - {font_name} ({len(font_files)} font files)")

            return 0

        sources = fonts_config.get("sources", [])
        installer = FontInstaller(fonts_dir=fonts_dir, sources=sources)

        success = installer.install_all(force=args.force)
        return 0 if success else 1

    except Exception as e:
        print_error(f"Font installation failed: {e}")
        return 1
