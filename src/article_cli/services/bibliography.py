"""
Bibliography service.
"""

from dataclasses import dataclass
from typing import Any, Callable

from ..config import Config
from ..reporting import print_info, print_success
from ..zotero import ZoteroBibTexUpdater


@dataclass(frozen=True)
class BibliographyUpdateOptions:
    """User-facing bibliography update options."""

    no_backup: bool = False
    dry_run: bool = False


class BibliographyService:
    """Service boundary for bibliography synchronization."""

    def __init__(
        self,
        config: Config,
        updater_cls: Callable[..., ZoteroBibTexUpdater] = ZoteroBibTexUpdater,
    ) -> None:
        self.config = config
        self.updater_cls = updater_cls

    def update(self, args: Any, options: BibliographyUpdateOptions) -> bool:
        """Validate config and update bibliography data."""
        zotero_config = self.config.validate_zotero_config(args)

        if options.dry_run:
            library = (
                f"group {zotero_config['group_id']}"
                if zotero_config["group_id"]
                else f"user {zotero_config['user_id']}"
            )
            print_info("Dry run: no bibliography files were changed.")
            print_info(f"Would update bibliography from Zotero {library}.")
            print_info(f"Would write: {zotero_config['output_file']}")
            if not options.no_backup:
                print_info("Would create a backup if the output file exists.")
            print_success("Bibliography update dry run completed")
            return True

        updater = self.updater_cls(
            api_key=zotero_config["api_key"],
            user_id=zotero_config["user_id"],
            group_id=zotero_config["group_id"],
            output_file=zotero_config["output_file"],
        )
        return bool(updater.update(backup=not options.no_backup))
