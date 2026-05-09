"""
Tests for article-cli LaTeX compiler module

Tests for Issue #1: XeLaTeX and LuaLaTeX engine support
"""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from article_cli.latex_compiler import LaTeXCompiler
from article_cli.config import Config


class TestLaTeXCompilerEngines:
    """Test cases for LaTeX engine support (Issue #1)"""

    @pytest.fixture
    def compiler(self):
        """Create a LaTeXCompiler instance with default config"""
        config = Config()
        return LaTeXCompiler(config)

    @pytest.fixture
    def mock_tex_path(self, tmp_path):
        """Create a mock .tex file"""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(
            r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        return tex_file

    # --- Test _build_latexmk_command with different pdf_modes ---

    def test_build_latexmk_command_default_pdf(self, compiler, mock_tex_path):
        """Test latexmk command builds with -pdf flag by default"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert "latexmk" in cmd
        assert "-pdf" in cmd
        assert "-xelatex" not in cmd
        assert "-lualatex" not in cmd

    def test_build_latexmk_command_xelatex_mode(self, compiler, mock_tex_path):
        """Test latexmk command builds with -xelatex flag"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=False, output_dir=None, pdf_mode="xelatex"
        )

        assert "latexmk" in cmd
        assert "-xelatex" in cmd
        assert "-pdf" not in cmd
        assert "-lualatex" not in cmd

    def test_build_latexmk_command_lualatex_mode(self, compiler, mock_tex_path):
        """Test latexmk command builds with -lualatex flag"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=False, output_dir=None, pdf_mode="lualatex"
        )

        assert "latexmk" in cmd
        assert "-lualatex" in cmd
        assert "-pdf" not in cmd
        assert "-xelatex" not in cmd

    def test_build_latexmk_command_with_shell_escape(self, compiler, mock_tex_path):
        """Test latexmk command includes --shell-escape when requested"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=True, output_dir=None
        )

        assert "--shell-escape" in cmd

    def test_build_latexmk_command_with_output_dir(self, compiler, mock_tex_path):
        """Test latexmk command includes output directory"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=False, output_dir="build"
        )

        assert "-outdir" in cmd
        assert "build" in cmd

    def test_build_latexmk_command_continuous_mode(self, compiler, mock_tex_path):
        """Test latexmk command includes -pvc for continuous mode"""
        cmd = compiler._build_latexmk_command(
            mock_tex_path, shell_escape=False, output_dir=None, continuous=True
        )

        assert "-pvc" in cmd

    # --- Test _build_xelatex_command ---

    def test_build_xelatex_command_basic(self, compiler, mock_tex_path):
        """Test xelatex command builds correctly"""
        cmd = compiler._build_xelatex_command(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert cmd[0] == "xelatex"
        assert "-synctex=1" in cmd
        assert "-interaction=nonstopmode" in cmd
        assert "-file-line-error" in cmd
        assert str(mock_tex_path) in cmd

    def test_build_xelatex_command_with_shell_escape(self, compiler, mock_tex_path):
        """Test xelatex command includes --shell-escape"""
        cmd = compiler._build_xelatex_command(
            mock_tex_path, shell_escape=True, output_dir=None
        )

        assert "--shell-escape" in cmd

    def test_build_xelatex_command_with_output_dir(self, compiler, mock_tex_path):
        """Test xelatex command includes output directory"""
        cmd = compiler._build_xelatex_command(
            mock_tex_path, shell_escape=False, output_dir="build"
        )

        assert "-output-directory" in cmd
        assert "build" in cmd

    # --- Test _build_lualatex_command ---

    def test_build_lualatex_command_basic(self, compiler, mock_tex_path):
        """Test lualatex command builds correctly"""
        cmd = compiler._build_lualatex_command(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert cmd[0] == "lualatex"
        assert "-synctex=1" in cmd
        assert "-interaction=nonstopmode" in cmd
        assert "-file-line-error" in cmd
        assert str(mock_tex_path) in cmd

    def test_build_lualatex_command_with_shell_escape(self, compiler, mock_tex_path):
        """Test lualatex command includes --shell-escape"""
        cmd = compiler._build_lualatex_command(
            mock_tex_path, shell_escape=True, output_dir=None
        )

        assert "--shell-escape" in cmd

    def test_build_lualatex_command_with_output_dir(self, compiler, mock_tex_path):
        """Test lualatex command includes output directory"""
        cmd = compiler._build_lualatex_command(
            mock_tex_path, shell_escape=False, output_dir="build"
        )

        assert "-output-directory" in cmd
        assert "build" in cmd

    # --- Test _compile_once routing ---

    def test_compile_once_routes_to_latexmk(self, compiler, mock_tex_path):
        """Test that 'latexmk' engine routes to _run_latexmk"""
        with patch.object(compiler, "_run_latexmk", return_value=True) as mock_run:
            result = compiler._compile_once(mock_tex_path, "latexmk", False, None)

            mock_run.assert_called_once_with(mock_tex_path, False, None)
            assert result is True

    def test_compile_once_routes_to_pdflatex(self, compiler, mock_tex_path):
        """Test that 'pdflatex' engine routes to _run_pdflatex"""
        with patch.object(compiler, "_run_pdflatex", return_value=True) as mock_run:
            result = compiler._compile_once(mock_tex_path, "pdflatex", False, None)

            mock_run.assert_called_once_with(mock_tex_path, False, None)
            assert result is True

    def test_compile_once_routes_to_xelatex(self, compiler, mock_tex_path):
        """Test that 'xelatex' engine routes to _run_xelatex"""
        with patch.object(compiler, "_run_xelatex", return_value=True) as mock_run:
            result = compiler._compile_once(mock_tex_path, "xelatex", False, None)

            mock_run.assert_called_once_with(mock_tex_path, False, None)
            assert result is True

    def test_compile_once_routes_to_lualatex(self, compiler, mock_tex_path):
        """Test that 'lualatex' engine routes to _run_lualatex"""
        with patch.object(compiler, "_run_lualatex", return_value=True) as mock_run:
            result = compiler._compile_once(mock_tex_path, "lualatex", False, None)

            mock_run.assert_called_once_with(mock_tex_path, False, None)
            assert result is True

    def test_compile_once_unknown_engine_returns_false(self, compiler, mock_tex_path):
        """Test that unknown engine returns False"""
        result = compiler._compile_once(mock_tex_path, "unknown_engine", False, None)

        assert result is False

    def test_compile_refreshes_gitinfo2_metadata(self, compiler, mock_tex_path):
        """Test compile refreshes gitinfo2 metadata before building"""
        with patch(
            "article_cli.latex_compiler.refresh_gitinfo2_metadata", return_value=True
        ) as refresh_mock, patch.object(
            compiler, "_compile_once", return_value=True
        ) as compile_mock:
            result = compiler.compile(str(mock_tex_path), engine="latexmk")

        refresh_mock.assert_called_once_with(mock_tex_path.parent)
        compile_mock.assert_called_once_with(mock_tex_path, "latexmk", False, None)
        assert result is True

    # --- Test _compile_watch restrictions ---

    def test_compile_watch_rejects_pdflatex(self, compiler, mock_tex_path):
        """Test that watch mode rejects pdflatex engine"""
        result = compiler._compile_watch(mock_tex_path, "pdflatex", False, None)

        assert result is False

    def test_compile_watch_rejects_xelatex(self, compiler, mock_tex_path):
        """Test that watch mode rejects xelatex engine"""
        result = compiler._compile_watch(mock_tex_path, "xelatex", False, None)

        assert result is False

    def test_compile_watch_rejects_lualatex(self, compiler, mock_tex_path):
        """Test that watch mode rejects lualatex engine"""
        result = compiler._compile_watch(mock_tex_path, "lualatex", False, None)

        assert result is False

    # --- Test check_dependencies ---

    def test_check_dependencies_includes_xelatex(self, compiler):
        """Test that dependency check includes xelatex"""
        with patch.object(compiler, "_check_command", return_value=True):
            deps = compiler.check_dependencies()

            assert "xelatex" in deps

    def test_check_dependencies_includes_lualatex(self, compiler):
        """Test that dependency check includes lualatex"""
        with patch.object(compiler, "_check_command", return_value=True):
            deps = compiler.check_dependencies()

            assert "lualatex" in deps

    def test_check_dependencies_all_engines(self, compiler):
        """Test that all expected engines are in dependency check"""
        with patch.object(compiler, "_check_command", return_value=True):
            deps = compiler.check_dependencies()

            expected_tools = ["latexmk", "pdflatex", "xelatex", "lualatex", "bibtex"]
            for tool in expected_tools:
                assert tool in deps, f"Missing tool: {tool}"


class TestLaTeXCompilerCommandExecution:
    """Test actual command execution (with mocking)"""

    @pytest.fixture
    def compiler(self):
        """Create a LaTeXCompiler instance with default config"""
        config = Config()
        return LaTeXCompiler(config)

    @pytest.fixture
    def mock_tex_path(self, tmp_path):
        """Create a mock .tex file"""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(
            r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        return tex_file

    @patch("subprocess.run")
    def test_run_xelatex_success(self, mock_run, compiler, mock_tex_path, tmp_path):
        """Test successful xelatex compilation"""
        # Create mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock pdf content")

        # Mock successful subprocess run
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = compiler._run_xelatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        # Should have been called 3 times (3 passes)
        assert mock_run.call_count == 3
        assert result is True

    @patch("subprocess.run")
    def test_run_lualatex_success(self, mock_run, compiler, mock_tex_path, tmp_path):
        """Test successful lualatex compilation"""
        # Create mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock pdf content")

        # Mock successful subprocess run
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = compiler._run_lualatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        # Should have been called 3 times (3 passes)
        assert mock_run.call_count == 3
        assert result is True

    @patch("subprocess.run")
    def test_run_xelatex_failure(self, mock_run, compiler, mock_tex_path):
        """Test xelatex compilation failure"""
        # Mock failed subprocess run
        mock_run.return_value = MagicMock(returncode=1, stdout="Error!", stderr="")

        result = compiler._run_xelatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert result is False

    @patch("subprocess.run")
    def test_run_lualatex_failure(self, mock_run, compiler, mock_tex_path):
        """Test lualatex compilation failure"""
        # Mock failed subprocess run
        mock_run.return_value = MagicMock(returncode=1, stdout="Error!", stderr="")

        result = compiler._run_lualatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert result is False

    @patch("subprocess.run")
    def test_run_xelatex_timeout(self, mock_run, compiler, mock_tex_path):
        """Test xelatex compilation timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="xelatex", timeout=120)

        result = compiler._run_xelatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert result is False

    @patch("subprocess.run")
    def test_run_lualatex_timeout(self, mock_run, compiler, mock_tex_path):
        """Test lualatex compilation timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="lualatex", timeout=120)

        result = compiler._run_lualatex(
            mock_tex_path, shell_escape=False, output_dir=None
        )

        assert result is False
