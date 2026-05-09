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
    version,
)

COMMAND_MODULES = [
    init,
    setup,
    clean,
    compile,
    doctor,
    version,
    release,
    bibtex,
    config,
    fonts,
    themes,
]
