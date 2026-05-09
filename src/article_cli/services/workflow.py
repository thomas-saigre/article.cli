"""
Repository workflow setup service.
"""

from pathlib import Path
from typing import List, Optional, Type

from ..repository_setup import RepositorySetup


class WorkflowService:
    """Service boundary for generated repository workflow/config setup."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        setup_cls: Type[RepositorySetup] = RepositorySetup,
    ) -> None:
        self.setup = setup_cls(repo_path) if repo_path is not None else setup_cls()

    def initialize_repository(
        self,
        title: str,
        authors: List[str],
        group_id: str = "4678293",
        force: bool = False,
        main_tex_file: Optional[str] = None,
        project_type: str = "article",
        theme: str = "",
        aspect_ratio: str = "169",
        style: str = "default",
        template: str = "",
        additional_documents: Optional[List[str]] = None,
        output_dir: str = "",
        fonts_dir: str = "",
        install_fonts: bool = False,
    ) -> bool:
        """Initialize a new article repository."""
        return self.setup.init_repository(
            title=title,
            authors=authors,
            group_id=group_id,
            force=force,
            main_tex_file=main_tex_file,
            project_type=project_type,
            theme=theme,
            aspect_ratio=aspect_ratio,
            style=style,
            template=template,
            additional_documents=additional_documents,
            output_dir=output_dir,
            fonts_dir=fonts_dir,
            install_fonts=install_fonts,
        )
