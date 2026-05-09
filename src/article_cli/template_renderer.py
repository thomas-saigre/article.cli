"""
Template rendering helpers for generated article repositories.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined

TEMPLATE_VERSION = "1"


@dataclass(frozen=True)
class TemplateWriteResult:
    """Result of rendering a template to disk."""

    path: Path
    status: str


class TemplateRenderer:
    """Render package templates with strict, explicit context."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=PackageLoader("article_cli", "templates"),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
            variable_start_string="[[",
            variable_end_string="]]",
            block_start_string="[%",
            block_end_string="%]",
            comment_start_string="[#",
            comment_end_string="#]",
        )

    def render(self, template_name: str, context: Mapping[str, Any]) -> str:
        """Render a template from package resources."""
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_path(self, template_path: Path, context: Mapping[str, Any]) -> str:
        """Render a user-supplied template from the filesystem."""
        template_path = template_path.expanduser().resolve()
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        env = self.env.overlay(loader=FileSystemLoader(str(template_path.parent)))
        template = env.get_template(template_path.name)
        return template.render(**context)

    def write(
        self,
        template_name: str,
        destination: Path,
        context: Mapping[str, Any],
        force: bool = False,
    ) -> TemplateWriteResult:
        """Render a template to a file using a simple overwrite policy."""
        if destination.exists() and not force:
            return TemplateWriteResult(destination, "skipped")

        existed = destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render(template_name, context), encoding="utf-8")
        return TemplateWriteResult(destination, "overwritten" if existed else "created")
