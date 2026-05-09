"""
Tests for shared project context resolution.
"""

import subprocess

from article_cli.config import Config
from article_cli.project_context import ProjectContext


def test_project_context_resolves_configured_document_policy(tmp_path):
    """Configured document, engine, shell escape, and output are resolved once."""
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

    context = ProjectContext.resolve(Config(config_file, quiet=True), cwd=tmp_path)

    assert context.document == (tmp_path / "paper.tex").resolve()
    assert context.document_name == "paper.tex"
    assert context.engine == "xelatex"
    assert context.output_dir_name == "build"
    assert context.shell_escape is True


def test_project_context_detects_typst_documents(tmp_path):
    """A detected Typst source selects the Typst engine."""
    (tmp_path / "main.typ").write_text("= Title\n")

    context = ProjectContext.resolve(Config(quiet=True), cwd=tmp_path)

    assert context.document == (tmp_path / "main.typ").resolve()
    assert context.document_name == "main.typ"
    assert context.engine == "typst"


def test_project_context_resolves_cli_document_relative_to_cwd(tmp_path):
    """Explicit CLI document paths are relative to the user's current directory."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subdir = tmp_path / "sections"
    subdir.mkdir()
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\n")
    (subdir / "paper.tex").write_text("\\documentclass{article}\n")

    context = ProjectContext.resolve(
        Config(quiet=True),
        cwd=subdir,
        document="paper.tex",
    )

    assert context.project_root == tmp_path.resolve()
    assert context.document == (subdir / "paper.tex").resolve()
    assert context.document_name == "paper.tex"
