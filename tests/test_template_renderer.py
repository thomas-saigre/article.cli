from importlib.resources import files

import pytest
from jinja2 import UndefinedError

from article_cli.repository_setup import RepositorySetup
from article_cli.template_renderer import TemplateRenderer


def test_template_package_resources_are_available():
    """Template files should be importable package resources."""
    template_root = files("article_cli.templates")

    assert template_root.joinpath("article/main.tex.j2").is_file()
    assert template_root.joinpath("article/main.typ.j2").is_file()
    assert template_root.joinpath("article/lncs.tex.j2").is_file()
    assert template_root.joinpath("github/latex.yml.j2").is_file()


def test_template_renderer_uses_strict_undefined():
    """Missing template context should fail loudly."""
    renderer = TemplateRenderer()

    with pytest.raises(UndefinedError):
        renderer.render("article/main.tex.j2", {"title": "Missing Authors"})


def test_template_renderer_write_statuses(tmp_path):
    """Template writes should report created, skipped, and overwritten files."""
    renderer = TemplateRenderer()
    target = tmp_path / "main.tex"
    context = {"title": "Test", "authors_latex": "Author"}

    first = renderer.write("article/main.tex.j2", target, context)
    second = renderer.write("article/main.tex.j2", target, context)
    third = renderer.write("article/main.tex.j2", target, context, force=True)

    assert first.status == "created"
    assert second.status == "skipped"
    assert third.status == "overwritten"


def test_article_template_matches_golden_file(tmp_path):
    """Representative article template output should remain stable."""
    setup = RepositorySetup(tmp_path)
    rendered = setup._get_article_template("Golden Article", ["Alice", "Bob"])
    golden = (files("tests.golden").joinpath("article_main.tex")).read_text()

    assert rendered == golden
