"""
Git hook templates and helpers for article-cli.
"""

from __future__ import annotations

import stat
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .zotero import print_info, print_success, print_warning

MANAGED_HOOK_START = "# >>> article-cli gitinfo2 hook >>>"
MANAGED_HOOK_END = "# <<< article-cli gitinfo2 hook <<<"

GITINFO2_POST_COMMIT_HOOK = """#!/bin/sh
# Copyright 2015 Brent Longborough
# Part of gitinfo2 package Version 2
# Release 2.0.7 2015-11-22
# Please read gitinfo2.pdf for licencing and other details
# -----------------------------------------------------
# Post-{commit,checkout,merge} hook for the gitinfo2 package
#
# Get the first tag found in the history from the current HEAD
FIRSTTAG=$(git describe --tags --always --dirty='-*' 2>/dev/null)
# Get the first tag in history that looks like a Release
RELTAG=$(git describe --tags --long --always --dirty='-*' --match 'v[0-9]*\\.[0-9]*\\.[0-9]*' 2>/dev/null)
GIT_HEAD_INFO=$(git rev-parse --git-path gitHeadInfo.gin)
mkdir -p "$(dirname "$GIT_HEAD_INFO")"
# Hoover up the metadata
git --no-pager log -1 --date=short --decorate=short \\
    --pretty=format:"\\usepackage[%
        shash={%h},
        lhash={%H},
        authname={%an},
        authemail={%ae},
        authsdate={%ad},
        authidate={%ai},
        authudate={%at},
        commname={%cn},
        commemail={%ce},
        commsdate={%cd},
        commidate={%ci},
        commudate={%ct},
        refnames={%d},
        firsttagdescribe={$FIRSTTAG},
        reltag={$RELTAG}
    ]{gitexinfo}" HEAD > "$GIT_HEAD_INFO"
"""


def ensure_gitinfo2_hook_source(repo_path: Path, force: bool = False) -> Path:
    """
    Create hooks/post-commit for gitinfo2 if needed.

    Args:
        repo_path: Repository root path
        force: Overwrite existing hook if True

    Returns:
        Path to hooks/post-commit
    """
    hooks_dir = repo_path / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    post_commit_path = hooks_dir / "post-commit"
    if post_commit_path.exists() and not force:
        print_info("hooks/post-commit already exists (use --force to overwrite)")
        return post_commit_path

    post_commit_path.write_text(GITINFO2_POST_COMMIT_HOOK)
    post_commit_path.chmod(
        post_commit_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    print_success(f"Created: {post_commit_path.relative_to(repo_path)}")
    print_info("Made post-commit hook executable")

    return post_commit_path


def install_managed_gitinfo2_hook(source_hook: Path, destination_hook: Path) -> str:
    """
    Install or update the article-cli managed gitinfo2 hook block.

    Existing shell hooks are preserved. If a hook already contains an article-cli
    managed block, only that block is replaced.

    Args:
        source_hook: Repository-owned hooks/post-commit source hook.
        destination_hook: Actual Git hook path resolved through git.

    Returns:
        One of "created", "updated", "merged", or "skipped".
    """
    source_content = source_hook.read_text()
    managed_block = _managed_hook_block(source_content)
    destination_hook.parent.mkdir(parents=True, exist_ok=True)

    if not destination_hook.exists():
        destination_hook.write_text(f"#!/bin/sh\n{managed_block}")
        _make_executable(destination_hook)
        return "created"

    existing_content = destination_hook.read_text()
    if MANAGED_HOOK_START in existing_content and MANAGED_HOOK_END in existing_content:
        updated_content = _replace_managed_block(existing_content, managed_block)
        status = "updated" if updated_content != existing_content else "skipped"
        destination_hook.write_text(updated_content)
        _make_executable(destination_hook)
        return status

    if not _is_shell_hook(existing_content):
        companion = destination_hook.with_name(f"{destination_hook.name}.article-cli")
        companion.write_text(f"#!/bin/sh\n{managed_block}")
        _make_executable(companion)
        print_warning(
            f"Existing non-shell hook preserved: {destination_hook.name}; "
            f"created managed companion hook: {companion.name}"
        )
        return "skipped"

    separator = "\n\n" if existing_content.strip() else ""
    destination_hook.write_text(
        f"{existing_content.rstrip()}{separator}{managed_block}"
    )
    _make_executable(destination_hook)
    return "merged"


def gitinfo2_metadata_summary(start_path: Path) -> Optional[str]:
    """
    Return a concise summary of the local gitinfo2 metadata, if available.

    Args:
        start_path: Repository root or a path inside the repository

    Returns:
        Human-readable summary, or None when gitHeadLocal.gin is unavailable.
    """
    repo_path = _find_git_root(start_path) or start_path.resolve()
    metadata_path = repo_path / "gitHeadLocal.gin"
    if not metadata_path.exists():
        return None

    content = metadata_path.read_text()
    parts = []
    for key, label in [
        ("shash", "commit"),
        ("firsttagdescribe", "version"),
        ("reltag", "release"),
    ]:
        value = _extract_gitinfo2_option(content, key)
        if value:
            parts.append(f"{label} {value}")

    return "; ".join(parts) if parts else None


def refresh_gitinfo2_metadata(start_path: Path) -> bool:
    """
    Refresh gitinfo2 metadata and the local copy used by \\usepackage[local]{gitinfo2}.

    Args:
        start_path: Repository root or a path inside the repository

    Returns:
        True when gitHeadLocal.gin was refreshed, False otherwise
    """
    repo_path = _find_git_root(start_path) or start_path.resolve()
    git_head_info = _git_path(repo_path, "gitHeadInfo.gin")
    if git_head_info is None:
        git_head_info = _legacy_git_file(repo_path, "gitHeadInfo.gin")
    if git_head_info is None:
        return False

    metadata = _render_gitinfo2_metadata(repo_path)
    if metadata is not None:
        git_head_info.parent.mkdir(parents=True, exist_ok=True)
        git_head_info.write_text(metadata)
        shutil.copyfile(git_head_info, repo_path / "gitHeadLocal.gin")
        return True

    hook_path = _find_gitinfo2_hook(repo_path)
    if hook_path is None:
        return False

    try:
        subprocess.run(
            ["sh", str(hook_path)],
            check=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to refresh gitinfo2 metadata: {e}")
        return False

    git_head_info = _git_path(repo_path, "gitHeadInfo.gin")
    if git_head_info is None:
        git_head_info = _legacy_git_file(repo_path, "gitHeadInfo.gin")
    if git_head_info is None:
        return False
    if not git_head_info.exists():
        return False

    shutil.copyfile(git_head_info, repo_path / "gitHeadLocal.gin")
    return True


def render_gitinfo2_metadata(repo_path: Path) -> Optional[str]:
    """Render gitinfo2 metadata without writing any files."""
    return _render_gitinfo2_metadata(repo_path)


def _render_gitinfo2_metadata(repo_path: Path) -> Optional[str]:
    """Render gitinfo2 metadata directly from git."""
    dirty_suffix = "-*" if _is_dirty_for_gitinfo2(repo_path) else ""
    firsttag = _git_output(repo_path, ["describe", "--tags", "--always"])
    reltag = _git_output(
        repo_path,
        [
            "describe",
            "--tags",
            "--long",
            "--always",
            "--match",
            "v[0-9]*.[0-9]*.[0-9]*",
        ],
    )
    if firsttag is None or reltag is None:
        return None

    firsttag = f"{firsttag}{dirty_suffix}"
    reltag = f"{reltag}{dirty_suffix}"
    pretty_format = (
        "\\usepackage[%\n"
        "        shash={%h},\n"
        "        lhash={%H},\n"
        "        authname={%an},\n"
        "        authemail={%ae},\n"
        "        authsdate={%ad},\n"
        "        authidate={%ai},\n"
        "        authudate={%at},\n"
        "        commname={%cn},\n"
        "        commemail={%ce},\n"
        "        commsdate={%cd},\n"
        "        commidate={%ci},\n"
        "        commudate={%ct},\n"
        "        refnames={%d},\n"
        f"        firsttagdescribe={{{firsttag}}},\n"
        f"        reltag={{{reltag}}}\n"
        "    ]{gitexinfo}"
    )
    return _git_output(
        repo_path,
        [
            "--no-pager",
            "log",
            "-1",
            "--date=short",
            "--decorate=short",
            f"--pretty=format:{pretty_format}",
            "HEAD",
        ],
    )


def _is_dirty_for_gitinfo2(repo_path: Path) -> bool:
    """Return True when tracked files other than gitHeadLocal.gin are dirty."""
    result = _run_git(
        repo_path,
        [
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            ".",
            ":(exclude)gitHeadLocal.gin",
        ],
    )
    return bool(result and result.stdout.strip())


def _find_git_root(start_path: Path) -> Optional[Path]:
    """Find the repository root with git, if available."""
    cwd = start_path if start_path.is_dir() else start_path.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=False,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None

    if result.returncode != 0:
        return None

    root = result.stdout.strip()
    return Path(root).resolve() if root else None


def _git_path(repo_path: Path, git_path: str) -> Optional[Path]:
    """Resolve a path inside Git's metadata directory."""
    result = _run_git(repo_path, ["rev-parse", "--git-path", git_path])
    if result is None or result.returncode != 0:
        return None

    path_text = result.stdout.strip()
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute():
        path = repo_path / path
    return path.resolve()


def _legacy_git_file(repo_path: Path, name: str) -> Optional[Path]:
    """Return .git/name for test fixtures and non-worktree repositories."""
    git_dir = repo_path / ".git"
    if git_dir.is_dir():
        return git_dir / name
    return None


def _git_output(repo_path: Path, args: List[str]) -> Optional[str]:
    """Run git and return stdout without the trailing newline."""
    result = _run_git(repo_path, args)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")


def _run_git(
    repo_path: Path, args: List[str]
) -> Optional[subprocess.CompletedProcess[str]]:
    """Run git and return the completed process."""
    try:
        return subprocess.run(
            ["git", *args],
            check=False,
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None


def _find_gitinfo2_hook(repo_path: Path) -> Optional[Path]:
    """Find the gitinfo2 post-commit hook generated or installed by article-cli."""
    git_hook_path = _git_path(repo_path, "hooks/post-commit")
    for hook_path in [
        repo_path / "hooks" / "post-commit",
        git_hook_path,
        _legacy_git_file(repo_path, "hooks/post-commit"),
    ]:
        if hook_path and hook_path.exists():
            return hook_path
    return None


def _managed_hook_block(source_content: str) -> str:
    """Build the managed hook block without a nested shebang."""
    source_without_shebang = _strip_shebang(source_content).rstrip()
    return f"{MANAGED_HOOK_START}\n{source_without_shebang}\n{MANAGED_HOOK_END}\n"


def _replace_managed_block(content: str, replacement_block: str) -> str:
    """Replace an existing managed hook block."""
    start = content.index(MANAGED_HOOK_START)
    end = content.index(MANAGED_HOOK_END, start) + len(MANAGED_HOOK_END)
    return f"{content[:start]}{replacement_block.rstrip()}{content[end:]}"


def _strip_shebang(content: str) -> str:
    """Remove the first shebang line from hook content."""
    if not content.startswith("#!"):
        return content
    _, separator, rest = content.partition("\n")
    return rest if separator else ""


def _is_shell_hook(content: str) -> bool:
    """Return True if the existing hook can safely receive shell code."""
    first_line = content.splitlines()[0] if content.splitlines() else ""
    if not first_line.startswith("#!"):
        return True
    return any(shell in first_line for shell in ["sh", "bash", "dash", "zsh"])


def _make_executable(path: Path) -> None:
    """Ensure all executable bits are present on a hook."""
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_gitinfo2_option(content: str, key: str) -> Optional[str]:
    """Extract a gitinfo2 option value from gitHeadLocal.gin content."""
    marker = f"{key}={{"
    start = content.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = content.find("}", start)
    if end == -1:
        return None
    return content[start:end]
