"""
Tests for article-cli service boundaries.
"""

from pathlib import Path
from types import SimpleNamespace

from article_cli.config import Config
from article_cli.services.bibliography import (
    BibliographyService,
    BibliographyUpdateOptions,
)
from article_cli.services.compiler import CompileOptions, CompilerService
from article_cli.services.git import GitService
from article_cli.services.release import ReleaseService
from article_cli.services.workflow import WorkflowService


class FakeLatexCompiler:
    """Capture LaTeX compiler calls."""

    instances = []

    def __init__(self, config):
        self.config = config
        self.calls = []
        self.instances.append(self)

    def compile(self, **kwargs):
        self.calls.append(kwargs)
        return True


class FakeTypstCompiler:
    """Capture Typst compiler calls."""

    instances = []

    def __init__(self, config):
        self.config = config
        self.calls = []
        self.instances.append(self)

    def compile(self, **kwargs):
        self.calls.append(kwargs)
        return True


class FakeGitManager:
    """Capture git manager calls."""

    instances = []

    def __init__(self, repo_root=None):
        self.repo_root = Path(repo_root or ".").resolve()
        self.calls = []
        self.instances.append(self)

    def clean_latex_files(self, extensions):
        self.calls.append(("clean_latex_files", extensions))
        return True

    def setup_hooks(self, dry_run=False):
        self.calls.append(("setup_hooks", dry_run))
        return True

    def create_release(self, version, auto_push=False, dry_run=False):
        self.calls.append(("create_release", version, auto_push, dry_run))
        return True

    def tag_exists(self, tag):
        self.calls.append(("tag_exists", tag))
        return False

    def dirty_files(self, ignore_gitinfo=True):
        self.calls.append(("dirty_files", ignore_gitinfo))
        return []

    def create_tag(self, tag, force=False):
        self.calls.append(("create_tag", tag, force))
        return True

    def push_tag(self, tag):
        self.calls.append(("push_tag", tag))
        return True

    def list_releases(self, count=5):
        self.calls.append(("list_releases", count))
        return True

    def delete_release(self, version, remote=False):
        self.calls.append(("delete_release", version, remote))
        return True


class FakeRepositorySetup:
    """Capture repository setup calls."""

    instances = []

    def __init__(self, repo_path=None):
        self.repo_path = repo_path
        self.calls = []
        self.instances.append(self)

    def init_repository(self, **kwargs):
        self.calls.append(kwargs)
        return True


class FailingUpdater:
    """Updater that should not be instantiated during dry runs."""

    def __init__(self, **kwargs):
        raise AssertionError(
            "dry-run bibliography update should not instantiate updater"
        )


def reset_fakes():
    """Reset fake class state between tests."""
    FakeLatexCompiler.instances = []
    FakeTypstCompiler.instances = []
    FakeGitManager.instances = []
    FakeRepositorySetup.instances = []


def test_compiler_service_dispatches_latex_with_shared_policy(tmp_path):
    """Compiler service resolves project policy before calling the LaTeX compiler."""
    reset_fakes()
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\n")
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(
        """
[tool.article-cli.documents]
main = "paper.tex"

[tool.article-cli.latex]
engine = "xelatex"
shell_escape = true

[tool.article-cli.workflow]
output_dir = "build"
"""
    )

    service = CompilerService(
        Config(config_file, quiet=True),
        cwd=tmp_path,
        latex_compiler_cls=FakeLatexCompiler,
        git_manager_cls=FakeGitManager,
    )

    assert service.compile(CompileOptions(clean_first=True, clean_after=True)) is True
    assert FakeLatexCompiler.instances[0].calls == [
        {
            "tex_file": "paper.tex",
            "engine": "xelatex",
            "shell_escape": True,
            "output_dir": "build",
            "watch": False,
        }
    ]
    assert len(FakeGitManager.instances) == 2
    assert all(
        instance.calls[0][0] == "clean_latex_files"
        for instance in FakeGitManager.instances
    )


def test_compiler_service_dispatches_typst(tmp_path):
    """Compiler service dispatches Typst documents to the Typst compiler."""
    reset_fakes()
    (tmp_path / "main.typ").write_text("= Title\n")

    service = CompilerService(
        Config(quiet=True),
        cwd=tmp_path,
        typst_compiler_cls=FakeTypstCompiler,
    )

    assert service.compile(CompileOptions(font_paths=["fonts"], watch=True)) is True
    assert FakeTypstCompiler.instances[0].calls == [
        {
            "typ_file": "main.typ",
            "output_dir": None,
            "font_paths": ["fonts"],
            "watch": True,
        }
    ]


def test_bibliography_service_dry_run_does_not_instantiate_updater(tmp_path):
    """Bibliography dry runs validate configuration without touching Zotero."""
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(
        """
[tool.article-cli.zotero]
api_key = "test-key"
group_id = "4709047"
output_file = "references.bib"
"""
    )
    args = SimpleNamespace(api_key=None, user_id=None, group_id=None, output=None)

    service = BibliographyService(
        Config(config_file, quiet=True),
        updater_cls=FailingUpdater,
    )

    assert service.update(args, BibliographyUpdateOptions(dry_run=True)) is True


def test_git_release_and_workflow_services_delegate_to_implementation():
    """Thin services preserve existing implementation contracts."""
    reset_fakes()

    git_service = GitService(manager_cls=FakeGitManager)
    release_service = ReleaseService(manager_cls=FakeGitManager)
    workflow_service = WorkflowService(setup_cls=FakeRepositorySetup)

    assert git_service.setup_hooks(dry_run=True) is True
    assert release_service.create("v1.0.0", auto_push=True, dry_run=True) is True
    assert release_service.list(count=3) is True
    assert release_service.delete("v1.0.0", remote=True) is True
    assert (
        workflow_service.initialize_repository(
            title="Title",
            authors=["A. Author"],
            project_type="typst-article",
            additional_documents=["supplement.tex"],
            output_dir="build",
        )
        is True
    )

    assert FakeGitManager.instances[0].calls == [("setup_hooks", True)]
    assert FakeGitManager.instances[1].calls == [
        ("tag_exists", "v1.0.0"),
        ("dirty_files", True),
        ("list_releases", 3),
        ("delete_release", "v1.0.0", True),
    ]
    assert FakeRepositorySetup.instances[0].calls[0]["project_type"] == "typst-article"
    assert FakeRepositorySetup.instances[0].calls[0]["output_dir"] == "build"
