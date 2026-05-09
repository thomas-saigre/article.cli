"""
Tests for article-cli doctor diagnostics.
"""

import json
import subprocess
from pathlib import Path

from article_cli.cli import main
from article_cli.config import Config
from article_cli.doctor import DoctorService
from article_cli.git_manager import GitManager


def init_git_repository(path: Path) -> None:
    """Create a real git repository for doctor tests."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
    )


def write_ready_paper(path: Path) -> None:
    """Create a minimal configured paper repository."""
    (path / "main.tex").write_text("\\documentclass{article}\n")
    (path / "references.bib").write_text("@misc{test,title={Test}}\n")
    (path / "pyproject.toml").write_text(
        """
[tool.article-cli.project]
type = "article"

[tool.article-cli.documents]
main = "main.tex"

[tool.article-cli.latex]
engine = "pdflatex"
build_dir = "."

[tool.article-cli.zotero]
api_key = "test-key"
group_id = "4709047"
output_file = "references.bib"
"""
    )
    workflow_dir = path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "latex.yml").write_text(
        """
name: build
on:
  push:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: astral-sh/setup-uv@v8.1.0
      - run: article-cli compile main.tex
"""
    )


def test_doctor_reports_missing_git_repository_without_modifying_files(
    tmp_path, monkeypatch
):
    """Doctor should diagnose a missing Git repository without creating files."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.tex").write_text("\\documentclass{article}\n")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    report = DoctorService(Config(quiet=True), cwd=tmp_path).run()

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert report.ok is False
    assert report.error_count >= 1
    assert any(
        check.category == "git"
        and check.name == "repository"
        and check.status == "error"
        for check in report.checks
    )
    assert before == after
    assert not (tmp_path / "hooks").exists()
    assert not (tmp_path / "gitHeadLocal.gin").exists()


def test_doctor_ready_repository_has_no_blocking_errors(tmp_path, monkeypatch):
    """A configured repository with hooks and tools should pass doctor."""
    monkeypatch.chdir(tmp_path)
    init_git_repository(tmp_path)
    write_ready_paper(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    assert GitManager(tmp_path).setup_hooks() is True

    def fake_which(command):
        return f"/usr/bin/{command}"

    monkeypatch.setattr("article_cli.doctor.shutil.which", fake_which)
    report = DoctorService(Config(quiet=True), cwd=tmp_path).run()

    assert report.ok is True
    assert report.error_count == 0
    assert report.context["main_document"].endswith("main.tex")
    assert report.context["engine"] == "pdflatex"
    assert any(
        check.category == "workflow"
        and check.name == "yaml-parse"
        and check.status == "ok"
        for check in report.checks
    )


def test_doctor_json_output_is_machine_readable(tmp_path, monkeypatch, capsys):
    """doctor --json should not be polluted by config loading messages."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.article-cli.project]
type = "article"
"""
    )

    exit_code = main(["doctor", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["summary"]["errors"] >= 1
    assert "Loaded configuration" not in captured.out


def test_doctor_reports_existing_release_tag(tmp_path, monkeypatch):
    """A requested release tag that already exists is a blocking issue."""
    monkeypatch.chdir(tmp_path)
    init_git_repository(tmp_path)
    write_ready_paper(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "tag", "v1.0.0"], cwd=tmp_path, check=True)

    def fake_which(command):
        return f"/usr/bin/{command}"

    monkeypatch.setattr("article_cli.doctor.shutil.which", fake_which)
    report = DoctorService(Config(quiet=True), cwd=tmp_path).run(tag="v1.0.0")

    assert report.ok is False
    assert any(
        check.category == "release" and check.name == "tag" and check.status == "error"
        for check in report.checks
    )
