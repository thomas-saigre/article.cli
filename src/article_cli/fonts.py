"""
Font installation module for article-cli

Provides functionality to download and install fonts for XeLaTeX projects.
"""

import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any

import requests

from .reporting import print_error, print_info, print_success, print_warning

# Default font sources for common themes
# Note: Marianne font from French government requires manual download due to Cloudflare protection.
# Configure custom URL in pyproject.toml if you have a mirror or local copy.
DEFAULT_FONT_SOURCES = [
    {
        "name": "Roboto",
        "url": "https://github.com/googlefonts/roboto/releases/download/v2.138/roboto-unhinted.zip",
        "description": "Google's sans-serif font family",
    },
    {
        "name": "Roboto Mono",
        "url": "https://github.com/googlefonts/RobotoMono/archive/refs/heads/main.zip",
        "description": "Google's monospace font, good for code",
    },
]

# Additional font sources that may require special handling
OPTIONAL_FONT_SOURCES = {
    "Marianne": {
        "name": "Marianne",
        "url": "https://www.info.gouv.fr/upload/media/content/0001/14/e9dd2398914853b3c21c402245866bc74cd3d3c5.zip",
        "description": "French government official font - TTF version (Système de Design de l'État)",
        "note": "May require manual download due to Cloudflare protection",
    },
}


class FontInstaller:
    """Handles downloading and installing fonts for LaTeX projects"""

    def __init__(
        self,
        fonts_dir: Optional[Path] = None,
        sources: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Initialize font installer

        Args:
            fonts_dir: Directory to install fonts (default: fonts/)
            sources: List of font sources with 'name', 'url', and optional 'description'
        """
        self.fonts_dir = fonts_dir or Path("fonts")
        self.sources = sources or DEFAULT_FONT_SOURCES

    def install_all(self, force: bool = False) -> bool:
        """
        Install all configured fonts

        Args:
            force: Re-download even if fonts already exist

        Returns:
            True if all fonts installed successfully
        """
        print_info(f"Installing fonts to: {self.fonts_dir}")

        # Create fonts directory if it doesn't exist
        self.fonts_dir.mkdir(parents=True, exist_ok=True)

        success = True
        for source in self.sources:
            name = source.get("name", "Unknown")
            url = source.get("url", "")
            description = source.get("description", "")

            if not url:
                print_warning(f"Skipping '{name}': no URL provided")
                continue

            # Check if already installed
            font_subdir = self.fonts_dir / name.replace(" ", "")
            if font_subdir.exists() and not force:
                print_info(f"'{name}' already installed at {font_subdir}")
                continue

            print_info(f"Installing '{name}'...")
            if description:
                print_info(f"  {description}")

            try:
                self._download_and_extract(name, url, font_subdir)
                print_success(f"'{name}' installed successfully")
            except Exception as e:
                print_error(f"Failed to install '{name}': {e}")
                success = False

        if success:
            print_success(f"All fonts installed to {self.fonts_dir}")
            self._print_usage_instructions()

        return success

    def install_font(self, name: str, url: str, force: bool = False) -> bool:
        """
        Install a single font from URL

        Args:
            name: Font name (used for subdirectory)
            url: URL to download font zip file
            force: Re-download even if font already exists

        Returns:
            True if font installed successfully
        """
        font_subdir = self.fonts_dir / name.replace(" ", "")

        if font_subdir.exists() and not force:
            print_info(f"'{name}' already installed at {font_subdir}")
            return True

        # Create fonts directory if it doesn't exist
        self.fonts_dir.mkdir(parents=True, exist_ok=True)

        print_info(f"Installing '{name}' from {url}...")

        try:
            self._download_and_extract(name, url, font_subdir)
            print_success(f"'{name}' installed successfully")
            return True
        except Exception as e:
            print_error(f"Failed to install '{name}': {e}")
            return False

    def _download_and_extract(self, name: str, url: str, target_dir: Path) -> None:
        """
        Download and extract a font zip file

        Args:
            name: Font name for display
            url: URL to download
            target_dir: Directory to extract to
        """
        # Create target directory
        target_dir.mkdir(parents=True, exist_ok=True)

        # Download to temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

            try:
                print_info(f"  Downloading...")
                self._download_file(url, tmp_path)

                print_info(f"  Extracting to {target_dir}...")
                self._extract_zip(tmp_path, target_dir)

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
        # Use requests library for better redirect and header handling
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            response = requests.get(
                url, headers=headers, allow_redirects=True, stream=True, timeout=60
            )
            response.raise_for_status()

            # Get file size if available
            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) if content_length else None

            # Download in chunks
            chunk_size = 8192
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
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

        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP error: {e}")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection error: {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError("Download timed out")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Download failed: {e}")

    def _extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        """
        Extract a zip file to target directory

        Args:
            zip_path: Path to zip file
            target_dir: Directory to extract to
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Check for font files in the archive
                font_files = [
                    f
                    for f in zf.namelist()
                    if f.lower().endswith((".ttf", ".otf", ".woff", ".woff2"))
                ]

                if not font_files:
                    print_warning("  No font files found in archive")

                # Extract all files
                zf.extractall(target_dir)

                print_info(
                    f"  Extracted {len(zf.namelist())} files ({len(font_files)} fonts)"
                )

        except zipfile.BadZipFile:
            raise RuntimeError("Invalid or corrupted zip file")

    def _print_usage_instructions(self) -> None:
        """Print instructions for using installed fonts"""
        print_info("")
        print_info("To use these fonts in your LaTeX document:")
        print_info("  1. Make sure you're using XeLaTeX or LuaLaTeX")
        print_info("  2. Add the font path to your document preamble:")
        print_info(f"     \\fontspec{{[{self.fonts_dir}/FontName/font.ttf]}}")
        print_info("")
        print_info("For CI/CD, fonts are automatically installed if configured:")
        print_info("  [tool.article-cli.workflow]")
        print_info(f'  fonts_dir = "{self.fonts_dir}"')
        print_info("  install_fonts = true")

    def list_installed(self) -> List[str]:
        """
        List installed fonts

        Returns:
            List of installed font directory names
        """
        if not self.fonts_dir.exists():
            return []

        return [
            d.name
            for d in self.fonts_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def get_font_files(self, font_name: Optional[str] = None) -> List[Path]:
        """
        Get list of font files

        Args:
            font_name: Optional font name to filter by

        Returns:
            List of font file paths
        """
        if not self.fonts_dir.exists():
            return []

        search_dir = self.fonts_dir
        if font_name:
            search_dir = self.fonts_dir / font_name.replace(" ", "")
            if not search_dir.exists():
                return []

        font_files: List[Path] = []
        for ext in (".ttf", ".otf", ".woff", ".woff2"):
            font_files.extend(search_dir.rglob(f"*{ext}"))

        return sorted(font_files)


def install_fonts_from_config(config: Any, force: bool = False) -> bool:
    """
    Install fonts based on configuration

    Args:
        config: Config object with get_fonts_config() method
        force: Re-download even if fonts already exist

    Returns:
        True if all fonts installed successfully
    """
    fonts_config = config.get_fonts_config()

    fonts_dir = Path(fonts_config.get("directory", "fonts"))
    sources = fonts_config.get("sources", DEFAULT_FONT_SOURCES)

    installer = FontInstaller(fonts_dir=fonts_dir, sources=sources)
    return installer.install_all(force=force)
