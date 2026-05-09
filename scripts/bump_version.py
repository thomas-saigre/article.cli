#!/usr/bin/env python3
"""
Synchronize article-cli release versions across package and documentation files.

Usage:
    uv run python scripts/bump_version.py 2.0.0
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover - dependency exists in dev env
    raise SystemExit("PyYAML is required; run through `uv run`.") from e


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Update known release version surfaces."""
    parser = argparse.ArgumentParser(
        description="Update article-cli version surfaces consistently."
    )
    parser.add_argument("version", help="Full release version, for example 2.0.0")
    args = parser.parse_args()

    version = normalize_version(args.version)
    antora_version = ".".join(version.split(".")[:2])

    update_regex(
        ROOT / "pyproject.toml",
        r'(?m)^version = "[^"]+"',
        f'version = "{version}"',
        count=1,
    )
    update_regex(
        ROOT / "src" / "article_cli" / "__init__.py",
        r'__version__ = "[^"]+"',
        f'__version__ = "{version}"',
    )
    update_regex(
        ROOT / "src" / "article_cli" / "repository_setup.py",
        r'ARTICLE_CLI_MIN_VERSION = "[^"]+"',
        f'ARTICLE_CLI_MIN_VERSION = "{version}"',
    )
    update_antora(ROOT / "docs" / "antora.yml", version, antora_version)
    update_json_version(ROOT / "package.json", version)
    update_package_lock(ROOT / "package-lock.json", version)
    update_uv_lock(ROOT / "uv.lock", version)

    print(f"Updated article-cli release version to {version}")
    print(f"Updated Antora component version to {antora_version}")
    return 0


def normalize_version(raw_version: str) -> str:
    """Return a strict X.Y.Z version string."""
    version = raw_version.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        raise SystemExit("Expected a version like 2.0.0 or v2.0.0")
    return version


def update_regex(path: Path, pattern: str, replacement: str, count: int = 0) -> None:
    """Update a text file with a regex replacement."""
    text = path.read_text(encoding="utf-8")
    updated, replacements = re.subn(pattern, replacement, text, count=count)
    if replacements == 0:
        raise SystemExit(f"No version field matched in {path}")
    path.write_text(updated, encoding="utf-8")


def update_antora(path: Path, version: str, antora_version: str) -> None:
    """Update Antora component version and article-cli version attribute."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["version"] = antora_version
    data.setdefault("asciidoc", {}).setdefault("attributes", {})[
        "article-cli-version"
    ] = version

    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^version: '[^']+'", f"version: '{antora_version}'", text)
    text = re.sub(
        r"(?m)^    article-cli-version: '[^']+'",
        f"    article-cli-version: '{version}'",
        text,
    )
    path.write_text(text, encoding="utf-8")


def update_json_version(path: Path, version: str) -> None:
    """Update the root version in a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_package_lock(path: Path, version: str) -> None:
    """Update package-lock root version entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    if "" in data.get("packages", {}):
        data["packages"][""]["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_uv_lock(path: Path, version: str) -> None:
    """Update the editable article-cli package version in uv.lock."""
    text = path.read_text(encoding="utf-8")
    pattern = r'(\[\[package\]\]\nname = "article-cli"\nversion = ")[^"]+(")'
    updated, replacements = re.subn(
        pattern,
        rf"\g<1>{version}\2",
        text,
        count=1,
    )
    if replacements == 0:
        raise SystemExit(f"No article-cli package entry matched in {path}")
    path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
