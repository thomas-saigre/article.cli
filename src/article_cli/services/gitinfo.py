"""
gitinfo2 metadata service.
"""

from pathlib import Path
from typing import Optional, Type

from ..git_manager import GitManager


class GitInfoService:
    """Service boundary for gitinfo2 metadata refresh/reporting."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        manager_cls: Type[GitManager] = GitManager,
    ) -> None:
        self.manager = (
            manager_cls(repo_root) if repo_root is not None else manager_cls()
        )

    def refresh(self, dry_run: bool = False) -> bool:
        """Refresh or preview local gitinfo2 metadata."""
        return self.manager.refresh_version_metadata(dry_run)
