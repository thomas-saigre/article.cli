"""
Version consistency tests for release surfaces.
"""

import json
from pathlib import Path

import yaml

import article_cli
from article_cli.repository_setup import ARTICLE_CLI_MIN_VERSION

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_consistent():
    """Package, generated templates, docs, and docs package use one version."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    package_json = json.loads((ROOT / "package.json").read_text())
    package_lock = json.loads((ROOT / "package-lock.json").read_text())
    antora = yaml.safe_load((ROOT / "docs" / "antora.yml").read_text())
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text())

    version = pyproject["project"]["version"]
    antora_version = ".".join(version.split(".")[:2])

    assert article_cli.__version__ == version
    assert ARTICLE_CLI_MIN_VERSION == version
    assert package_json["version"] == version
    assert package_lock["version"] == version
    assert package_lock["packages"][""]["version"] == version
    assert antora["version"] == antora_version
    assert antora["asciidoc"]["attributes"]["article-cli-version"] == version
    article_package = next(
        package for package in uv_lock["package"] if package["name"] == "article-cli"
    )
    assert article_package["version"] == version
