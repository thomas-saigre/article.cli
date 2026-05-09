"""
Tests for article-cli command handlers.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import article_cli.zotero as zotero_module
from article_cli.cli import (
    create_parser,
    handle_compile_command,
    handle_update_bibtex_command,
)
from article_cli.commands import release as release_command
from article_cli.commands import setup as setup_command
from article_cli.commands import version as version_command
from article_cli.config import Config
from article_cli.zotero import ZoteroBibTexUpdater

ZOTERO_ENV_VARS = ("ZOTERO_API_KEY", "ZOTERO_USER_ID", "ZOTERO_GROUP_ID")


def clear_zotero_env(monkeypatch):
    """Keep CLI tests independent from developer Zotero credentials."""
    for var in ZOTERO_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_compile_uses_project_config_when_cli_args_absent(tmp_path, monkeypatch):
    """Compile should honor configured document, engine, shell escape, and output."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\n")
    (tmp_path / "pyproject.toml").write_text(
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
    args = SimpleNamespace(
        tex_file=None,
        engine=None,
        shell_escape=None,
        output_dir=None,
        clean_first=False,
        clean_after=False,
        watch=False,
        font_paths=None,
    )
    config = Config()

    with patch(
        "article_cli.latex_compiler.LaTeXCompiler.compile", return_value=True
    ) as compile_mock:
        result = handle_compile_command(args, config)

    assert result == 0
    compile_mock.assert_called_once_with(
        tex_file="paper.tex",
        engine="xelatex",
        shell_escape=True,
        output_dir="build",
        watch=False,
    )


def test_compile_cli_args_override_project_config(tmp_path, monkeypatch):
    """Explicit CLI compile arguments should override project configuration."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\n")
    (tmp_path / "pyproject.toml").write_text(
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
    args = SimpleNamespace(
        tex_file="paper.tex",
        engine="pdflatex",
        shell_escape=False,
        output_dir="out",
        clean_first=False,
        clean_after=False,
        watch=False,
        font_paths=None,
    )
    config = Config()

    with patch(
        "article_cli.latex_compiler.LaTeXCompiler.compile", return_value=True
    ) as compile_mock:
        result = handle_compile_command(args, config)

    assert result == 0
    compile_mock.assert_called_once_with(
        tex_file="paper.tex",
        engine="pdflatex",
        shell_escape=False,
        output_dir="out",
        watch=False,
    )


def test_update_bibtex_uses_configured_output_file(tmp_path, monkeypatch):
    """update-bibtex should not mask configured output_file with parser defaults."""
    clear_zotero_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.article-cli.zotero]
api_key = "test-key"
group_id = "4709047"
output_file = "zotero/references.bib"
"""
    )
    args = SimpleNamespace(
        api_key=None,
        user_id=None,
        group_id=None,
        collection=None,
        output=None,
        local_file=None,
        merged_output=None,
        include_local=False,
        no_backup=True,
        check=False,
        check_citations=False,
        timestamp=False,
    )
    config = Config()

    with patch("article_cli.commands.bibtex.ZoteroBibTexUpdater") as updater_cls:
        updater_cls.return_value.update.return_value = True
        result = handle_update_bibtex_command(args, config)

    assert result == 0
    updater_cls.assert_called_once_with(
        api_key="test-key",
        user_id=None,
        group_id="4709047",
        collection_id=None,
        output_file="zotero/references.bib",
    )
    updater_cls.return_value.update.assert_called_once_with(
        backup=False,
        check=False,
        include_local=False,
        local_file="local_references.bib",
        merged_output_file=None,
        check_citations=False,
        citation_sources=[],
        timestamp=False,
    )


def test_update_bibtex_cli_output_overrides_config(tmp_path, monkeypatch):
    """Explicit --output should override configured output_file."""
    clear_zotero_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.article-cli.zotero]
api_key = "test-key"
group_id = "4709047"
output_file = "zotero/references.bib"
"""
    )
    args = SimpleNamespace(
        api_key=None,
        user_id=None,
        group_id=None,
        collection=None,
        output="manual.bib",
        local_file=None,
        merged_output=None,
        include_local=False,
        no_backup=True,
        check=False,
        check_citations=False,
        timestamp=False,
    )
    config = Config()

    with patch("article_cli.commands.bibtex.ZoteroBibTexUpdater") as updater_cls:
        updater_cls.return_value.update.return_value = True
        result = handle_update_bibtex_command(args, config)

    assert result == 0
    assert updater_cls.call_args.kwargs["output_file"] == "manual.bib"


def test_bib_update_dry_run_does_not_contact_zotero(tmp_path, monkeypatch):
    """bib update --dry-run should validate config without writing references."""
    clear_zotero_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.article-cli.zotero]
api_key = "test-key"
group_id = "4709047"
output_file = "references.bib"
"""
    )
    args = SimpleNamespace(
        api_key=None,
        user_id=None,
        group_id=None,
        collection=None,
        output=None,
        local_file=None,
        merged_output=None,
        include_local=False,
        no_backup=False,
        dry_run=True,
        check=False,
        check_citations=False,
        timestamp=False,
    )
    config = Config(quiet=True)

    with patch("article_cli.commands.bibtex.ZoteroBibTexUpdater") as updater_cls:
        result = handle_update_bibtex_command(args, config)

    assert result == 0
    updater_cls.assert_not_called()
    assert not (tmp_path / "references.bib").exists()


def test_parser_config_backed_defaults_are_none():
    """Parser defaults must leave project config visible to command handlers."""
    parser = create_parser()

    compile_args = parser.parse_args(["compile"])
    bib_args = parser.parse_args(["update-bibtex"])
    canonical_bib_args = parser.parse_args(["bib", "update"])
    doctor_args = parser.parse_args(["doctor"])
    setup_args = parser.parse_args(["setup", "--dry-run"])
    version_args = parser.parse_args(["version", "--dry-run"])
    release_args = parser.parse_args(["release", "v1.0.0", "--dry-run"])
    create_args = parser.parse_args(["create", "v1.0.0", "--dry-run"])

    assert compile_args.engine is None
    assert compile_args.shell_escape is None
    assert compile_args.output_dir is None
    assert bib_args.output is None
    assert canonical_bib_args.output is None
    assert doctor_args.engine is None
    assert doctor_args.output_dir is None
    assert setup_args.dry_run is True
    assert version_args.dry_run is True
    assert release_args.dry_run is True
    assert create_args.dry_run is True


def test_setup_dry_run_is_forwarded_to_git_manager():
    """setup --dry-run should call the setup service in dry-run mode."""
    args = SimpleNamespace(dry_run=True)

    with patch("article_cli.commands.setup.GitManager") as manager_cls:
        manager_cls.return_value.setup_hooks.return_value = True
        result = setup_command.run(args, Config(quiet=True))

    assert result == 0
    manager_cls.return_value.setup_hooks.assert_called_once_with(dry_run=True)


def test_version_dry_run_is_forwarded_to_git_manager():
    """version --dry-run should not refresh files."""
    args = SimpleNamespace(dry_run=True)

    with patch("article_cli.commands.version.GitManager") as manager_cls:
        manager_cls.return_value.refresh_version_metadata.return_value = True
        result = version_command.run(args, Config(quiet=True))

    assert result == 0
    manager_cls.return_value.refresh_version_metadata.assert_called_once_with(True)


def test_release_dry_run_is_forwarded_to_git_manager():
    """release --dry-run should validate without creating a tag."""
    args = SimpleNamespace(version="v1.0.0", push=False, dry_run=True)

    with patch("article_cli.commands.release.GitManager") as manager_cls:
        manager_cls.return_value.create_release.return_value = True
        result = release_command.run_release(args, Config(quiet=True))

    assert result == 0
    manager_cls.return_value.create_release.assert_called_once_with(
        "v1.0.0", auto_push=False, dry_run=True
    )


def test_zotero_missing_requests_fails_at_command_time(monkeypatch):
    """Missing optional HTTP support should not terminate the process on import."""
    monkeypatch.setattr(zotero_module, "requests", None)

    with pytest.raises(RuntimeError, match="requests"):
        ZoteroBibTexUpdater(api_key="test-key", group_id="4709047")
