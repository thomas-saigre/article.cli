"""
Release service wrappers.
"""

from pathlib import Path
from typing import Optional, Type

from ..git_manager import GitManager


class ReleaseService:
    """Service boundary for tag-based paper releases."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        manager_cls: Type[GitManager] = GitManager,
    ) -> None:
        self.manager = (
            manager_cls(repo_root) if repo_root is not None else manager_cls()
        )

    def create(
        self, version: str, auto_push: bool = False, dry_run: bool = False
    ) -> bool:
        """Create or preview a release tag."""
        return self.manager.create_release(
            version,
            auto_push=auto_push,
            dry_run=dry_run,
        )

    def list(self, count: int = 5) -> bool:
        """List release tags."""
        return self.manager.list_releases(count)

    def delete(self, version: str, remote: bool = False) -> bool:
        """Delete a release tag."""
        return self.manager.delete_release(version, remote)
