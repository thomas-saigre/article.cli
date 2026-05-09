"""
Git operations and release management

Handles git hooks setup, release creation, and LaTeX build file cleanup.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Optional
import shutil

from .git_hooks import (
    ensure_gitinfo2_hook_source,
    gitinfo2_metadata_summary,
    install_managed_gitinfo2_hook,
    refresh_gitinfo2_metadata,
)
from .reporting import Colors, print_error, print_info, print_success, print_warning


class GitManager:
    """Git operations manager for article repositories"""

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize Git manager

        Args:
            repo_root: Repository root directory (defaults to current directory)
        """
        self.repo_root = self._resolve_git_root(repo_root or Path.cwd())

    def _resolve_git_root(self, start_path: Path) -> Path:
        """Resolve the Git repository root, including linked worktrees."""
        cwd = start_path if start_path.is_dir() else start_path.parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
        except (FileNotFoundError, OSError) as e:
            raise ValueError("Git is required but was not found") from e

        if result.returncode != 0:
            details = result.stderr.strip() or str(start_path)
            raise ValueError(f"Not a git repository: {details}")

        return Path(result.stdout.strip()).resolve()

    def _git_path(self, path: str) -> Path:
        """Resolve a Git metadata path using git rev-parse --git-path."""
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", path],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        git_path = Path(result.stdout.strip())
        if not git_path.is_absolute():
            git_path = self.repo_root / git_path
        return git_path.resolve()

    def setup_hooks(self, dry_run: bool = False) -> bool:
        """Setup git hooks for gitinfo2"""
        try:
            git_hooks_dir = self._git_path("hooks")
            post_commit_src = self.repo_root / "hooks" / "post-commit"

            if dry_run:
                print_info("Dry run: no setup files were changed.")
                print_info(f"Would ensure repository hook source: {post_commit_src}")
                print_info(f"Would ensure Git hooks directory: {git_hooks_dir}")
                for hook_name in ["post-commit", "post-checkout", "post-merge"]:
                    print_info(f"Would install or update managed hook: {hook_name}")
                print_info(
                    "Would refresh gitHeadLocal.gin if git metadata is available."
                )
                return True

            git_hooks_dir.mkdir(parents=True, exist_ok=True)
            post_commit_src = ensure_gitinfo2_hook_source(self.repo_root)

            for hook_name in ["post-commit", "post-checkout", "post-merge"]:
                dest = git_hooks_dir / hook_name
                status = install_managed_gitinfo2_hook(post_commit_src, dest)
                if status == "created":
                    print_success(f"Installed hook: {hook_name}")
                elif status == "updated":
                    print_success(f"Updated managed hook: {hook_name}")
                elif status == "merged":
                    print_success(
                        f"Preserved existing hook and added managed block: {hook_name}"
                    )
                else:
                    print_info(f"Hook already current: {hook_name}")

            if refresh_gitinfo2_metadata(self.repo_root):
                print_success("Refreshed gitHeadLocal.gin")
                summary = gitinfo2_metadata_summary(self.repo_root)
                if summary:
                    print_info(f"Version metadata: {summary}")
                print_info(
                    "gitHeadLocal.gin was not committed; commit it explicitly if your "
                    "paper policy tracks generated metadata."
                )
            else:
                print_warning(
                    "Could not refresh gitHeadLocal.gin yet. This is expected before "
                    "the first commit."
                )

            return True

        except subprocess.CalledProcessError as e:
            print_error(f"Git command failed: {e}")
            return False
        except Exception as e:
            print_error(f"Failed to setup hooks: {e}")
            return False

    def refresh_version_metadata(self, dry_run: bool = False) -> bool:
        """
        Refresh and report gitinfo2 version metadata without creating tags.

        Args:
            dry_run: Report planned actions without writing gitHeadLocal.gin

        Returns:
            True if the current git state could be reported, False otherwise
        """
        commit = self._git_output(["rev-parse", "--short", "HEAD"]) or "unknown"
        describe = self._git_output(
            ["describe", "--tags", "--long", "--always", "--dirty=-*"]
        )
        branch = self._git_output(["branch", "--show-current"]) or "detached"

        print_info(f"Git branch: {branch}")
        print_info(f"Git commit: {commit}")
        if describe:
            print_info(f"Git describe: {describe}")

        if dry_run:
            print_info("Dry run: no version metadata files were changed.")
            print_info("Would refresh gitHeadLocal.gin from gitinfo2 metadata.")
            return True

        if refresh_gitinfo2_metadata(self.repo_root):
            print_success("Refreshed gitHeadLocal.gin")
            summary = gitinfo2_metadata_summary(self.repo_root)
            if summary:
                print_info(f"Version metadata: {summary}")
        else:
            print_warning(
                "Could not refresh gitHeadLocal.gin. Run article-cli setup after "
                "the first commit if gitinfo2 hooks are missing."
            )

        return True

    def create_release(
        self, version: str, auto_push: bool = False, dry_run: bool = False
    ) -> bool:
        """
        Create a new release with the given version

        Args:
            version: Version string (e.g., 'v1.0.0')
            auto_push: Whether to automatically push the release
            dry_run: Validate and report actions without creating a release

        Returns:
            True if successful, False otherwise
        """
        # Validate version format
        if not re.match(r"^v\d+\.\d+\.\d+(-[a-z]+\.\d+)?$", version):
            print_error(f"Invalid version format: {version}")
            print_info("Expected format: vX.Y.Z or vX.Y.Z-pre.N")
            return False

        try:
            # Check if tag exists
            result = subprocess.run(
                ["git", "rev-parse", version], capture_output=True, cwd=self.repo_root
            )
            if result.returncode == 0:
                print_error(f"Tag {version} already exists")
                return False

            if dry_run:
                print_info("Dry run: no tags, commits, or metadata files were changed.")
                print_info(f"Would create annotated tag: {version}")
                print_info("Would refresh gitHeadLocal.gin after tagging.")
                if auto_push:
                    print_info("Would push with: git push origin --follow-tags")
                else:
                    print_info("Would leave push to the user.")
                return True

            # Create tag
            subprocess.run(
                ["git", "tag", "-a", version, "-m", f"Release {version}"],
                check=True,
                cwd=self.repo_root,
            )
            print_success(f"Created tag: {version}")

            # Trigger hooks
            subprocess.run(["git", "checkout"], check=True, cwd=self.repo_root)

            # Copy gitHeadInfo
            git_head_info = self.repo_root / ".git" / "gitHeadInfo.gin"
            if git_head_info.exists():
                local_copy = self.repo_root / "gitHeadLocal.gin"
                with open(git_head_info, "r") as src:
                    content = src.read()
                    with open(local_copy, "w") as dst:
                        dst.write(content)

                    # Show reltag
                    for line in content.split("\n"):
                        if "reltag" in line:
                            print_info(f"Release tag: {line}")

                subprocess.run(
                    ["git", "add", "gitHeadLocal.gin"], check=True, cwd=self.repo_root
                )
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"Updated gitHeadLocal.gin for release {version}",
                    ],
                    check=True,
                    cwd=self.repo_root,
                )
                subprocess.run(
                    ["git", "tag", "-f", "-a", version, "-m", f"Release {version}"],
                    check=True,
                    cwd=self.repo_root,
                )

            print_success(f"Release {version} created successfully")

            if auto_push:
                try:
                    subprocess.run(
                        ["git", "push", "origin", "--follow-tags"],
                        check=True,
                        cwd=self.repo_root,
                    )
                    print_success("Release pushed to remote")
                except subprocess.CalledProcessError as e:
                    print_warning(f"Failed to push release: {e}")
                    print_info("Push manually with: git push origin --follow-tags")
            else:
                print_info("Push with: git push origin --follow-tags")

            return True

        except subprocess.CalledProcessError as e:
            print_error(f"Git command failed: {e}")
            return False
        except Exception as e:
            print_error(f"Failed to create release: {e}")
            return False

    def _git_output(self, args: List[str]) -> Optional[str]:
        """Run git and return stdout without the trailing newline."""
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.repo_root,
            )
        except (FileNotFoundError, OSError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def list_releases(self, count: int = 5) -> bool:
        """
        List recent releases

        Args:
            count: Number of releases to show

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-creatordate"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.repo_root,
            )

            tags = result.stdout.strip().split("\n")
            if not tags or tags == [""]:
                print_info("No releases found")
                return True

            print(f"\n{Colors.BOLD}Recent releases:{Colors.ENDC}")
            for i, tag in enumerate(tags[:count], 1):
                print(f"  {i}. {tag}")

            if len(tags) > count:
                print(f"  ... and {len(tags) - count} more")

            return True

        except subprocess.CalledProcessError as e:
            print_error(f"Failed to list releases: {e}")
            return False

    def delete_release(self, version: str, delete_remote: bool = False) -> bool:
        """
        Delete a release tag

        Args:
            version: Version tag to delete
            delete_remote: Whether to also delete from remote

        Returns:
            True if successful, False otherwise
        """
        try:
            subprocess.run(
                ["git", "tag", "-d", version], check=True, cwd=self.repo_root
            )
            print_success(f"Deleted local tag: {version}")

            if delete_remote:
                try:
                    subprocess.run(
                        ["git", "push", "origin", "--delete", version],
                        check=True,
                        cwd=self.repo_root,
                    )
                    print_success(f"Deleted remote tag: {version}")
                except subprocess.CalledProcessError as e:
                    print_warning(f"Failed to delete remote tag: {e}")
                    print_info(
                        f"Delete manually with: git push origin --delete {version}"
                    )
            else:
                print_info(f"To delete remote: git push origin --delete {version}")

            return True

        except subprocess.CalledProcessError as e:
            print_error(f"Failed to delete tag: {e}")
            return False

    def clean_latex_files(self, extensions: Optional[List[str]] = None) -> bool:
        """
        Clean LaTeX build files

        Args:
            extensions: List of file extensions to clean (defaults to common LaTeX files)

        Returns:
            True if successful, False otherwise
        """
        if extensions is None:
            extensions = [
                ".aux",
                ".bbl",
                ".blg",
                ".log",
                ".out",
                ".pyg",
                ".fls",
                ".synctex.gz",
                ".toc",
                ".fdb_latexmk",
                ".idx",
                ".ilg",
                ".ind",
                ".chl",
                ".lof",
                ".lot",
            ]

        removed_count = 0

        # Remove files by extension
        for ext in extensions:
            for file in self.repo_root.glob(f"*{ext}"):
                try:
                    file.unlink()
                    removed_count += 1
                except Exception as e:
                    print_warning(f"Could not remove {file}: {e}")

        # Remove _minted directories
        for minted_dir in self.repo_root.glob("_minted-*"):
            if minted_dir.is_dir():
                try:
                    shutil.rmtree(minted_dir)
                    removed_count += 1
                except Exception as e:
                    print_warning(f"Could not remove {minted_dir}: {e}")

        if removed_count > 0:
            print_success(f"Removed {removed_count} build file(s)")
        else:
            print_info("No build files to clean")

        return True

    def get_current_branch(self) -> Optional[str]:
        """Get the current git branch name"""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.repo_root,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def is_clean_working_directory(self) -> bool:
        """Check if the working directory is clean (no uncommitted changes)"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.repo_root,
            )
            return len(result.stdout.strip()) == 0
        except subprocess.CalledProcessError:
            return False
