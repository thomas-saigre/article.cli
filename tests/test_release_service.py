"""
Tests for transactional release helpers.
"""

from pathlib import Path

from article_cli.config import Config
from article_cli.services.release import ReleaseOptions, ReleaseService, validate_tag


class FakeGitManager:
    """Capture release git operations without touching git."""

    instances = []

    def __init__(self, repo_root=None):
        self.repo_root = Path(repo_root or ".").resolve()
        self.calls = []
        self.existing_tags = set()
        self.dirty = []
        self.instances.append(self)

    def tag_exists(self, tag):
        self.calls.append(("tag_exists", tag))
        return tag in self.existing_tags

    def dirty_files(self, ignore_gitinfo=True):
        self.calls.append(("dirty_files", ignore_gitinfo))
        return list(self.dirty)

    def create_tag(self, tag, force=False):
        self.calls.append(("create_tag", tag, force))
        return True

    def list_releases(self, count=5):
        self.calls.append(("list_releases", count))
        return True

    def delete_release(self, version, remote=False):
        self.calls.append(("delete_release", version, remote))
        return True


def test_paper_tag_policy_accepts_short_paper_tags():
    """Paper releases may use v1, v1.0, or full SemVer tags."""
    assert validate_tag("v1", "paper")
    assert validate_tag("v1.0", "paper")
    assert validate_tag("v1.0.0", "paper")
    assert validate_tag("v1.0.0-rc.1", "paper")


def test_semver_tag_policy_remains_strict():
    """Strict SemVer still rejects short paper tags."""
    assert not validate_tag("v1", "semver")
    assert validate_tag("v1.0.0", "semver")


def test_release_dry_run_does_not_create_tag(tmp_path):
    """A release dry run performs preflight but does not mutate tags."""
    service = ReleaseService(
        Config(quiet=True),
        repo_root=tmp_path,
        manager_cls=FakeGitManager,
    )

    assert service.release(ReleaseOptions(tag="v1", dry_run=True)) is True

    assert FakeGitManager.instances[-1].calls == [
        ("tag_exists", "v1"),
        ("dirty_files", True),
    ]


def test_release_blocks_dirty_tree_without_explicit_override(tmp_path):
    """Dirty files stop a release unless allow_dirty is explicitly enabled."""
    service = ReleaseService(
        Config(quiet=True),
        repo_root=tmp_path,
        manager_cls=FakeGitManager,
    )
    FakeGitManager.instances[-1].dirty = ["M paper.tex"]

    assert service.release(ReleaseOptions(tag="v1")) is False

    assert ("create_tag", "v1", False) not in FakeGitManager.instances[-1].calls


def test_release_prints_rollback_guidance_after_post_tag_failure(
    tmp_path, monkeypatch, capsys
):
    """A failure after tag creation should tell the user how to roll it back."""
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\n")
    monkeypatch.setattr(
        "article_cli.services.release.refresh_gitinfo2_metadata",
        lambda repo_root: True,
    )
    monkeypatch.setattr(
        "article_cli.services.release.gitinfo2_metadata_summary",
        lambda repo_root: "release v1",
    )
    service = ReleaseService(
        Config(quiet=True),
        repo_root=tmp_path,
        manager_cls=FakeGitManager,
    )

    assert (
        service.release(
            ReleaseOptions(
                tag="v1",
                compile_pdf=False,
                check_pdf=True,
                checksum=False,
            )
        )
        is False
    )

    assert ("create_tag", "v1", False) in FakeGitManager.instances[-1].calls
    assert "Rollback local tag with: git tag -d v1" in capsys.readouterr().out
