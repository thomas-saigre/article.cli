"""
Tests for generated GitHub Actions workflow policy.
"""

from pathlib import Path

import yaml

from article_cli.repository_setup import RepositorySetup

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


def _init_project(tmp_path: Path, **kwargs: object) -> tuple[str, dict]:
    """Initialize a project and return workflow text plus parsed pyproject."""
    setup = RepositorySetup(tmp_path)
    assert setup.init_repository(
        title="Workflow Test",
        authors=["A. Author"],
        group_id="12345",
        **kwargs,
    )
    workflow_text = (tmp_path / ".github" / "workflows" / "latex.yml").read_text()
    yaml.safe_load(workflow_text)
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    return workflow_text, pyproject


def test_default_workflow_is_portable_and_policy_driven(tmp_path):
    """Default generated CI should use public runners and no Zotero secret."""
    workflow_text, pyproject = _init_project(tmp_path, project_type="article")

    workflow = yaml.safe_load(workflow_text)
    workflow_config = pyproject["tool"]["article-cli"]["workflow"]

    assert workflow["jobs"]["workflow-setup"]["runs-on"] == "ubuntu-24.04"
    assert workflow_config["runner_policy"] == "github"
    assert workflow_config["bibliography"] == "off"
    assert workflow_config["release"] == "github"
    assert "/orgs/feelpp/actions/runners" not in workflow_text
    assert "TOKEN_RUNNER" not in workflow_text
    assert "self-texlive" not in workflow_text
    assert "ZOTERO_API_KEY" not in workflow_text
    assert "article-cli doctor --json" in workflow_text
    assert "article-cli-doctor.json" in workflow_text


def test_workflow_can_opt_into_self_hosted_runner_and_bibliography_check(tmp_path):
    """Self-hosted discovery and Zotero checks should be explicit opt-ins."""
    workflow_text, pyproject = _init_project(
        tmp_path,
        project_type="presentation",
        ci_runner_policy="self-hosted-auto",
        ci_self_hosted_org="cemosis",
        ci_self_hosted_label="self-texlive",
        ci_bibliography="check",
        ci_artifact_includes=["./results/**"],
    )

    workflow_config = pyproject["tool"]["article-cli"]["workflow"]

    assert workflow_config["runner_policy"] == "self-hosted-auto"
    assert workflow_config["self_hosted_org"] == "cemosis"
    assert workflow_config["bibliography"] == "check"
    assert workflow_config["artifact_includes"] == ["./results/**"]
    assert "/orgs/cemosis/actions/runners" in workflow_text
    assert "/orgs/feelpp/actions/runners" not in workflow_text
    assert "TOKEN_RUNNER" in workflow_text
    assert "article-cli bib update --check" in workflow_text
    assert "./results/**" in workflow_text


def test_workflow_required_bibliography_fails_without_secret(tmp_path):
    """The required bibliography policy should fail when the secret is absent."""
    workflow_text, pyproject = _init_project(
        tmp_path,
        project_type="article",
        ci_bibliography="required",
    )

    workflow_config = pyproject["tool"]["article-cli"]["workflow"]

    assert workflow_config["bibliography"] == "required"
    assert "ZOTERO_API_KEY is required" in workflow_text
    assert "exit 1" in workflow_text
    assert "article-cli bib update" in workflow_text


def test_workflow_release_job_can_be_disabled_for_typst(tmp_path):
    """Typst workflows should parse and support release job opt-out."""
    workflow_text, pyproject = _init_project(
        tmp_path,
        project_type="typst-article",
        ci_release_policy="off",
    )

    workflow = yaml.safe_load(workflow_text)
    workflow_config = pyproject["tool"]["article-cli"]["workflow"]

    assert workflow_config["release"] == "off"
    assert "release" not in workflow["jobs"]
    assert "check" in workflow["jobs"]
    assert "typst-community/setup-typst@v4" in workflow_text
    assert "runs-on: ubuntu-24.04" in workflow_text
