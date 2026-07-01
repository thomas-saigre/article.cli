"""
Zotero bibliography synchronization module

Handles fetching BibTeX entries from Zotero API with robust pagination,
error handling, and rate limiting.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import time

from .reporting import print_error, print_info, print_success, print_warning

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


BIBTEX_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
LATEX_CITE_RE = re.compile(
    r"\\(?:no)?(?:cite|parencite|textcite|autocite|citep|citet|citeauthor|citeyear)"
    r"(?:\s*\[[^\]]*\])*\s*\{([^{}]+)\}"
)
LATEX_AUX_CITE_RE = re.compile(r"\\citation\{([^{}]+)\}")
BIBLATEX_AUX_CITE_RE = re.compile(r"\\abx@aux@cite\{[^{}]*\}\{([^{}]+)\}")
TYPST_CITE_RE = re.compile(r"(?<![\w.-])@([A-Za-z0-9_:+.-]+)")


def split_bibtex_entries(content: str) -> List[str]:
    """Split BibTeX content into balanced entries."""
    entries: List[str] = []
    index = 0
    while True:
        start = content.find("@", index)
        if start == -1:
            break

        brace = content.find("{", start)
        if brace == -1:
            break

        depth = 0
        end = brace
        while end < len(content):
            char = content[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1

        if depth == 0:
            entry = content[start:end].strip()
            if entry:
                entries.append(entry)
            index = end
        else:
            break

    return entries


def extract_bibtex_keys(content: str) -> Set[str]:
    """Extract citation keys from BibTeX content."""
    return {match.group(1).strip() for match in BIBTEX_ENTRY_RE.finditer(content)}


def extract_citation_keys(path: Path) -> Set[str]:
    """Extract citation keys from LaTeX, Typst, and aux files."""
    if not path.exists() or not path.is_file():
        return set()

    text = path.read_text(encoding="utf-8", errors="replace")
    keys: Set[str] = set()

    if path.suffix == ".aux":
        for pattern in [LATEX_AUX_CITE_RE, BIBLATEX_AUX_CITE_RE]:
            for match in pattern.finditer(text):
                keys.update(_split_key_list(match.group(1)))
    elif path.suffix == ".typ":
        keys.update(match.group(1).strip() for match in TYPST_CITE_RE.finditer(text))
    else:
        for match in LATEX_CITE_RE.finditer(text):
            keys.update(_split_key_list(match.group(1)))

    keys.discard("*")
    return keys


def _split_key_list(keys: str) -> Set[str]:
    """Split comma-separated citation keys."""
    return {key.strip() for key in keys.split(",") if key.strip()}


class ZoteroBibTexUpdater:
    """Handle Zotero BibTeX synchronization with robust error handling and rate limiting"""

    def __init__(
        self,
        api_key: Optional[str],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        output_file: Optional[str] = None,
    ):
        # Validate required parameters
        if not api_key:
            raise ValueError("API key is required")
        if not user_id and not group_id:
            raise ValueError("Either user_id or group_id is required")
        if requests is None:
            raise RuntimeError(
                "'requests' library is required for Zotero synchronization. "
                "Install development dependencies with: uv sync --all-extras --dev"
            )

        self.api_key = api_key
        self.user_id = user_id
        self.group_id = group_id
        self.collection_id = collection_id
        self.output_file = output_file or "references.bib"
        self.base_url = "https://api.zotero.org"
        self.limit = 100
        self.retry_count: int = 3
        self.retry_backoff: float = 1.0
        self._group_name: Optional[str] = None

        # Create session with persistent headers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Zotero-API-Version": "3",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "ArticleCLI/1.0",
            }
        )

    def _build_url(self) -> str:
        """Build the Zotero API URL based on user or group ID"""
        if self.group_id:
            library_url = f"{self.base_url}/groups/{self.group_id}"
        elif self.user_id:
            library_url = f"{self.base_url}/users/{self.user_id}"
        else:
            raise ValueError("Either user_id or group_id must be provided")

        if self.collection_id:
            return f"{library_url}/collections/{self.collection_id}/items"
        return f"{library_url}/items"

    def _get_group_info(self) -> Optional[Dict[str, Any]]:
        """Get group information including name"""
        if not self.group_id:
            return None

        try:
            url = f"{self.base_url}/groups/{self.group_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()  # type: ignore
        except Exception as e:
            print_warning(f"Could not fetch group info: {e}")
            return None

    def get_group_name(self) -> Optional[str]:
        """Get the name of the Zotero group"""
        if self._group_name is not None:
            return self._group_name

        if not self.group_id:
            return None

        group_info = self._get_group_info()
        if group_info and "data" in group_info:
            self._group_name = group_info["data"].get("name", "Unknown Group")
            return self._group_name

        return None

    def _fetch_page(self, url: str, start: int = 0) -> Tuple[str, dict]:
        """
        Fetch a single page of results from Zotero API

        Args:
            url: Base API URL
            start: Starting index for pagination

        Returns:
            Tuple of (response_content, headers_dict)
        """
        params: Dict[str, str] = {
            "format": "bibtex",
            "start": str(start),
            "limit": str(self.limit),
        }

        try:
            response = self._request_get(url, params=params, timeout=30)

            # Check rate limiting
            rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
            if rate_limit_remaining and int(rate_limit_remaining) < 5:
                rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))
                wait_time = max(0, rate_limit_reset - time.time())
                if wait_time > 0:
                    print_warning(
                        f"Rate limit low ({rate_limit_remaining} remaining). Waiting {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time + 1)

            return response.text, dict(response.headers)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print_error(f"Rate limit exceeded. Retry after {retry_after}s")
                raise
            elif e.response.status_code == 403:
                print_error("Access forbidden. Check your API key and permissions.")
                raise
            elif e.response.status_code == 404:
                print_error("Resource not found. Check your user/group ID.")
                raise
            else:
                print_error(f"HTTP error {e.response.status_code}: {e.response.reason}")
                raise
        except requests.exceptions.RequestException as e:
            print_error(f"Network error: {str(e)}")
            raise

    def _request_get(
        self, url: str, params: Optional[Dict[str, str]] = None, timeout: int = 30
    ) -> Any:
        """Run a GET request with bounded retries for transient failures."""
        last_error: Optional[Exception] = None
        response: Any = None
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt < self.retry_count:
                        wait_time = self._retry_wait(response, attempt)
                        print_warning(
                            f"Zotero request returned HTTP {response.status_code}; "
                            f"retrying in {wait_time:.1f}s "
                            f"({attempt}/{self.retry_count})"
                        )
                        time.sleep(wait_time)
                        continue
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt >= self.retry_count:
                    break
                wait_time = self.retry_backoff * (2 ** (attempt - 1))
                print_warning(
                    f"Zotero request failed: {e}; retrying in {wait_time:.1f}s "
                    f"({attempt}/{self.retry_count})"
                )
                time.sleep(wait_time)

        if last_error is not None:
            raise last_error
        if response is None:
            raise RuntimeError("Zotero request failed before receiving a response")
        response.raise_for_status()
        return response

    def _retry_wait(self, response: Any, attempt: int) -> float:
        """Return retry delay from Zotero headers or exponential backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return float(self.retry_backoff * (2 ** (attempt - 1)))

    def _count_bibtex_entries(self, content: str) -> int:
        """Count the number of BibTeX entries in the content"""
        return len(split_bibtex_entries(content))

    def _filter_empty_entries(self, content: str) -> Tuple[str, int]:
        """
        Filter out empty or near-empty BibTeX entries

        Args:
            content: BibTeX content to filter

        Returns:
            Tuple of (filtered_content, num_removed)
        """
        import re

        # Pattern to match BibTeX entries
        entry_pattern_empty = r"@\w+\{[^,]*,\s*\}"
        entry_pattern_keywords = r"@\w+\{[^,]*,\s*keywords\s*=\s*\{[^}]*\},*\s*\}"

        # Find all empty entries (those with just the citation key and closing brace)
        empty_entries = re.findall(entry_pattern_empty, content)
        # Find all entries that only have a keywords field
        empty_entries += re.findall(entry_pattern_keywords, content)

        if not empty_entries:
            return content, 0

        # Remove empty entries
        filtered_content = content
        for entry in empty_entries:
            filtered_content = filtered_content.replace(entry, "")

        # Clean up multiple blank lines
        filtered_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", filtered_content)

        return filtered_content, len(empty_entries)

    def _normalize_bibtex_content(self, content: str) -> str:
        """Return BibTeX entries sorted by citation key for stable output."""
        entries = split_bibtex_entries(content)
        keyed_entries = []
        unkeyed_entries = []

        for entry in entries:
            match = BIBTEX_ENTRY_RE.search(entry)
            if match:
                keyed_entries.append((match.group(1).lower(), entry.strip()))
            else:
                unkeyed_entries.append(entry.strip())

        sorted_entries = [entry for _, entry in sorted(keyed_entries)]
        sorted_entries.extend(unkeyed_entries)
        return "\n\n".join(sorted_entries).strip()

    def _merge_bibtex_content(self, zotero_content: str, local_content: str) -> str:
        """Merge Zotero and local entries, keeping Zotero entries on key conflicts."""
        entries_by_key: Dict[str, str] = {}
        order: List[str] = []

        for entry in split_bibtex_entries(zotero_content):
            match = BIBTEX_ENTRY_RE.search(entry)
            if not match:
                continue
            key = match.group(1)
            entries_by_key[key] = entry.strip()
            order.append(key)

        duplicate_local_keys = []
        for entry in split_bibtex_entries(local_content):
            match = BIBTEX_ENTRY_RE.search(entry)
            if not match:
                continue
            key = match.group(1)
            if key in entries_by_key:
                duplicate_local_keys.append(key)
                continue
            entries_by_key[key] = entry.strip()
            order.append(key)

        if duplicate_local_keys:
            print_warning(
                "Skipped local entries already present in Zotero: "
                + ", ".join(sorted(duplicate_local_keys))
            )

        return "\n\n".join(entries_by_key[key] for key in sorted(order, key=str.lower))

    def _build_document(
        self,
        content: str,
        total_entries: int,
        num_removed: int,
        local_file: Optional[Path] = None,
        timestamp: bool = False,
    ) -> str:
        """Build deterministic BibTeX file content with a stable header."""
        header = [
            "% BibTeX entries from Zotero",
            f"% Total entries: {total_entries}",
        ]
        if self.group_id:
            header.append(f"% Zotero group: {self.group_id}")
        elif self.user_id:
            header.append(f"% Zotero user: {self.user_id}")
        if self.collection_id:
            header.append(f"% Zotero collection: {self.collection_id}")
        if local_file is not None:
            header.append(f"% Local entries: {local_file}")
        if num_removed > 0:
            header.append(f"% Filtered out: {num_removed} empty entries")
        if timestamp:
            header.append(f"% Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        body = content.strip()
        return "\n".join(header) + "\n\n" + body + "\n"

    def _write_if_changed(
        self,
        path: Path,
        content: str,
        backup: bool,
        check: bool,
    ) -> bool:
        """Write content only when changed, or report stale content in check mode."""
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            print_success(f"Bibliography is already up to date: {path}")
            return True

        if check:
            print_error(f"Bibliography is not up to date: {path}")
            return False

        if backup and current is not None:
            self._backup_existing_file(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print_success(f"Updated bibliography: {path}")
        return True

    def _backup_existing_file(self, path: Optional[Path] = None) -> None:
        """Create a backup of the existing BibTeX file"""
        output_path = path or Path(self.output_file)
        if output_path.exists():
            backup_file = output_path.with_name(output_path.name + ".backup")
            try:
                with open(output_path, "r", encoding="utf-8") as src:
                    with open(backup_file, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
                print_info(f"Created backup: {backup_file}")
            except Exception as e:
                print_warning(f"Could not create backup: {e}")

    def update(
        self,
        backup: bool = True,
        check: bool = False,
        include_local: bool = False,
        local_file: Optional[str] = None,
        merged_output_file: Optional[str] = None,
        check_citations: bool = False,
        citation_sources: Optional[Sequence[Path]] = None,
        timestamp: bool = False,
    ) -> bool:
        """
        Fetch and update BibTeX file from Zotero with improved pagination

        Args:
            backup: Whether to create a backup of existing file
            check: Whether to check freshness without writing files
            include_local: Whether to merge local/manual BibTeX entries
            local_file: Local/manual BibTeX file path
            merged_output_file: Optional output path for merged bibliography
            check_citations: Whether to check citation key completeness
            citation_sources: Source files to scan for citation keys
            timestamp: Whether to include a generated timestamp in the header

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._validate_inputs():
                return False

            fetched = self._fetch_zotero_bibtex()
            if fetched is None:
                return False
            filtered_content, total_entries, num_removed = fetched

            output_path = Path(self.output_file)
            output_content = self._build_document(
                filtered_content,
                total_entries,
                num_removed,
                timestamp=timestamp,
            )
            results, bibliography_for_citation_check = self._write_bibliography_outputs(
                output_path=output_path,
                output_content=output_content,
                filtered_content=filtered_content,
                num_removed=num_removed,
                backup=backup,
                check=check,
                include_local=include_local,
                local_file=local_file,
                merged_output_file=merged_output_file,
                timestamp=timestamp,
            )

            if check_citations:
                results.append(
                    self._check_citation_completeness(
                        bibliography_for_citation_check,
                        citation_sources or [],
                    )
                )

            return self._finish_update(results, total_entries)

        except Exception as e:
            print_error(f"Unexpected error during update: {e}")
            return False

    def _validate_inputs(self) -> bool:
        """Validate required Zotero identifiers."""
        if not self.api_key:
            print_error("Zotero API key is required")
            return False
        if not self.user_id and not self.group_id:
            print_error("Either user_id or group_id must be provided")
            return False
        return True

    def _describe_connection(self) -> None:
        """Report the Zotero library selected for export."""
        if self.group_id:
            group_name = self.get_group_name()
            if group_name:
                print_info(
                    f"Connecting to Zotero group: {group_name} (ID: {self.group_id})"
                )
            else:
                print_info(f"Connecting to Zotero group ID: {self.group_id}")
        elif self.user_id:
            print_info(f"Connecting to Zotero user library (ID: {self.user_id})")

        if self.collection_id:
            print_info(f"Exporting Zotero collection: {self.collection_id}")

    def _fetch_zotero_bibtex(self) -> Optional[Tuple[str, int, int]]:
        """Fetch, filter, normalize, and count Zotero BibTeX content."""
        base_url = self._build_url()
        self._describe_connection()
        print_info("Fetching BibTeX entries from Zotero...")

        first_page = self._fetch_initial_page(base_url)
        if first_page is None:
            return None

        initial_content, total_results = first_page
        all_content = self._fetch_remaining_pages(
            base_url,
            initial_content,
            total_results,
        )
        if all_content is None:
            return None

        filtered_content, num_removed = self._filter_empty_entries(
            "\n\n".join(all_content)
        )
        filtered_content = self._normalize_bibtex_content(filtered_content)
        if num_removed > 0:
            print_warning(
                f"Filtered out {num_removed} empty/incomplete entries from Zotero"
            )

        total_entries = self._count_bibtex_entries(filtered_content)
        if total_entries == 0:
            print_warning("No valid BibTeX entries found after filtering")
            return None

        return filtered_content, total_entries, num_removed

    def _fetch_initial_page(self, base_url: str) -> Optional[Tuple[str, int]]:
        """Fetch the first Zotero page and return content plus total count."""
        try:
            initial_content, initial_headers = self._fetch_page(base_url, start=0)
        except Exception as e:
            print_error(f"Failed to connect to Zotero: {e}")
            return None

        total_results = int(initial_headers.get("Total-Results", 0))
        if total_results == 0:
            print_warning("No items found in Zotero library")
            return None

        print_info(f"Found {total_results} total items in library")
        return initial_content, total_results

    def _fetch_remaining_pages(
        self,
        base_url: str,
        initial_content: str,
        total_results: int,
    ) -> Optional[List[str]]:
        """Fetch all remaining Zotero BibTeX pages."""
        all_content: List[str] = []
        if initial_content.strip():
            all_content.append(initial_content)

        pages_needed = (total_results + self.limit - 1) // self.limit
        print_info(f"Fetching {pages_needed} pages ({self.limit} items per page)...")

        for page in range(1, pages_needed):
            start = page * self.limit
            self._print_fetch_progress(page, pages_needed, start, total_results)
            try:
                content, _ = self._fetch_page(base_url, start=start)
            except Exception as e:
                print_error(f"\nFailed to fetch page {page + 1}: {e}")
                return None
            if content.strip():
                all_content.append(content)

        print()
        return all_content

    def _print_fetch_progress(
        self,
        page: int,
        pages_needed: int,
        start: int,
        total_results: int,
    ) -> None:
        """Print single-line Zotero pagination progress."""
        progress = ((page + 1) / pages_needed) * 100
        current = min(start + self.limit, total_results)
        print(
            f"  Progress: {progress:.0f}% ({current}/{total_results} items)",
            end="\r",
        )

    def _write_bibliography_outputs(
        self,
        output_path: Path,
        output_content: str,
        filtered_content: str,
        num_removed: int,
        backup: bool,
        check: bool,
        include_local: bool,
        local_file: Optional[str],
        merged_output_file: Optional[str],
        timestamp: bool,
    ) -> Tuple[List[bool], str]:
        """Write primary and optional merged bibliography outputs."""
        if not include_local:
            return (
                [
                    self._write_if_changed(
                        output_path,
                        output_content,
                        backup=backup,
                        check=check,
                    )
                ],
                output_content,
            )

        local_path = Path(local_file) if local_file else Path("local_references.bib")
        if not local_path.exists():
            print_warning(f"Local BibTeX file not found: {local_path}")
            return (
                [
                    self._write_if_changed(
                        output_path,
                        output_content,
                        backup=backup,
                        check=check,
                    )
                ],
                output_content,
            )

        merged_document = self._build_merged_document(
            filtered_content,
            local_path,
            num_removed,
            timestamp,
        )
        merged_path = Path(merged_output_file) if merged_output_file else None
        if merged_path is None:
            return (
                [
                    self._write_if_changed(
                        output_path,
                        merged_document,
                        backup=backup,
                        check=check,
                    )
                ],
                merged_document,
            )

        return (
            [
                self._write_if_changed(
                    output_path,
                    output_content,
                    backup=backup,
                    check=check,
                ),
                self._write_if_changed(
                    merged_path,
                    merged_document,
                    backup=backup,
                    check=check,
                ),
            ],
            merged_document,
        )

    def _build_merged_document(
        self,
        filtered_content: str,
        local_path: Path,
        num_removed: int,
        timestamp: bool,
    ) -> str:
        """Build a merged Zotero + local BibTeX document."""
        local_content = local_path.read_text(encoding="utf-8", errors="replace")
        merged_content = self._merge_bibtex_content(filtered_content, local_content)
        merged_entries = self._count_bibtex_entries(merged_content)
        return self._build_document(
            merged_content,
            merged_entries,
            num_removed,
            local_file=local_path,
            timestamp=timestamp,
        )

    def _finish_update(self, results: Sequence[bool], total_entries: int) -> bool:
        """Return final update status and print a short summary."""
        if all(results):
            print_success(f"Bibliography contains {total_entries} Zotero entries")
            return True
        return False

    def _check_citation_completeness(
        self, bibliography_content: str, citation_sources: Sequence[Path]
    ) -> bool:
        """Check whether cited keys are present in bibliography content."""
        if not citation_sources:
            print_info("No citation source files found for citation check.")
            return True

        bibliography_keys = extract_bibtex_keys(bibliography_content)
        cited_keys: Set[str] = set()
        for source in citation_sources:
            cited_keys.update(extract_citation_keys(source))

        if not cited_keys:
            print_info("No citation keys found in source files.")
            return True

        missing = sorted(cited_keys - bibliography_keys)
        if missing:
            print_error(
                "Missing bibliography entries for citations: " + ", ".join(missing)
            )
            return False

        print_success(f"All {len(cited_keys)} cited keys are present in bibliography")
        return True
