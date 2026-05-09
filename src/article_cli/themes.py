"""
Theme installation module for article-cli

Provides functionality to download and install Beamer themes for presentations.
"""

import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .reporting import print_error, print_info, print_success, print_warning

# Default theme sources
DEFAULT_THEME_SOURCES: Dict[str, Dict[str, Any]] = {
    "numpex": {
        "url": "https://github.com/numpex/presentation.template.d/archive/refs/heads/main.zip",
        "description": "NumPEx Beamer/Typst theme following French government visual identity",
        "files": [
            "beamerthemenumpex.sty",
            "beamercolorthemenumpex.sty",
            "beamerfontthemenumpex.sty",
        ],
        "typst_files": [
            "numpex.typ",
        ],
        "directories": ["images"],
        "requires_fonts": True,
        "engine": "xelatex",
    },
}


class ThemeInstaller:
    """Handles downloading and installing Beamer themes for presentations"""

    def __init__(
        self,
        themes_dir: Optional[Path] = None,
        sources: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize theme installer

        Args:
            themes_dir: Directory to install themes (default: current directory)
            sources: Dict of theme sources with name as key
        """
        self.themes_dir = themes_dir or Path(".")
        self.sources = sources or DEFAULT_THEME_SOURCES

    def list_available(self) -> List[Dict[str, Any]]:
        """
        List all available themes

        Returns:
            List of theme info dicts
        """
        themes = []
        for name, info in self.sources.items():
            themes.append(
                {
                    "name": name,
                    "description": info.get("description", ""),
                    "url": info.get("url", ""),
                    "requires_fonts": info.get("requires_fonts", False),
                    "engine": info.get("engine", "pdflatex"),
                }
            )
        return themes

    def list_installed(self) -> List[Dict[str, Any]]:
        """
        List installed themes in the themes directory

        Returns:
            List of installed theme info
        """
        installed = []

        for name, info in self.sources.items():
            # Check if theme files exist
            theme_files = info.get("files", [])
            if theme_files:
                main_file = self.themes_dir / theme_files[0]
                if main_file.exists():
                    installed.append(
                        {
                            "name": name,
                            "path": str(self.themes_dir),
                            "files": [
                                str(self.themes_dir / f)
                                for f in theme_files
                                if (self.themes_dir / f).exists()
                            ],
                        }
                    )

        return installed

    def install_theme(self, name: str, force: bool = False) -> bool:
        """
        Install a theme by name

        Args:
            name: Theme name (must be in sources)
            force: Re-download even if theme already exists

        Returns:
            True if theme installed successfully
        """
        if name not in self.sources:
            print_error(f"Unknown theme: '{name}'")
            print_info("Available themes:")
            for theme_name, theme_info in self.sources.items():
                desc = theme_info.get("description", "")
                print_info(f"  - {theme_name}: {desc}")
            return False

        theme_info = self.sources[name]
        theme_files = theme_info.get("files", [])
        typst_files = theme_info.get("typst_files", [])
        theme_dirs = theme_info.get("directories", [])

        # Combine LaTeX and Typst files for extraction
        all_files = theme_files + typst_files

        # Check if already installed
        if theme_files and not force:
            main_file = self.themes_dir / theme_files[0]
            if main_file.exists():
                print_info(f"Theme '{name}' already installed at {self.themes_dir}")
                return True

        url = theme_info.get("url", "")
        if not url:
            print_error(f"No URL configured for theme '{name}'")
            return False

        description = theme_info.get("description", "")
        print_info(f"Installing theme '{name}'...")
        if description:
            print_info(f"  {description}")

        try:
            self._download_and_extract_theme(name, url, all_files, theme_dirs)
            print_success(f"Theme '{name}' installed successfully")

            # Show additional info
            if theme_info.get("requires_fonts"):
                print_info("")
                print_warning("This theme requires custom fonts.")
                print_info("Run 'article-cli install-fonts' to install them.")

            engine = theme_info.get("engine", "pdflatex")
            if engine != "pdflatex":
                print_info("")
                print_info(f"This theme requires {engine} for compilation.")
                print_info(f"Use: article-cli compile --engine {engine}")

            self._print_usage_instructions(name)
            return True

        except Exception as e:
            print_error(f"Failed to install theme '{name}': {e}")
            return False

    def install_from_url(
        self,
        name: str,
        url: str,
        files: Optional[List[str]] = None,
        force: bool = False,
    ) -> bool:
        """
        Install a theme from a custom URL

        Args:
            name: Theme name to use
            url: URL to download theme archive
            files: List of specific files to extract (optional)
            force: Re-download even if theme exists

        Returns:
            True if theme installed successfully
        """
        print_info(f"Installing theme '{name}' from {url}...")

        try:
            self._download_and_extract_theme(name, url, files or [], [])
            print_success(f"Theme '{name}' installed successfully")
            return True
        except Exception as e:
            print_error(f"Failed to install theme '{name}': {e}")
            return False

    def _download_and_extract_theme(
        self,
        name: str,
        url: str,
        theme_files: List[str],
        theme_dirs: List[str],
    ) -> None:
        """
        Download and extract theme files from archive

        Args:
            name: Theme name for display
            url: URL to download
            theme_files: Specific files to extract
            theme_dirs: Specific directories to extract
        """
        # Create themes directory
        self.themes_dir.mkdir(parents=True, exist_ok=True)

        # Download to temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

            try:
                print_info("  Downloading...")
                self._download_file(url, tmp_path)

                print_info(f"  Extracting theme files...")
                self._extract_theme_files(tmp_path, theme_files, theme_dirs)

            finally:
                # Clean up temporary file
                if tmp_path.exists():
                    tmp_path.unlink()

    def _download_file(self, url: str, dest: Path) -> None:
        """
        Download a file from URL with progress indication

        Args:
            url: URL to download
            dest: Destination path
        """
        # Create request with user agent to avoid blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; article-cli theme installer)"
        }
        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=60) as response:
                # Get file size if available
                content_length = response.headers.get("Content-Length")
                total_size = int(content_length) if content_length else None

                # Download in chunks
                chunk_size = 8192
                downloaded = 0

                with open(dest, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Show progress
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            print(
                                f"\r  Progress: {downloaded:,} / {total_size:,} bytes ({percent:.1f}%)",
                                end="",
                                flush=True,
                            )
                        else:
                            print(
                                f"\r  Downloaded: {downloaded:,} bytes",
                                end="",
                                flush=True,
                            )

                print()  # New line after progress

        except HTTPError as e:
            raise RuntimeError(f"HTTP error {e.code}: {e.reason}")
        except URLError as e:
            raise RuntimeError(f"URL error: {e.reason}")
        except TimeoutError:
            raise RuntimeError("Download timed out")

    def _extract_theme_files(
        self, zip_path: Path, theme_files: List[str], theme_dirs: List[str]
    ) -> None:
        """
        Extract specific theme files from a zip archive

        Args:
            zip_path: Path to zip file
            theme_files: List of file names to extract
            theme_dirs: List of directory names to extract
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Get all file names in archive
                all_files = zf.namelist()

                # Find and extract theme files
                extracted_count = 0

                for member in all_files:
                    member_name = Path(member).name
                    member_parts = Path(member).parts

                    # Check if this is one of the theme files
                    if theme_files and member_name in theme_files:
                        # Extract to themes directory with just the filename
                        target_path = self.themes_dir / member_name
                        with zf.open(member) as source:
                            with open(target_path, "wb") as target:
                                target.write(source.read())
                        print_info(f"    Extracted: {member_name}")
                        extracted_count += 1

                    # Check if this is in one of the theme directories
                    for theme_dir in theme_dirs:
                        if theme_dir in member_parts:
                            # Find the index of the theme_dir in the path
                            dir_idx = member_parts.index(theme_dir)
                            # Build relative path from theme_dir onwards
                            rel_parts = member_parts[dir_idx:]
                            rel_path = Path(*rel_parts)

                            target_path = self.themes_dir / rel_path

                            if member.endswith("/"):
                                # It's a directory
                                target_path.mkdir(parents=True, exist_ok=True)
                            else:
                                # It's a file
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                with zf.open(member) as source:
                                    with open(target_path, "wb") as target:
                                        target.write(source.read())
                                print_info(f"    Extracted: {rel_path}")
                                extracted_count += 1
                            break

                # If no specific files requested, extract all .sty files
                if not theme_files and not theme_dirs:
                    for member in all_files:
                        if member.endswith(".sty"):
                            member_name = Path(member).name
                            target_path = self.themes_dir / member_name
                            with zf.open(member) as source:
                                with open(target_path, "wb") as target:
                                    target.write(source.read())
                            print_info(f"    Extracted: {member_name}")
                            extracted_count += 1

                print_info(f"  Extracted {extracted_count} files")

        except zipfile.BadZipFile:
            raise RuntimeError("Invalid or corrupted zip file")

    def _print_usage_instructions(self, name: str) -> None:
        """Print instructions for using installed theme"""
        print_info("")
        print_info("To use this theme in your LaTeX presentation:")
        print_info(f"  \\usetheme{{{name}}}")
        print_info("")
        print_info("Example LaTeX document:")
        print_info("  \\documentclass[aspectratio=169]{beamer}")
        print_info(f"  \\usetheme{{{name}}}")
        print_info("  \\title{Your Title}")
        print_info("  \\author{Your Name}")
        print_info("  \\begin{document}")
        print_info("  \\maketitle")
        print_info("  \\end{document}")
        print_info("")
        print_info("To use this theme in Typst:")
        print_info(f'  #import "{name}.typ": *')
        print_info(
            f'  #show: {name}-theme.with(title: "Your Title", author: "Your Name")'
        )


def get_available_themes() -> Dict[str, Dict[str, Any]]:
    """Get dictionary of available themes"""
    return DEFAULT_THEME_SOURCES.copy()


def get_theme_info(name: str) -> Optional[Dict[str, Any]]:
    """Get info for a specific theme"""
    return DEFAULT_THEME_SOURCES.get(name)
