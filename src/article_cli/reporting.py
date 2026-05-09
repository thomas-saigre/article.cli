"""
Terminal reporting helpers for article-cli.
"""

import sys


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_success(msg: str) -> None:
    """Print success message in green."""
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str) -> None:
    """Print error message in red."""
    print(f"{Colors.FAIL}✗ Error: {msg}{Colors.ENDC}", file=sys.stderr)


def print_warning(msg: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.WARNING}⚠ Warning: {msg}{Colors.ENDC}")


def print_info(msg: str) -> None:
    """Print info message in cyan."""
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")
