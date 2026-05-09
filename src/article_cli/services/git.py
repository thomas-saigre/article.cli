"""
Git service wrappers.
"""

from pathlib import Path
from typing import List, Optional, Type

from ..git_manager import GitManager


class GitService:
    """Service boundary around repository git operations."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        manager_cls: Type[GitManager] = GitManager,
    ) -> None:
        self.manager = (
            manager_cls(repo_root) if repo_root is not None else manager_cls()
        )

    def setup_hooks(self, dry_run: bool = False) -> bool:
        """Install or preview article-cli managed hooks."""
        return self.manager.setup_hooks(dry_run=dry_run)

    def clean_latex_files(self, extensions: Optional[List[str]] = None) -> bool:
        """Clean LaTeX build files."""
        return self.manager.clean_latex_files(extensions)
