"""
Tests for article-cli Typst compiler module
"""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from article_cli.typst_compiler import TypstCompiler
from article_cli.config import Config


class TestTypstCompilerInit:
    """Test cases for TypstCompiler initialization"""

    def test_init_with_default_config(self):
        """Test TypstCompiler initializes with default config"""
        config = Config()
        compiler = TypstCompiler(config)

        assert compiler.config == config
        assert compiler.typst_config is not None

    def test_init_loads_typst_config(self):
        """Test TypstCompiler loads Typst-specific config"""
        config = Config()
        compiler = TypstCompiler(config)

        # Should have font_paths and build_dir from config
        assert "font_paths" in compiler.typst_config
        assert "build_dir" in compiler.typst_config


class TestTypstCompilerCommands:
    """Test cases for Typst command building"""

    @pytest.fixture
    def compiler(self):
        """Create a TypstCompiler instance with default config"""
        config = Config()
        return TypstCompiler(config)

    @pytest.fixture
    def mock_typ_path(self, tmp_path):
        """Create a mock .typ file"""
        typ_file = tmp_path / "test.typ"
        typ_file.write_text('#set page(paper: "a4")\nHello World')
        return typ_file

    # --- Test _build_compile_command ---

    def test_build_compile_command_basic(self, compiler, mock_typ_path):
        """Test basic typst compile command"""
        cmd = compiler._build_compile_command(mock_typ_path, None, [])

        assert cmd[0] == "typst"
        assert cmd[1] == "compile"
        assert str(mock_typ_path) in cmd

    def test_build_compile_command_with_font_paths(self, compiler, mock_typ_path):
        """Test typst compile command with font paths"""
        font_paths = ["fonts/Marianne", "fonts/Roboto"]
        cmd = compiler._build_compile_command(mock_typ_path, None, font_paths)

        assert "--font-path" in cmd
        assert "fonts/Marianne" in cmd
        assert "fonts/Roboto" in cmd

    def test_build_compile_command_with_output_dir(self, compiler, mock_typ_path):
        """Test typst compile command with output directory"""
        cmd = compiler._build_compile_command(mock_typ_path, "build/typst", [])

        # Should include output path
        assert any("build/typst" in str(arg) for arg in cmd)

    def test_build_compile_command_multiple_font_paths(self, compiler, mock_typ_path):
        """Test typst compile command with multiple font paths"""
        font_paths = ["fonts/A", "fonts/B", "fonts/C"]
        cmd = compiler._build_compile_command(mock_typ_path, None, font_paths)

        # Count --font-path occurrences
        font_path_count = cmd.count("--font-path")
        assert font_path_count == 3

    # --- Test _build_watch_command ---

    def test_build_watch_command_basic(self, compiler, mock_typ_path):
        """Test basic typst watch command"""
        cmd = compiler._build_watch_command(mock_typ_path, None, [])

        assert cmd[0] == "typst"
        assert cmd[1] == "watch"
        assert str(mock_typ_path) in cmd

    def test_build_watch_command_with_font_paths(self, compiler, mock_typ_path):
        """Test typst watch command with font paths"""
        font_paths = ["fonts/Marianne"]
        cmd = compiler._build_watch_command(mock_typ_path, None, font_paths)

        assert "--font-path" in cmd
        assert "fonts/Marianne" in cmd

    def test_build_watch_command_with_output_dir(self, compiler, mock_typ_path):
        """Test typst watch command with output directory"""
        cmd = compiler._build_watch_command(mock_typ_path, "build", [])

        # Should include output path
        assert any("build" in str(arg) for arg in cmd)


class TestTypstCompilerCompilation:
    """Test cases for Typst compilation"""

    @pytest.fixture
    def compiler(self):
        """Create a TypstCompiler instance with default config"""
        config = Config()
        return TypstCompiler(config)

    @pytest.fixture
    def mock_typ_path(self, tmp_path):
        """Create a mock .typ file"""
        typ_file = tmp_path / "test.typ"
        typ_file.write_text('#set page(paper: "a4")\nHello World')
        return typ_file

    def test_compile_nonexistent_file(self, compiler, tmp_path):
        """Test compiling a file that doesn't exist"""
        result = compiler.compile(str(tmp_path / "nonexistent.typ"))
        assert result is False

    @patch("subprocess.run")
    def test_compile_once_success(self, mock_run, compiler, mock_typ_path, tmp_path):
        """Test successful Typst compilation"""
        # Create mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock pdf content")

        # Mock successful subprocess run
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = compiler._compile_once(mock_typ_path, None, [])

        mock_run.assert_called_once()
        assert result is True

    @patch("subprocess.run")
    def test_compile_once_failure(self, mock_run, compiler, mock_typ_path):
        """Test Typst compilation failure"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="Error!", stderr="Compilation failed"
        )

        result = compiler._compile_once(mock_typ_path, None, [])

        assert result is False

    @patch("subprocess.run")
    def test_compile_once_timeout(self, mock_run, compiler, mock_typ_path):
        """Test Typst compilation timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="typst", timeout=120)

        result = compiler._compile_once(mock_typ_path, None, [])

        assert result is False

    @patch("subprocess.run")
    def test_compile_once_typst_not_found(self, mock_run, compiler, mock_typ_path):
        """Test Typst not installed"""
        mock_run.side_effect = FileNotFoundError()

        result = compiler._compile_once(mock_typ_path, None, [])

        assert result is False

    @patch("subprocess.run")
    def test_compile_with_font_paths(self, mock_run, compiler, mock_typ_path, tmp_path):
        """Test compilation with custom font paths"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock pdf content")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = compiler.compile(
            str(mock_typ_path), font_paths=["fonts/custom"], watch=False
        )

        # Check that font path was included in command
        call_args = mock_run.call_args[0][0]
        assert "--font-path" in call_args
        assert "fonts/custom" in call_args
        assert result is True


class TestTypstCompilerDependencies:
    """Test cases for dependency checking"""

    @pytest.fixture
    def compiler(self):
        """Create a TypstCompiler instance with default config"""
        config = Config()
        return TypstCompiler(config)

    def test_check_dependencies_structure(self, compiler):
        """Test dependency check returns expected structure"""
        with patch.object(compiler, "_check_command", return_value=True):
            deps = compiler.check_dependencies()

            assert "typst" in deps

    @patch("subprocess.run")
    def test_check_command_available(self, mock_run, compiler):
        """Test _check_command when command is available"""
        mock_run.return_value = MagicMock(returncode=0)

        result = compiler._check_command("typst")

        assert result is True

    @patch("subprocess.run")
    def test_check_command_not_found(self, mock_run, compiler):
        """Test _check_command when command is not found"""
        mock_run.side_effect = FileNotFoundError()

        result = compiler._check_command("typst")

        assert result is False

    @patch("subprocess.run")
    def test_check_command_timeout(self, mock_run, compiler):
        """Test _check_command when command times out"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="typst", timeout=10)

        result = compiler._check_command("typst")

        assert result is False


class TestTypstCompilerIntegration:
    """Integration tests for TypstCompiler"""

    @pytest.fixture
    def compiler(self):
        """Create a TypstCompiler instance with default config"""
        config = Config()
        return TypstCompiler(config)

    @pytest.fixture
    def mock_typ_file(self, tmp_path):
        """Create a mock .typ file"""
        typ_file = tmp_path / "presentation.typ"
        typ_file.write_text(
            """
#set page(paper: "presentation-16-9")
#set text(size: 24pt)

= Title Slide

Hello, World!
"""
        )
        return typ_file

    def test_compile_merges_config_font_paths(self, tmp_path):
        """Test that compile merges font paths from config and arguments"""
        # Create a config with font paths
        config = Config()

        # Patch get_typst_config to return font paths
        with patch.object(
            config,
            "get_typst_config",
            return_value={"font_paths": ["fonts/A"], "build_dir": ""},
        ):
            compiler = TypstCompiler(config)

            typ_file = tmp_path / "test.typ"
            typ_file.write_text('#set page(paper: "a4")\nTest')

            with patch.object(
                compiler, "_compile_once", return_value=True
            ) as mock_compile:
                compiler.compile(str(typ_file), font_paths=["fonts/B"])

                # Should have been called with merged font paths
                call_args = mock_compile.call_args
                font_paths_arg = call_args[0][2]  # Third positional argument
                assert "fonts/A" in font_paths_arg
                assert "fonts/B" in font_paths_arg
