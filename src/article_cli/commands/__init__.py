"""
Command modules for article-cli.
"""

from . import (
    bibtex,
    clean,
    compile,
    config,
    doctor,
    fonts,
    init,
    release,
    setup,
    themes,
)

COMMAND_MODULES = [
    init,
    setup,
    clean,
    compile,
    doctor,
    release,
    bibtex,
    config,
    fonts,
    themes,
]
