"""
Read-only project diagnostics command.
"""

import argparse
from typing import Any

from ..config import Config
from ..doctor import DoctorService, print_doctor_report, report_to_json


def add_parser(subparsers: Any) -> None:
    """Register the doctor command parser."""
    parser = subparsers.add_parser(
        "doctor",
        help="Diagnose repository setup, build, bibliography, and release readiness",
    )
    parser.add_argument(
        "document",
        nargs="?",
        help="Main document to check (.tex or .typ). Defaults to project config or auto-detection.",
    )
    parser.add_argument(
        "--engine",
        choices=["latexmk", "pdflatex", "xelatex", "lualatex", "typst"],
        help="Compilation engine to validate. Defaults to project config.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory to validate. Defaults to project config.",
    )
    parser.add_argument(
        "--tag",
        help="Release tag to validate for release readiness.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit stable machine-readable JSON.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the doctor command."""
    report = DoctorService(config).run(
        document=args.document,
        engine=args.engine,
        output_dir=args.output_dir,
        tag=args.tag,
    )

    if args.json:
        print(report_to_json(report))
    else:
        print_doctor_report(report)

    return 0 if report.ok else 1
