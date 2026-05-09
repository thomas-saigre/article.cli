"""
Article CLI - A command-line tool for managing LaTeX and Typst documents

This package provides tools for:
- Git release management with gitinfo2 support
- Zotero bibliography synchronization
- LaTeX and Typst compilation
- Theme installation for presentations
- Git hooks setup
"""

__version__ = "1.5.0"
__author__ = "Christophe Prud'homme"
__email__ = "prudhomm@cemosis.fr"

from .cli import main
from .config import Config
from .zotero import ZoteroBibTexUpdater
from .git_manager import GitManager
from .repository_setup import RepositorySetup
from .latex_compiler import LaTeXCompiler
from .typst_compiler import TypstCompiler

__all__ = [
    "main",
    "Config",
    "ZoteroBibTexUpdater",
    "GitManager",
    "RepositorySetup",
    "LaTeXCompiler",
    "TypstCompiler",
]
