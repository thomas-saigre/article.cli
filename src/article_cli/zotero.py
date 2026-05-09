"""
Zotero bibliography synchronization module

Handles fetching BibTeX entries from Zotero API with robust pagination,
error handling, and rate limiting.
"""

import os
from typing import Optional, Tuple, List, Dict, Any
import time

from .reporting import Colors, print_error, print_info, print_success, print_warning

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


class ZoteroBibTexUpdater:
    """Handle Zotero BibTeX synchronization with robust error handling and rate limiting"""

    def __init__(
        self,
        api_key: Optional[str],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
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
        self.output_file = output_file or "references.bib"
        self.base_url = "https://api.zotero.org"
        self.limit = 100
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
            return f"{self.base_url}/groups/{self.group_id}/items"
        elif self.user_id:
            return f"{self.base_url}/users/{self.user_id}/items"
        else:
            raise ValueError("Either user_id or group_id must be provided")

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
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

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

    def _count_bibtex_entries(self, content: str) -> int:
        """Count the number of BibTeX entries in the content"""
        return (
            content.count("@article")
            + content.count("@book")
            + content.count("@inproceedings")
            + content.count("@incollection")
            + content.count("@misc")
            + content.count("@phdthesis")
            + content.count("@techreport")
            + content.count("@mastersthesis")
        )

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
        entry_pattern = r"@\w+\{[^,]*,\s*\}"

        # Find all empty entries (those with just the citation key and closing brace)
        empty_entries = re.findall(entry_pattern, content)

        if not empty_entries:
            return content, 0

        # Remove empty entries
        filtered_content = content
        for entry in empty_entries:
            filtered_content = filtered_content.replace(entry, "")

        # Clean up multiple blank lines
        filtered_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", filtered_content)

        return filtered_content, len(empty_entries)

    def _backup_existing_file(self) -> None:
        """Create a backup of the existing BibTeX file"""
        if os.path.exists(self.output_file):
            backup_file = f"{self.output_file}.backup"
            try:
                with open(self.output_file, "r", encoding="utf-8") as src:
                    with open(backup_file, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
                print_info(f"Created backup: {backup_file}")
            except Exception as e:
                print_warning(f"Could not create backup: {e}")

    def update(self, backup: bool = True) -> bool:
        """
        Fetch and update BibTeX file from Zotero with improved pagination

        Args:
            backup: Whether to create a backup of existing file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            if not self.api_key:
                print_error("Zotero API key is required")
                return False

            if not self.user_id and not self.group_id:
                print_error("Either user_id or group_id must be provided")
                return False

            # Create backup if requested
            if backup:
                self._backup_existing_file()

            # Build URL
            base_url = self._build_url()

            # Show what we're connecting to
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

            # First request to get total count
            print_info("Fetching BibTeX entries from Zotero...")

            try:
                initial_content, initial_headers = self._fetch_page(base_url, start=0)
            except Exception as e:
                print_error(f"Failed to connect to Zotero: {e}")
                return False

            # Get total number of items from header
            total_results = int(initial_headers.get("Total-Results", 0))

            if total_results == 0:
                print_warning("No items found in Zotero library")
                return False

            print_info(f"Found {total_results} total items in library")

            # Collect all BibTeX content
            all_bibtex_content: List[str] = []

            # Add initial page
            if initial_content.strip():
                all_bibtex_content.append(initial_content)

            # Calculate pages needed
            pages_needed = (total_results + self.limit - 1) // self.limit
            print_info(
                f"Fetching {pages_needed} pages ({self.limit} items per page)..."
            )

            # Fetch remaining pages
            for page in range(1, pages_needed):
                start = page * self.limit
                progress = ((page + 1) / pages_needed) * 100

                print(
                    f"  Progress: {progress:.0f}% ({start + self.limit if start + self.limit < total_results else total_results}/{total_results} items)",
                    end="\r",
                )

                try:
                    content, _ = self._fetch_page(base_url, start=start)
                    if content.strip():
                        all_bibtex_content.append(content)
                except Exception as e:
                    print_error(f"\nFailed to fetch page {page + 1}: {e}")
                    return False

            print()  # New line after progress

            # Combine all content
            combined_content = "\n\n".join(all_bibtex_content)

            # Filter out empty entries
            filtered_content, num_removed = self._filter_empty_entries(combined_content)
            if num_removed > 0:
                print_warning(
                    f"Filtered out {num_removed} empty/incomplete entries from Zotero"
                )

            # Count total valid entries
            total_entries = self._count_bibtex_entries(filtered_content)

            if total_entries == 0:
                print_warning("No valid BibTeX entries found after filtering")
                return False

            # Write to file
            print_info(
                f"Writing {total_entries} valid entries to {self.output_file}..."
            )

            try:
                with open(self.output_file, "w", encoding="utf-8") as f:
                    # Add header comment
                    f.write(f"% BibTeX entries from Zotero\n")
                    f.write(f"% Total entries: {total_entries}\n")
                    if num_removed > 0:
                        f.write(f"% Filtered out: {num_removed} empty entries\n")
                    f.write(f"% Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(filtered_content)
                    if not filtered_content.endswith("\n"):
                        f.write("\n")

                print_success(
                    f"Successfully updated {self.output_file} with {total_entries} entries"
                )
                return True

            except IOError as e:
                print_error(f"Failed to write to {self.output_file}: {e}")
                return False

        except Exception as e:
            print_error(f"Unexpected error during update: {e}")
            return False
