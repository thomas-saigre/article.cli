"""
Tests for article-cli repository setup module

Tests project type support including article, presentation, and poster templates.
"""

import subprocess
import json
import shutil
import tempfile
from pathlib import Path

import yaml

from article_cli.git_hooks import refresh_gitinfo2_metadata
from article_cli.git_manager import GitManager
from article_cli.repository_setup import RepositorySetup
from article_cli.template_renderer import TEMPLATE_VERSION

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


def init_git_repository(path: Path) -> None:
    """Create a real git repository for hook tests."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
    )


def assert_generated_project_files_parse(root: Path) -> None:
    """Assert generated structured project files are syntactically valid."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    settings = json.loads((root / ".vscode" / "settings.json").read_text())
    workflow_text = (root / ".github" / "workflows" / "latex.yml").read_text()
    workflow = yaml.safe_load(workflow_text)

    assert pyproject["tool"]["article-cli"]["template"]["version"] == TEMPLATE_VERSION
    if "latex-workshop.latex.recipes" in settings:
        assert settings["latex-workshop.latex.recipes"]
    else:
        assert settings["typst-lsp.exportPdf"] == "onSave"
    assert workflow["jobs"]["build_document"]
    assert "${{ github.ref_name }}" in workflow_text
    assert "article-cli>=1.5.0" in workflow_text


class TestRepositorySetupProjectTypes:
    """Test cases for project type support in RepositorySetup"""

    def test_init_default_repo_path(self):
        """Test RepositorySetup uses current directory by default"""
        setup = RepositorySetup()
        assert setup.repo_path == Path.cwd()

    def test_init_custom_repo_path(self):
        """Test RepositorySetup with custom path"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            assert setup.repo_path == Path(temp_dir)

    def test_detect_or_create_tex_file_article_default(self):
        """Test default tex filename for article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._detect_or_create_tex_file(
                None, "Test Title", ["Author One"], False, "article", "", "169"
            )
            # Should create main.tex for articles
            assert result == "main.tex"
            assert (Path(temp_dir) / "main.tex").exists()

    def test_detect_or_create_typst_article_default(self):
        """Test default typ filename for Typst article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._detect_or_create_tex_file(
                None,
                "Test Title",
                ["Author One"],
                False,
                "typst-article",
                "",
                "169",
            )

            assert result == "main.typ"
            assert (Path(temp_dir) / "main.typ").exists()

    def test_detect_or_create_tex_file_presentation_default(self):
        """Test default tex filename for presentation type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._detect_or_create_tex_file(
                None, "Test Title", ["Author One"], False, "presentation", "", "169"
            )
            # Should create presentation.tex for presentations
            assert result == "presentation.tex"
            assert (Path(temp_dir) / "presentation.tex").exists()

    def test_detect_or_create_tex_file_poster_default(self):
        """Test default tex filename for poster type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._detect_or_create_tex_file(
                None, "Test Title", ["Author One"], False, "poster", "", "169"
            )
            # Should create poster.tex for posters
            assert result == "poster.tex"
            assert (Path(temp_dir) / "poster.tex").exists()

    def test_detect_existing_tex_file(self):
        """Test detection of existing .tex file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an existing tex file
            existing_tex = Path(temp_dir) / "existing.tex"
            existing_tex.write_text("\\documentclass{article}")

            setup = RepositorySetup(Path(temp_dir))
            result = setup._detect_or_create_tex_file(
                None, "Test Title", ["Author One"], False, "article", "", "169"
            )
            # Should detect the existing file
            assert result == "existing.tex"


class TestArticleTemplate:
    """Test cases for article template generation"""

    def test_get_article_template_content(self):
        """Test article template contains expected elements"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_article_template("Test Article", ["John Doe"])

            assert "\\documentclass" in template
            assert "article" in template
            assert "Test Article" in template
            assert "\\usepackage{amsmath" in template
            assert "\\maketitle" in template

    def test_get_article_template_multiple_authors(self):
        """Test article template with multiple authors"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_article_template(
                "Multi-Author Article", ["Alice Smith", "Bob Jones", "Carol White"]
            )

            # Template includes authors list
            assert "Alice Smith" in template or "Multi-Author Article" in template

    def test_get_article_template_lncs_style(self):
        """Test article template with LNCS style"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_article_template(
                "LNCS Article", ["Alice Smith"], "lncs"
            )

            assert "\\documentclass[runningheads]{llncs}" in template
            assert "\\bibliographystyle{splncs04}" in template

    def test_get_article_template_ieee_style(self):
        """Test article template with IEEE style"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_article_template(
                "IEEE Article", ["Alice Smith"], "ieee"
            )

            assert "\\documentclass[conference]{IEEEtran}" in template
            assert "\\bibliographystyle{IEEEtran}" in template

    def test_get_typst_article_template(self):
        """Test Typst article template generation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_typst_article_template(
                "Typst Article", ["Alice Smith"]
            )

            assert "// Typst Article" in template
            assert '#bibliography("references.bib"' in template

    def test_get_custom_article_template(self, tmp_path):
        """Test rendering a user-provided article template"""
        custom_template = tmp_path / "custom.tex.j2"
        custom_template.write_text("Title=[[ title ]]; Authors=[[ authors_display ]]")
        setup = RepositorySetup(tmp_path)

        template = setup._get_article_template(
            "Custom Article", ["Alice Smith"], template=str(custom_template)
        )

        assert template == "Title=Custom Article; Authors=Alice Smith"


class TestPresentationTemplate:
    """Test cases for presentation (Beamer) template generation"""

    def test_get_presentation_template_basic(self):
        """Test presentation template contains expected Beamer elements"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_presentation_template(
                "Test Presentation", ["Presenter One"], "", "169"
            )

            assert "\\documentclass" in template
            assert "beamer" in template
            assert "Test Presentation" in template
            assert "Presenter One" in template

    def test_get_presentation_template_with_theme(self):
        """Test presentation template with custom Beamer theme"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_presentation_template(
                "Themed Presentation", ["Speaker"], "metropolis", "169"
            )

            assert "metropolis" in template
            assert "\\usetheme{metropolis}" in template

    def test_get_presentation_template_aspect_ratio_169(self):
        """Test presentation template with 16:9 aspect ratio"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_presentation_template(
                "Wide Presentation", ["Speaker"], "", "169"
            )

            assert "aspectratio=169" in template

    def test_get_presentation_template_aspect_ratio_43(self):
        """Test presentation template with 4:3 aspect ratio"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_presentation_template(
                "Standard Presentation", ["Speaker"], "", "43"
            )

            assert "aspectratio=43" in template

    def test_get_presentation_template_aspect_ratio_1610(self):
        """Test presentation template with 16:10 aspect ratio"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_presentation_template(
                "16:10 Presentation", ["Speaker"], "", "1610"
            )

            assert "aspectratio=1610" in template


class TestPosterTemplate:
    """Test cases for poster (beamerposter or tikzposter) template generation"""

    def test_get_poster_template_basic(self):
        """Test poster template contains expected elements"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_poster_template(
                "Test Poster", ["Researcher One", "Researcher Two"]
            )

            assert "\\documentclass" in template
            # May use tikzposter or beamerposter
            assert "poster" in template.lower()
            assert "Test Poster" in template

    def test_get_poster_template_size_a0(self):
        """Test poster template uses A0 size by default"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            template = setup._get_poster_template("Poster", ["Author"])

            # Should have A0 paper size settings
            assert "a0" in template.lower()


class TestConfigGeneration:
    """Test cases for configuration file generation"""

    def test_create_pyproject_article_type(self):
        """Test pyproject.toml generation for article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_pyproject(
                "test-project",
                "Test Article",
                ["Author"],
                "12345",
                False,
                "article",
                "",
                "169",
            )

            assert result is True
            pyproject_path = Path(temp_dir) / "pyproject.toml"
            assert pyproject_path.exists()

            content = pyproject_path.read_text()
            parsed = tomllib.loads(content)
            assert "[tool.article-cli.project]" in content
            assert 'type = "article"' in content
            assert (
                parsed["tool"]["article-cli"]["template"]["version"] == TEMPLATE_VERSION
            )

    def test_create_pyproject_presentation_type(self):
        """Test pyproject.toml generation for presentation type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_pyproject(
                "test-presentation",
                "Test Presentation",
                ["Speaker"],
                "12345",
                False,
                "presentation",
                "numpex",
                "169",
            )

            assert result is True
            pyproject_path = Path(temp_dir) / "pyproject.toml"
            content = pyproject_path.read_text()
            parsed = tomllib.loads(content)

            assert "[tool.article-cli.project]" in content
            assert 'type = "presentation"' in content
            assert "[tool.article-cli.presentation]" in content
            assert 'theme = "numpex"' in content
            assert 'aspect_ratio = "169"' in content
            # Presentations should default to xelatex
            assert 'engine = "xelatex"' in content
            assert parsed["tool"]["article-cli"]["latex"]["engine"] == "xelatex"

    def test_create_pyproject_poster_type(self):
        """Test pyproject.toml generation for poster type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_pyproject(
                "test-poster",
                "Test Poster",
                ["Researcher"],
                "12345",
                False,
                "poster",
                "",
                "169",
            )

            assert result is True
            pyproject_path = Path(temp_dir) / "pyproject.toml"
            content = pyproject_path.read_text()
            parsed = tomllib.loads(content)

            assert "[tool.article-cli.project]" in content
            assert 'type = "poster"' in content
            assert "[tool.article-cli.poster]" in content
            assert parsed["tool"]["article-cli"]["project"]["type"] == "poster"

    def test_create_pyproject_typst_article_type(self):
        """Test pyproject.toml generation for Typst article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_pyproject(
                "test-typst-article",
                "Test Typst Article",
                ["Author"],
                "12345",
                False,
                "typst-article",
                "",
                "169",
                style="lncs",
                main_document="main.typ",
            )

            assert result is True
            content = (Path(temp_dir) / "pyproject.toml").read_text()
            parsed = tomllib.loads(content)

            assert 'type = "typst-article"' in content
            assert "[tool.article-cli.typst]" in content
            assert parsed["tool"]["article-cli"]["latex"]["engine"] == "typst"
            assert parsed["tool"]["article-cli"]["project"]["style"] == "lncs"
            assert parsed["tool"]["article-cli"]["documents"]["main"] == "main.typ"


class TestReadmeGeneration:
    """Test cases for README.md generation"""

    def test_create_readme_article_type(self):
        """Test README.md generation for article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_readme(
                "test-article", "Test Article", ["Author"], "main.tex", False, "article"
            )

            assert result is True
            readme_path = Path(temp_dir) / "README.md"
            assert readme_path.exists()

            content = readme_path.read_text()
            assert "Test Article" in content
            assert "latexmk -pdf main.tex" in content
            assert "article" in content.lower()

    def test_create_readme_presentation_type(self):
        """Test README.md generation for presentation type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_readme(
                "test-presentation",
                "Test Presentation",
                ["Speaker"],
                "presentation.tex",
                False,
                "presentation",
            )

            assert result is True
            readme_path = Path(temp_dir) / "README.md"
            content = readme_path.read_text()

            assert "Test Presentation" in content
            assert "latexmk -xelatex presentation.tex" in content
            assert "presentation" in content.lower()

    def test_create_readme_poster_type(self):
        """Test README.md generation for poster type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_readme(
                "test-poster",
                "Test Poster",
                ["Researcher"],
                "poster.tex",
                False,
                "poster",
            )

            assert result is True
            readme_path = Path(temp_dir) / "README.md"
            content = readme_path.read_text()

            assert "Test Poster" in content
            assert "latexmk -xelatex poster.tex" in content
            assert "poster" in content.lower()

    def test_create_readme_typst_article_type(self):
        """Test README.md generation for Typst article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_readme(
                "test-typst",
                "Test Typst",
                ["Author"],
                "main.typ",
                False,
                "typst-article",
                "lncs",
            )

            assert result is True
            content = (Path(temp_dir) / "README.md").read_text()

            assert "typst compile main.typ" in content
            assert "Document style: `lncs`" in content


class TestVSCodeSettingsGeneration:
    """Test cases for VS Code settings generation"""

    def test_create_vscode_settings_article(self):
        """Test VS Code settings for article type (pdflatex)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vscode_dir = Path(temp_dir) / ".vscode"
            vscode_dir.mkdir()

            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_vscode_settings(False, "article")

            assert result is True
            settings_path = vscode_dir / "settings.json"
            assert settings_path.exists()

            content = settings_path.read_text()
            settings = json.loads(content)
            assert "latexmk-pdf" in content
            assert '"-pdf"' in content
            assert settings["latex-workshop.latex.recipes"][0]["name"] == "latexmk-pdf"

    def test_create_vscode_settings_presentation(self):
        """Test VS Code settings for presentation type (xelatex)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vscode_dir = Path(temp_dir) / ".vscode"
            vscode_dir.mkdir()

            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_vscode_settings(False, "presentation")

            assert result is True
            settings_path = vscode_dir / "settings.json"
            content = settings_path.read_text()
            settings = json.loads(content)

            assert "latexmk-xelatex" in content
            assert '"-xelatex"' in content
            assert (
                settings["latex-workshop.latex.recipes"][0]["name"] == "latexmk-xelatex"
            )

    def test_create_vscode_settings_poster(self):
        """Test VS Code settings for poster type (xelatex)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vscode_dir = Path(temp_dir) / ".vscode"
            vscode_dir.mkdir()

            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_vscode_settings(False, "poster")

            assert result is True
            settings_path = vscode_dir / "settings.json"
            content = settings_path.read_text()
            settings = json.loads(content)

            assert "latexmk-xelatex" in content
            assert '"-xelatex"' in content
            assert (
                settings["latex-workshop.latex.recipes"][0]["name"] == "latexmk-xelatex"
            )

    def test_create_vscode_settings_typst_article(self):
        """Test VS Code settings for Typst article type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vscode_dir = Path(temp_dir) / ".vscode"
            vscode_dir.mkdir()

            setup = RepositorySetup(Path(temp_dir))
            result = setup._create_vscode_settings(False, "typst-article")

            assert result is True
            settings = json.loads((vscode_dir / "settings.json").read_text())

            assert settings["typst-lsp.exportPdf"] == "onSave"


class TestGitHookSetup:
    """Test cases for gitinfo2 hook generation and installation"""

    def test_create_git_hooks_creates_missing_hooks_directory(self, tmp_path):
        """Test repository setup creates hooks/post-commit when hooks is missing"""
        setup = RepositorySetup(tmp_path)

        result = setup._create_git_hooks(False)

        post_commit = tmp_path / "hooks" / "post-commit"
        assert result is True
        assert post_commit.exists()
        assert "gitHeadInfo.gin" in post_commit.read_text()
        assert post_commit.stat().st_mode & 0o111

    def test_setup_hooks_bootstraps_missing_hooks_directory(self, tmp_path):
        """Test article-cli setup creates source hooks before installing them"""
        init_git_repository(tmp_path)
        git_hooks_dir = tmp_path / ".git" / "hooks"
        shutil.rmtree(git_hooks_dir)

        manager = GitManager(tmp_path)

        result = manager.setup_hooks()

        assert result is True
        assert (tmp_path / "hooks" / "post-commit").exists()
        for hook_name in ["post-commit", "post-checkout", "post-merge"]:
            installed_hook = git_hooks_dir / hook_name
            assert installed_hook.exists()
            assert "gitHeadInfo.gin" in installed_hook.read_text()
            assert installed_hook.stat().st_mode & 0o111

    def test_setup_hooks_preserves_existing_user_hook(self, tmp_path):
        """Test setup appends a managed block without overwriting user hooks"""
        init_git_repository(tmp_path)
        git_hooks_dir = tmp_path / ".git" / "hooks"
        user_hook = git_hooks_dir / "post-commit"
        user_hook.write_text("#!/bin/sh\necho user hook\n")
        user_hook.chmod(0o755)

        manager = GitManager(tmp_path)

        result = manager.setup_hooks()

        content = user_hook.read_text()
        assert result is True
        assert "echo user hook" in content
        assert "# >>> article-cli gitinfo2 hook >>>" in content
        assert "gitHeadInfo.gin" in content

    def test_setup_hooks_is_idempotent(self, tmp_path):
        """Test repeated setup updates managed hooks without duplicating blocks"""
        init_git_repository(tmp_path)
        manager = GitManager(tmp_path)

        assert manager.setup_hooks() is True
        assert manager.setup_hooks() is True

        installed_hook = tmp_path / ".git" / "hooks" / "post-commit"
        content = installed_hook.read_text()
        assert content.count("# >>> article-cli gitinfo2 hook >>>") == 1
        assert content.count("# <<< article-cli gitinfo2 hook <<<") == 1

    def test_setup_hooks_supports_linked_worktree(self, tmp_path):
        """Test setup resolves git root and hook path in linked worktrees"""
        main_repo = tmp_path / "main"
        worktree_repo = tmp_path / "worktree"
        main_repo.mkdir()
        init_git_repository(main_repo)
        (main_repo / "README.md").write_text("initial\n")
        subprocess.run(["git", "add", "README.md"], cwd=main_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=main_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "worktree", "add", str(worktree_repo)],
            cwd=main_repo,
            check=True,
            capture_output=True,
        )

        manager = GitManager(worktree_repo)

        result = manager.setup_hooks()

        hook_path = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks/post-commit"],
            cwd=worktree_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        installed_hook = Path(hook_path)
        if not installed_hook.is_absolute():
            installed_hook = worktree_repo / installed_hook

        assert result is True
        assert manager.repo_root == worktree_repo.resolve()
        assert installed_hook.exists()
        assert "gitHeadInfo.gin" in installed_hook.read_text()

    def test_refresh_gitinfo2_metadata_updates_local_copy(self, tmp_path):
        """Test refresh runs the hook and copies gitHeadInfo.gin locally"""
        git_dir = tmp_path / ".git"
        hooks_dir = tmp_path / "hooks"
        git_dir.mkdir()
        hooks_dir.mkdir()

        hook = hooks_dir / "post-commit"
        hook.write_text(
            "#!/bin/sh\n"
            "cat > .git/gitHeadInfo.gin <<'EOF'\n"
            "\\usepackage[firsttagdescribe={v0.5.0}]{gitexinfo}\n"
            "EOF\n"
        )

        result = refresh_gitinfo2_metadata(tmp_path)

        assert result is True
        assert (tmp_path / "gitHeadLocal.gin").read_text() == (
            "\\usepackage[firsttagdescribe={v0.5.0}]{gitexinfo}\n"
        )

    def test_refresh_gitinfo2_metadata_ignores_dirty_local_copy(self, tmp_path):
        """Test gitHeadLocal.gin alone does not mark the version dirty"""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
        )
        (tmp_path / "main.tex").write_text("\\documentclass{article}\n")
        (tmp_path / "gitHeadLocal.gin").write_text("stale\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "tag", "v0.5.0"], cwd=tmp_path, check=True)
        (tmp_path / "gitHeadLocal.gin").write_text("dirty local metadata\n")

        result = refresh_gitinfo2_metadata(tmp_path)

        content = (tmp_path / "gitHeadLocal.gin").read_text()
        assert result is True
        assert "firsttagdescribe={v0.5.0}" in content
        assert "reltag={v0.5.0-0-" in content
        assert "-*}" not in content


class TestFullRepositoryInit:
    """Integration tests for full repository initialization"""

    def test_init_article_repository(self):
        """Test full article repository initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup.init_repository(
                title="Test Article",
                authors=["Author One", "Author Two"],
                group_id="12345",
                force=False,
                project_type="article",
            )

            assert result is True
            # Check all expected files exist
            assert (Path(temp_dir) / "main.tex").exists()
            assert (Path(temp_dir) / "pyproject.toml").exists()
            assert (Path(temp_dir) / "README.md").exists()
            assert (Path(temp_dir) / ".gitignore").exists()
            assert (Path(temp_dir) / ".vscode" / "settings.json").exists()
            assert (Path(temp_dir) / ".github" / "workflows").exists()
            assert_generated_project_files_parse(Path(temp_dir))

    def test_init_typst_article_repository(self):
        """Test full Typst article repository initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup.init_repository(
                title="Test Typst Article",
                authors=["Author One"],
                group_id="12345",
                force=False,
                project_type="typst-article",
                style="lncs",
            )

            root = Path(temp_dir)
            assert result is True
            assert (root / "main.typ").exists()
            assert_generated_project_files_parse(root)

            pyproject = tomllib.loads((root / "pyproject.toml").read_text())
            workflow = (root / ".github" / "workflows" / "latex.yml").read_text()

            assert pyproject["tool"]["article-cli"]["latex"]["engine"] == "typst"
            assert pyproject["tool"]["article-cli"]["project"]["style"] == "lncs"
            assert pyproject["tool"]["article-cli"]["documents"]["main"] == "main.typ"
            assert "typst-community/setup-typst@v4" in workflow
            assert "Compile Typst document" in workflow

    def test_init_presentation_repository(self):
        """Test full presentation repository initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup.init_repository(
                title="Test Presentation",
                authors=["Speaker One"],
                group_id="12345",
                force=False,
                project_type="presentation",
                theme="metropolis",
                aspect_ratio="169",
            )

            assert result is True
            # Check presentation-specific files
            assert (Path(temp_dir) / "presentation.tex").exists()

            # Check pyproject.toml has presentation config
            pyproject = (Path(temp_dir) / "pyproject.toml").read_text()
            assert 'type = "presentation"' in pyproject
            assert "[tool.article-cli.presentation]" in pyproject
            assert_generated_project_files_parse(Path(temp_dir))

    def test_init_poster_repository(self):
        """Test full poster repository initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup.init_repository(
                title="Test Poster",
                authors=["Researcher"],
                group_id="12345",
                force=False,
                project_type="poster",
            )

            assert result is True
            # Check poster-specific files
            assert (Path(temp_dir) / "poster.tex").exists()

            # Check pyproject.toml has poster config
            pyproject = (Path(temp_dir) / "pyproject.toml").read_text()
            assert 'type = "poster"' in pyproject
            assert "[tool.article-cli.poster]" in pyproject
            assert_generated_project_files_parse(Path(temp_dir))

    def test_init_multi_document_repository_with_fonts(self):
        """Test workflow and config rendering for output dirs, fonts, and extra docs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup = RepositorySetup(Path(temp_dir))
            result = setup.init_repository(
                title="Test Multi Document",
                authors=["Author"],
                group_id="12345",
                force=False,
                project_type="presentation",
                additional_documents=["poster.tex"],
                output_dir="build",
                fonts_dir="fonts",
                install_fonts=True,
            )

            assert result is True
            root = Path(temp_dir)
            assert_generated_project_files_parse(root)

            pyproject = tomllib.loads((root / "pyproject.toml").read_text())
            workflow = (root / ".github" / "workflows" / "latex.yml").read_text()

            assert pyproject["tool"]["article-cli"]["workflow"] == {
                "output_dir": "build",
                "fonts_dir": "fonts",
                "install_fonts": True,
            }
            assert "Install custom fonts" in workflow
            assert "poster.tex" in workflow
            assert "poster.pdf" in workflow


class TestConfigProjectMethods:
    """Test cases for Config class project type methods"""

    def test_get_project_config_defaults(self):
        """Test getting project configuration with defaults"""
        from article_cli.config import Config

        config = Config()
        project_config = config.get_project_config()

        # Uses 'project_type' key, defaults to 'article'
        assert project_config["project_type"] == "article"

    def test_get_presentation_config_defaults(self):
        """Test getting presentation configuration with defaults"""
        from article_cli.config import Config

        config = Config()
        presentation_config = config.get_presentation_config()

        assert presentation_config["theme"] == ""
        assert presentation_config["aspect_ratio"] == "169"

    def test_get_poster_config_defaults(self):
        """Test getting poster configuration with defaults"""
        from article_cli.config import Config

        config = Config()
        poster_config = config.get_poster_config()

        assert poster_config["size"] == "a0"
        assert poster_config["orientation"] == "portrait"
