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
        ci_bibliography: str = "off",
        ci_runner_policy: str = "github",
        ci_github_runner: str = "ubuntu-24.04",
        ci_self_hosted_label: str = "self-texlive",
        ci_self_hosted_org: str = "",
        ci_release_policy: str = "github",
        ci_artifact_includes: Optional[List[str]] = None,
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
            ci_bibliography=ci_bibliography,
            ci_runner_policy=ci_runner_policy,
            ci_github_runner=ci_github_runner,
            ci_self_hosted_label=ci_self_hosted_label,
            ci_self_hosted_org=ci_self_hosted_org,
            ci_release_policy=ci_release_policy,
            ci_artifact_includes=ci_artifact_includes,
        )
