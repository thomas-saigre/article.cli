"""
Configuration management command.
"""

import argparse
from pathlib import Path
from typing import Any

from ..config import Config
from ..reporting import print_error, print_info


def add_parser(subparsers: Any) -> None:
    """Register the config command parser."""
    parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = parser.add_subparsers(
        dest="config_command", help="Config subcommands"
    )

    create_parser = config_subparsers.add_parser(
        "create", help="Create sample configuration file"
    )
    create_parser.add_argument("--path", type=Path, help="Path for config file")

    config_subparsers.add_parser("show", help="Show current configuration")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle config subcommands."""
    if args.config_command == "create":
        try:
            path = args.path or Path.cwd() / ".article-cli.toml"
            config.create_sample_config(path)
            return 0
        except Exception as e:
            print_error(f"Failed to create config file: {e}")
            return 1

    if args.config_command == "show":
        return _show_config(config)

    print_error("Unknown config command")
    return 1


def _show_config(config: Config) -> int:
    """Print the effective configuration."""
    try:
        print_info("Current configuration:")
        zotero_config = config.get_zotero_config()
        git_config = config.get_git_config()
        latex_config = config.get_latex_config()

        print("\n[Zotero]")
        print(f"  API Key: {'***' if zotero_config['api_key'] else 'Not set'}")
        print(f"  User ID: {zotero_config['user_id'] or 'Not set'}")

        if zotero_config["group_id"]:
            group_display = zotero_config["group_id"]

            if zotero_config["api_key"]:
                try:
                    from ..zotero import ZoteroBibTexUpdater

                    updater = ZoteroBibTexUpdater(
                        api_key=zotero_config["api_key"],
                        group_id=zotero_config["group_id"],
                    )
                    group_name = updater.get_group_name()
                    if group_name:
                        group_display = f"{zotero_config['group_id']} ({group_name})"
                except Exception:
                    pass

            print(f"  Group ID: {group_display}")
        else:
            print("  Group ID: Not set")

        print(f"  Output File: {zotero_config['output_file']}")

        print("\n[Git]")
        print(f"  Auto Push: {git_config['auto_push']}")
        print(f"  Default Branch: {git_config['default_branch']}")

        print("\n[LaTeX]")
        print(f"  Clean Extensions: {len(latex_config['clean_extensions'])} extensions")
        print(f"  Build Directory: {latex_config['build_dir']}")
        print(f"  Engine: {latex_config['engine']}")
        print(f"  Shell Escape: {latex_config['shell_escape']}")
        print(f"  Timeout: {latex_config['timeout']}s")

        return 0
    except Exception as e:
        print_error(f"Failed to show configuration: {e}")
        return 1
