"""
Bibliography service.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..config import Config
from ..reporting import print_info, print_success
from ..zotero import ZoteroBibTexUpdater


@dataclass(frozen=True)
class BibliographyUpdateOptions:
    """User-facing bibliography update options."""

    no_backup: bool = False
    dry_run: bool = False
    check: bool = False
    include_local: bool = False
    check_citations: bool = False
    timestamp: bool = False


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
            if zotero_config.get("collection_id"):
                print_info(f"Would export collection: {zotero_config['collection_id']}")
            print_info(f"Would write: {zotero_config['output_file']}")
            if options.include_local:
                print_info(
                    f"Would include local entries: {zotero_config['local_file']}"
                )
            if zotero_config.get("merged_output_file"):
                print_info(
                    f"Would write merged file: {zotero_config['merged_output_file']}"
                )
            if options.check:
                print_info("Would check whether bibliography files are current.")
            if options.check_citations:
                print_info("Would check citation key completeness.")
            if not options.no_backup:
                print_info("Would create a backup if the output file exists.")
            print_success("Bibliography update dry run completed")
            return True

        updater = self.updater_cls(
            api_key=zotero_config["api_key"],
            user_id=zotero_config["user_id"],
            group_id=zotero_config["group_id"],
            collection_id=zotero_config.get("collection_id") or None,
            output_file=zotero_config["output_file"],
        )
        return bool(
            updater.update(
                backup=not options.no_backup,
                check=options.check,
                include_local=options.include_local,
                local_file=zotero_config.get("local_file") or None,
                merged_output_file=zotero_config.get("merged_output_file") or None,
                check_citations=options.check_citations,
                citation_sources=_citation_sources(self.config),
                timestamp=options.timestamp
                or not bool(zotero_config.get("deterministic", True)),
            )
        )


def _citation_sources(config: Config) -> list[Path]:
    """Return likely source files for citation completeness checks."""
    documents_config = config.get_documents_config()
    candidates = []
    main = documents_config.get("main")
    if main:
        candidates.append(Path(str(main)))
        candidates.append(Path(str(main)).with_suffix(".aux"))

    for document in documents_config.get("additional") or []:
        candidates.append(Path(str(document)))
        candidates.append(Path(str(document)).with_suffix(".aux"))

    if not candidates:
        candidates.extend(sorted(Path.cwd().glob("*.tex")))
        candidates.extend(sorted(Path.cwd().glob("*.typ")))
        candidates.extend(sorted(Path.cwd().glob("*.aux")))

    return [path for path in candidates if path.exists()]
