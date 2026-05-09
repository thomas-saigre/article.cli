"""
Repository initialization command.
"""

import argparse
from typing import Any

from ..config import Config
from ..reporting import print_error
from ..repository_setup import RepositorySetup
from ..services.workflow import WorkflowService


def add_parser(subparsers: Any) -> None:
    """Register the init command parser."""
    parser = subparsers.add_parser(
        "init", help="Initialize repository with workflows and configuration"
    )
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument(
        "--authors",
        required=True,
        help='Comma-separated list of authors (e.g., "John Doe,Jane Smith")',
    )
    parser.add_argument(
        "--group-id",
        default="4678293",
        help="Zotero group ID (default: 4678293 for article.template)",
    )
    parser.add_argument(
        "--tex-file",
        help="Main .tex or .typ file (auto-detected if not specified)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--type",
        choices=[
            "article",
            "typst-article",
            "presentation",
            "poster",
            "typst-presentation",
            "typst-poster",
        ],
        default="article",
        help=(
            "Project type (default: article). Use 'typst-article' for a Typst "
            "article, 'presentation' for Beamer, and 'typst-presentation' for "
            "Typst slides."
        ),
    )
    parser.add_argument(
        "--theme",
        default="",
        help="Theme for presentations (e.g., 'numpex'). Works with both Beamer and Typst.",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=["169", "43", "1610"],
        default="169",
        help="Aspect ratio for presentations (default: 169 for 16:9).",
    )
    parser.add_argument(
        "--style",
        default="default",
        help=(
            "Built-in article style to use when creating a new source file "
            "(default: default; examples: lncs, ieee)."
        ),
    )
    parser.add_argument(
        "--template",
        default="",
        help=(
            "Path to a custom Jinja2 source template for TeX or Typst articles. "
            "Overrides --style for the generated source file."
        ),
    )
    parser.add_argument(
        "--ci-bib",
        choices=["off", "check", "update", "required"],
        default="off",
        help="Generated CI bibliography policy (default: off).",
    )
    parser.add_argument(
        "--ci-runner-policy",
        choices=["github", "self-hosted", "self-hosted-auto"],
        default="github",
        help="Generated CI runner policy (default: github).",
    )
    parser.add_argument(
        "--ci-github-runner",
        default="ubuntu-24.04",
        help="GitHub-hosted runner for generated CI (default: ubuntu-24.04).",
    )
    parser.add_argument(
        "--ci-self-hosted-label",
        default="self-texlive",
        help="Self-hosted runner label when generated CI opts into it.",
    )
    parser.add_argument(
        "--ci-self-hosted-org",
        default="",
        help="GitHub organization used for opt-in self-hosted runner discovery.",
    )
    parser.add_argument(
        "--ci-release",
        choices=["github", "off"],
        default="github",
        help="Generated CI release policy (default: github).",
    )
    parser.add_argument(
        "--ci-artifact",
        action="append",
        default=[],
        help="Extra artifact path/glob to include in generated CI artifacts.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, config: Config) -> int:
    """Handle the init command."""
    try:
        authors = [a.strip() for a in args.authors.split(",")]

        service = WorkflowService(setup_cls=RepositorySetup)
        return (
            0
            if service.initialize_repository(
                title=args.title,
                authors=authors,
                group_id=args.group_id,
                force=args.force,
                main_tex_file=args.tex_file,
                project_type=args.type,
                theme=args.theme,
                aspect_ratio=args.aspect_ratio,
                style=args.style,
                template=args.template,
                ci_bibliography=args.ci_bib,
                ci_runner_policy=args.ci_runner_policy,
                ci_github_runner=args.ci_github_runner,
                ci_self_hosted_label=args.ci_self_hosted_label,
                ci_self_hosted_org=args.ci_self_hosted_org,
                ci_release_policy=args.ci_release,
                ci_artifact_includes=args.ci_artifact,
            )
            else 1
        )
    except Exception as e:
        print_error(f"Failed to initialize repository: {e}")
        return 1
