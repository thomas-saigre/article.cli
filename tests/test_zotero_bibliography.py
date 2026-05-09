"""
Tests for deterministic Zotero BibTeX synchronization.
"""

from pathlib import Path

from article_cli.zotero import (
    ZoteroBibTexUpdater,
    extract_bibtex_keys,
    extract_citation_keys,
)


class FakeResponse:
    """Minimal response object for Zotero updater tests."""

    def __init__(self, text: str, total: int = 1, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.reason = "OK" if status_code < 400 else "temporary failure"
        self.headers = {"Total-Results": str(total)}

    def raise_for_status(self):
        """Raise a requests-compatible error for failed responses."""
        if self.status_code < 400:
            return

        import requests

        error = requests.exceptions.HTTPError(self.reason)
        error.response = self
        raise error


class FakeSession:
    """Return queued fake responses and record requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=30):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


def make_updater(tmp_path: Path, responses) -> ZoteroBibTexUpdater:
    """Create an updater with a fake session."""
    updater = ZoteroBibTexUpdater(
        api_key="test-key",
        user_id="1234",
        output_file=str(tmp_path / "references.bib"),
    )
    updater.session = FakeSession(responses)
    updater.retry_backoff = 0
    return updater


def test_update_writes_deterministic_bibtex_and_skips_unchanged_file(tmp_path):
    """Default output has no timestamp and does not rewrite unchanged content."""
    bibtex = """
@misc{zeta,
  title = {Zeta}
}

@article{alpha,
  title = {Alpha}
}
"""
    updater = make_updater(tmp_path, [FakeResponse(bibtex, total=2)])

    assert updater.update(backup=True) is True

    output = tmp_path / "references.bib"
    content = output.read_text()
    assert "% Generated:" not in content
    assert "% Total entries: 2" in content
    assert content.index("@article{alpha") < content.index("@misc{zeta")

    updater.session = FakeSession([FakeResponse(bibtex, total=2)])
    assert updater.update(backup=True) is True
    assert not (tmp_path / "references.bib.backup").exists()


def test_update_check_reports_stale_bibliography_without_writing(tmp_path):
    """Check mode reports stale content and leaves the file untouched."""
    output = tmp_path / "references.bib"
    output.write_text("stale content\n")
    updater = make_updater(
        tmp_path,
        [FakeResponse("@misc{fresh,\n  title = {Fresh}\n}\n", total=1)],
    )

    assert updater.update(check=True, backup=True) is False
    assert output.read_text() == "stale content\n"
    assert not (tmp_path / "references.bib.backup").exists()


def test_collection_url_supports_zotero_collections_and_subcollections(tmp_path):
    """Collection keys are encoded in the Zotero API URL."""
    updater = ZoteroBibTexUpdater(
        api_key="test-key",
        group_id="4709047",
        collection_id="ABC123",
        output_file=str(tmp_path / "references.bib"),
    )

    assert updater._build_url().endswith("/groups/4709047/collections/ABC123/items")


def test_include_local_can_write_separate_merged_output(tmp_path):
    """Local manual entries can be merged without changing Zotero-only output."""
    local = tmp_path / "local_references.bib"
    local.write_text("@misc{local,\n  title = {Local}\n}\n")
    merged = tmp_path / "references.all.bib"
    updater = make_updater(
        tmp_path,
        [FakeResponse("@misc{zotero,\n  title = {Zotero}\n}\n", total=1)],
    )

    assert (
        updater.update(
            include_local=True,
            local_file=str(local),
            merged_output_file=str(merged),
            backup=False,
        )
        is True
    )

    zotero_only = (tmp_path / "references.bib").read_text()
    merged_content = merged.read_text()
    assert "zotero" in zotero_only
    assert "local" not in zotero_only
    assert "zotero" in merged_content
    assert "local" in merged_content
    assert f"% Local entries: {local}" in merged_content


def test_citation_completeness_detects_missing_keys(tmp_path):
    """Citation checks report source citations missing from BibTeX."""
    source = tmp_path / "paper.tex"
    source.write_text(r"\cite{known,missing}")
    updater = make_updater(
        tmp_path,
        [FakeResponse("@misc{known,\n  title = {Known}\n}\n", total=1)],
    )

    assert updater.update(check_citations=True, citation_sources=[source]) is False
    assert extract_citation_keys(source) == {"known", "missing"}
    assert extract_bibtex_keys((tmp_path / "references.bib").read_text()) == {"known"}


def test_transient_zotero_failures_are_retried(tmp_path, monkeypatch):
    """Transient HTTP failures are retried before the update fails."""
    monkeypatch.setattr("article_cli.zotero.time.sleep", lambda _: None)
    updater = make_updater(
        tmp_path,
        [
            FakeResponse("", total=1, status_code=503),
            FakeResponse("@misc{retry,\n  title = {Retry}\n}\n", total=1),
        ],
    )

    assert updater.update(backup=False) is True
    assert len(updater.session.calls) == 2
