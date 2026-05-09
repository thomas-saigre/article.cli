"""
Configuration management for article-cli

Supports both environment variables and TOML configuration files.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
import argparse

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for older Python versions
    except ImportError:
        tomllib = None


class Config:
    """Configuration manager for article-cli"""

    def __init__(
        self, config_file: Optional[Union[str, Path]] = None, quiet: bool = False
    ):
        """
        Initialize configuration manager

        Args:
            config_file: Optional path to configuration file
            quiet: Suppress informational config-loading messages
        """
        self.config_file = config_file
        self.quiet = quiet
        self.loaded_config_file: Optional[Path] = None
        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _find_config_file(self) -> Optional[Path]:
        """Find configuration file in project directory"""
        if self.config_file:
            config_path = Path(self.config_file)
            if config_path.exists():
                return config_path
            else:
                raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Look for default config files (in priority order)
        search_paths = [
            Path.cwd()
            / ".article-cli.toml",  # Dedicated config file (highest priority)
            Path.cwd() / "pyproject.toml",  # Project config file
            Path.cwd() / "article-cli.toml",  # Alternative dedicated file
            Path.home() / ".config" / "article-cli" / "config.toml",  # XDG config
            Path.home() / ".article-cli.toml",  # User config (lowest priority)
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    def _load_config(self) -> None:
        """Load configuration from file if it exists"""
        config_path = self._find_config_file()
        self.loaded_config_file = config_path.resolve() if config_path else None

        if config_path and tomllib:
            try:
                with open(config_path, "rb") as f:
                    full_config = tomllib.load(f)

                # Handle pyproject.toml vs dedicated config file
                if config_path.name == "pyproject.toml":
                    # Extract article-cli config section from pyproject.toml
                    self._config_data = full_config.get("tool", {}).get(
                        "article-cli", {}
                    )
                    if self._config_data:
                        if not self.quiet:
                            print(
                                f"Loaded configuration from: {config_path} [tool.article-cli]"
                            )
                    else:
                        # Fallback: look for legacy sections at root level
                        legacy_sections = ["zotero", "git", "latex"]
                        self._config_data = {
                            k: v for k, v in full_config.items() if k in legacy_sections
                        }
                        if self._config_data:
                            if not self.quiet:
                                print(
                                    f"Loaded legacy configuration from: {config_path}"
                                )
                else:
                    # Dedicated config file - use as-is
                    self._config_data = full_config
                    if not self.quiet:
                        print(f"Loaded configuration from: {config_path}")

            except Exception as e:
                if not self.quiet:
                    print(f"Warning: Could not load config file {config_path}: {e}")
                self._config_data = {}
        elif config_path and not tomllib:
            if not self.quiet:
                print(
                    "Warning: TOML support not available. Install dependencies with: uv sync"
                )
            self._config_data = {}
        else:
            self._config_data = {}

    def get(
        self, section: str, key: str, default: Any = None, env_var: Optional[str] = None
    ) -> Any:
        """
        Get configuration value with priority: CLI args > env vars > config file > default

        Args:
            section: Configuration section name
            key: Configuration key name
            default: Default value if not found
            env_var: Environment variable name to check

        Returns:
            Configuration value
        """
        # Check environment variable first
        if env_var and env_var in os.environ:
            return os.environ[env_var]

        # Check config file
        if section in self._config_data and key in self._config_data[section]:
            return self._config_data[section][key]

        return default

    def get_zotero_config(self) -> Dict[str, Any]:
        """Get Zotero-specific configuration"""
        return {
            "api_key": self.get("zotero", "api_key", env_var="ZOTERO_API_KEY"),
            "user_id": self.get("zotero", "user_id", env_var="ZOTERO_USER_ID"),
            "group_id": self.get("zotero", "group_id", env_var="ZOTERO_GROUP_ID"),
            "collection_id": self.get(
                "zotero", "collection_id", "", env_var="ZOTERO_COLLECTION_ID"
            ),
            "output_file": self.get(
                "zotero", "output_file", "references.bib", env_var="BIBTEX_FILE"
            ),
            "local_file": self.get("zotero", "local_file", "local_references.bib"),
            "merged_output_file": self.get("zotero", "merged_output_file", ""),
            "deterministic": self.get("zotero", "deterministic", True),
        }

    def get_git_config(self) -> Dict[str, Any]:
        """Get Git-specific configuration"""
        return {
            "auto_push": self.get("git", "auto_push", False),
            "default_branch": self.get("git", "default_branch", "main"),
        }

    def get_release_config(self) -> Dict[str, Any]:
        """Get release workflow configuration."""
        return {
            "tag_policy": self.get("release", "tag_policy", "paper"),
            "allow_dirty": self.get("release", "allow_dirty", False),
            "compile": self.get("release", "compile", True),
            "check_pdf": self.get("release", "check_pdf", True),
            "checksum": self.get("release", "checksum", True),
            "bibliography": self.get("release", "bibliography", "off"),
            "github_release": self.get("release", "github_release", False),
        }

    def get_latex_config(self) -> Dict[str, Any]:
        """Get LaTeX-specific configuration"""
        default_extensions = [
            ".aux",
            ".bbl",
            ".blg",
            ".log",
            ".out",
            ".pyg",
            ".fls",
            ".synctex.gz",
            ".toc",
            ".fdb_latexmk",
            ".idx",
            ".ilg",
            ".ind",
            ".chl",
            ".lof",
            ".lot",
        ]

        return {
            "clean_extensions": self.get(
                "latex", "clean_extensions", default_extensions
            ),
            "build_dir": self.get("latex", "build_dir", "."),
            "engine": self.get("latex", "engine", "latexmk"),
            "shell_escape": self.get("latex", "shell_escape", False),
            "timeout": self.get("latex", "timeout", 300),
        }

    def get_project_config(self) -> Dict[str, Any]:
        """Get project-level configuration"""
        return {
            "project_type": self.get("project", "type", "article"),
            "style": self.get("project", "style", "default"),
            "template": self.get("project", "template", ""),
        }

    def get_documents_config(self) -> Dict[str, Any]:
        """Get documents configuration for multi-document projects"""
        return {
            "main": self.get("documents", "main", ""),
            "additional": self.get("documents", "additional", []),
        }

    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow-specific configuration for GitHub Actions"""
        return {
            "output_dir": self.get("workflow", "output_dir", ""),
            "fonts_dir": self.get("workflow", "fonts_dir", ""),
            "install_fonts": self.get("workflow", "install_fonts", False),
            "runner_policy": self.get("workflow", "runner_policy", "github"),
            "github_runner": self.get("workflow", "github_runner", "ubuntu-24.04"),
            "self_hosted_label": self.get(
                "workflow", "self_hosted_label", "self-texlive"
            ),
            "self_hosted_org": self.get("workflow", "self_hosted_org", ""),
            "bibliography": self.get("workflow", "bibliography", "off"),
            "release": self.get("workflow", "release", "github"),
            "artifact_includes": self.get("workflow", "artifact_includes", []),
        }

    def get_presentation_config(self) -> Dict[str, Any]:
        """Get presentation-specific configuration (for Beamer)"""
        return {
            "theme": self.get("presentation", "theme", ""),
            "aspect_ratio": self.get("presentation", "aspect_ratio", "169"),
            "color_theme": self.get("presentation", "color_theme", ""),
            "font_theme": self.get("presentation", "font_theme", ""),
        }

    def get_poster_config(self) -> Dict[str, Any]:
        """Get poster-specific configuration"""
        return {
            "size": self.get("poster", "size", "a0"),
            "orientation": self.get("poster", "orientation", "portrait"),
            "columns": self.get("poster", "columns", 3),
        }

    def get_fonts_config(self) -> Dict[str, Any]:
        """Get font installation configuration"""
        # Import default sources from fonts module to keep them in sync
        from .fonts import DEFAULT_FONT_SOURCES

        return {
            "directory": self.get("fonts", "directory", "fonts"),
            "sources": self.get("fonts", "sources", DEFAULT_FONT_SOURCES),
        }

    def get_themes_config(self) -> Dict[str, Any]:
        """Get theme installation configuration"""
        # Default theme sources
        default_sources = {
            "numpex": {
                "url": "https://github.com/numpex/presentation.template.d/archive/refs/heads/main.zip",
                "description": "NumPEx Beamer theme following French government visual identity",
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

        return {
            "directory": self.get("themes", "directory", "."),
            "sources": self.get("themes", "sources", default_sources),
        }

    def get_typst_config(self) -> Dict[str, Any]:
        """Get Typst-specific configuration"""
        return {
            "font_paths": self.get("typst", "font_paths", []),
            "build_dir": self.get("typst", "build_dir", ""),
        }

    def validate_zotero_config(self, args: argparse.Namespace) -> Dict[str, Any]:
        """
        Validate and merge Zotero configuration from args and config

        Args:
            args: Parsed command line arguments

        Returns:
            Dict with validated Zotero configuration

        Raises:
            ValueError: If required configuration is missing
        """
        config = self.get_zotero_config()

        # Override with command line arguments
        if hasattr(args, "api_key") and args.api_key:
            config["api_key"] = args.api_key
        if hasattr(args, "user_id") and args.user_id:
            config["user_id"] = args.user_id
        if hasattr(args, "group_id") and args.group_id:
            config["group_id"] = args.group_id
        if hasattr(args, "collection") and args.collection:
            config["collection_id"] = args.collection
        if hasattr(args, "output") and args.output:
            config["output_file"] = args.output
        if hasattr(args, "local_file") and args.local_file:
            config["local_file"] = args.local_file
        if hasattr(args, "merged_output") and args.merged_output:
            config["merged_output_file"] = args.merged_output

        # Validate required fields
        if not config["api_key"]:
            raise ValueError(
                "Zotero API key is required. Set via:\n"
                "  - Command line: --api-key YOUR_KEY\n"
                "  - Environment: export ZOTERO_API_KEY=YOUR_KEY\n"
                '  - Config file: [zotero] api_key = "YOUR_KEY"'
            )

        if not config["user_id"] and not config["group_id"]:
            raise ValueError(
                "Either Zotero user ID or group ID is required. Set via:\n"
                "  - Command line: --user-id ID or --group-id ID\n"
                "  - Environment: export ZOTERO_USER_ID=ID or ZOTERO_GROUP_ID=ID\n"
                '  - Config file: [zotero] user_id = "ID" or group_id = "ID"'
            )

        return config

    def create_sample_config(self, path: Optional[Path] = None) -> Path:
        """
        Create a sample configuration file

        Args:
            path: Optional path for config file

        Returns:
            Path to created config file
        """
        if path is None:
            path = Path.cwd() / ".article-cli.toml"

        sample_config = """# Article CLI Configuration File
# Copy this file to your project root as .article-cli.toml

[zotero]
# Your Zotero API key (get from https://www.zotero.org/settings/keys)
api_key = "your_api_key_here"

# Either user_id OR group_id (not both)
# user_id = "your_user_id"
group_id = "4678293"  # Default group ID for article.template

# Output file for bibliography
output_file = "references.bib"

# Optional Zotero collection or subcollection key
# collection_id = ""

# Optional local/manual entries. Use article-cli bib update --include-local
# to merge them into the output or --merged-output to write a separate file.
local_file = "local_references.bib"
# merged_output_file = ""

# Deterministic output omits timestamps and writes only when content changes.
deterministic = true

[git]
# Automatically push after creating releases
auto_push = false

# Default branch name
default_branch = "main"

[release]
# Tag policy: "paper" accepts v1, v1.0, v1.0.0 and prerelease suffixes.
# Use "semver" for strict vX.Y.Z, or "loose" for any non-space tag.
tag_policy = "paper"
allow_dirty = false
compile = true
check_pdf = true
checksum = true
# bibliography policy: "off", "check", or "update"
bibliography = "off"
github_release = false

[latex]
# File extensions to clean
clean_extensions = [
    ".aux", ".bbl", ".blg", ".log", ".out", ".pyg",
    ".fls", ".synctex.gz", ".toc", ".fdb_latexmk",
    ".idx", ".ilg", ".ind", ".chl", ".lof", ".lot"
]

# Build directory (relative to project root)
build_dir = "."

# Default LaTeX engine
# Options: "latexmk", "pdflatex", "xelatex", "lualatex"
# Use xelatex or lualatex for documents with custom fonts (e.g., Beamer presentations)
engine = "latexmk"

# Enable shell escape by default
shell_escape = false

# Compilation timeout in seconds
timeout = 300

[project]
# Project type: "article", "typst-article", "presentation", "typst-presentation",
# "poster", or "typst-poster"
type = "article"

# Built-in source style for generated article files, e.g. "default", "lncs", "ieee".
# Use article-cli init --template PATH for a project-specific Jinja2 template.
style = "default"

# Presentation-specific settings (only used when type = "presentation")
[presentation]
# Beamer theme (e.g., "numpex", "metropolis", "default")
theme = ""

# Aspect ratio: "169" (16:9), "43" (4:3), or "1610" (16:10)
aspect_ratio = "169"

# Optional: color theme (e.g., "crane", "dolphin")
color_theme = ""

# Optional: font theme (e.g., "professionalfonts")
font_theme = ""

# Poster-specific settings (only used when type = "poster")
[poster]
# Poster size: "a0", "a1", "a2", etc.
size = "a0"

# Orientation: "portrait" or "landscape"
orientation = "portrait"

# Number of columns
columns = 3

# Multi-document projects (for projects with multiple LaTeX documents)
[documents]
# Main document to compile
main = "main.tex"

# Additional documents to compile (e.g., poster alongside presentation)
# additional = ["poster.tex"]

# Workflow settings for GitHub Actions
[workflow]
# Runner policy: "github", "self-hosted", or "self-hosted-auto".
runner_policy = "github"
github_runner = "ubuntu-24.04"
self_hosted_label = "self-texlive"
# Self-hosted auto-discovery only runs when this organization is set.
self_hosted_org = ""

# Bibliography policy in generated CI: "off", "check", "update", or "required".
bibliography = "off"

# Release policy in generated CI: "github" or "off".
release = "github"

# Extra artifact path globs to include in generated CI artifacts.
artifact_includes = []

# Output directory for compiled files (empty string means root directory)
# output_dir = "build"

# Directory containing custom fonts (for XeLaTeX compilation)
# fonts_dir = "fonts"

# Whether to install custom fonts in CI environment
# install_fonts = true

# Font installation settings (for XeLaTeX projects)
[fonts]
# Directory to install fonts
directory = "fonts"

# Font sources to download (default: Marianne and Roboto Mono)
# You can customize this list or add your own fonts
# [[fonts.sources]]
# name = "Marianne"
# url = "https://www.systeme-de-design.gouv.fr/uploads/Marianne_fd0ba9c190.zip"
# description = "French government official font"
#
# [[fonts.sources]]
# name = "Roboto Mono"
# url = "https://fonts.google.com/download?family=Roboto+Mono"
# description = "Google's monospace font"

# Theme installation settings (for Beamer presentations)
[themes]
# Directory to install themes (default: current directory)
directory = "."

# Theme sources (default: numpex theme)
# [themes.sources.numpex]
# url = "https://github.com/numpex/presentation.template.d/archive/refs/heads/main.zip"
# description = "NumPEx Beamer theme"
# files = ["beamerthemenumpex.sty", "beamercolorthemenumpex.sty", "beamerfontthemenumpex.sty"]
# typst_files = ["numpex.typ"]
# directories = ["images"]
# requires_fonts = true
# engine = "xelatex"

# Typst compilation settings
[typst]
# Font paths for Typst compiler (relative to project root)
# font_paths = ["fonts/Marianne/desktop", "fonts/Roboto/static"]

# Output directory for Typst builds
# build_dir = "build/typst"
"""

        try:
            with open(path, "w") as f:
                f.write(sample_config)
            print(f"Created sample configuration file: {path}")
            return path
        except Exception as e:
            raise RuntimeError(f"Could not create config file {path}: {e}")

    def __repr__(self) -> str:
        return f"Config(config_file={self.config_file}, sections={list(self._config_data.keys())})"
