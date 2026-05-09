"""
Tests for article-cli configuration module
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from article_cli.config import Config

ZOTERO_ENV_VARS = ("ZOTERO_API_KEY", "ZOTERO_USER_ID", "ZOTERO_GROUP_ID")


@pytest.fixture(autouse=True)
def isolate_zotero_environment(monkeypatch):
    """Keep config tests independent from developer or CI Zotero credentials."""
    for var in ZOTERO_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestConfig:
    """Test cases for Config class"""

    def test_init_without_config_file(self):
        """Test Config initialization without config file"""
        config = Config()
        assert config.config_file is None
        assert config._config_data == {}

    def test_get_default_values(self):
        """Test getting configuration with default values"""
        config = Config()

        # Test with no config or env vars
        value = config.get("section", "key", "default_value")
        assert value == "default_value"

    @patch.dict(os.environ, {"TEST_ENV_VAR": "env_value"})
    def test_get_environment_variable_priority(self):
        """Test that environment variables take priority"""
        config = Config()

        value = config.get("section", "key", "default_value", env_var="TEST_ENV_VAR")
        assert value == "env_value"

    def test_get_zotero_config_defaults(self):
        """Test getting Zotero configuration with defaults"""
        config = Config()
        zotero_config = config.get_zotero_config()

        assert zotero_config["api_key"] is None
        assert zotero_config["user_id"] is None
        assert zotero_config["group_id"] is None
        assert zotero_config["output_file"] == "references.bib"

    @patch.dict(os.environ, {"ZOTERO_API_KEY": "test_key", "ZOTERO_GROUP_ID": "12345"})
    def test_get_zotero_config_from_env(self):
        """Test getting Zotero configuration from environment"""
        config = Config()
        zotero_config = config.get_zotero_config()

        assert zotero_config["api_key"] == "test_key"
        assert zotero_config["group_id"] == "12345"

    def test_get_git_config_defaults(self):
        """Test getting Git configuration with defaults"""
        config = Config()
        git_config = config.get_git_config()

        assert git_config["auto_push"] is False
        assert git_config["default_branch"] == "main"

    def test_get_latex_config_defaults(self):
        """Test getting LaTeX configuration with defaults"""
        config = Config()
        latex_config = config.get_latex_config()

        assert isinstance(latex_config["clean_extensions"], list)
        assert ".aux" in latex_config["clean_extensions"]
        assert latex_config["build_dir"] == "."

    def test_create_sample_config(self):
        """Test creating sample configuration file"""
        config = Config()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test-config.toml"
            result_path = config.create_sample_config(config_path)

            assert result_path == config_path
            assert config_path.exists()

            # Check that the file contains expected sections
            content = config_path.read_text()
            assert "[zotero]" in content
            assert "[git]" in content
            assert "[latex]" in content


# Mock argparse.Namespace for testing
class MockArgs:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestValidateZoteroConfig:
    """Test Zotero configuration validation"""

    def test_validate_missing_api_key(self):
        """Test validation fails when API key is missing"""
        config = Config()
        args = MockArgs()

        with pytest.raises(ValueError, match="Zotero API key is required"):
            config.validate_zotero_config(args)

    def test_validate_missing_ids(self):
        """Test validation fails when both user and group IDs are missing"""
        config = Config()
        args = MockArgs(api_key="test_key")

        with pytest.raises(
            ValueError, match="Either Zotero user ID or group ID is required"
        ):
            config.validate_zotero_config(args)

    def test_validate_success_with_group_id(self):
        """Test successful validation with group ID"""
        config = Config()
        args = MockArgs(api_key="test_key", group_id="12345")

        result = config.validate_zotero_config(args)

        assert result["api_key"] == "test_key"
        assert result["group_id"] == "12345"
        assert result["user_id"] is None

    def test_validate_success_with_user_id(self):
        """Test successful validation with user ID"""
        config = Config()
        args = MockArgs(api_key="test_key", user_id="67890")

        result = config.validate_zotero_config(args)

        assert result["api_key"] == "test_key"
        assert result["user_id"] == "67890"
        assert result["group_id"] is None

    @patch.dict(
        os.environ, {"ZOTERO_API_KEY": "env_key", "ZOTERO_GROUP_ID": "env_group"}
    )
    def test_validate_with_env_vars(self):
        """Test validation uses environment variables"""
        config = Config()
        args = MockArgs()

        result = config.validate_zotero_config(args)

        assert result["api_key"] == "env_key"
        assert result["group_id"] == "env_group"

    def test_validate_args_override_env(self):
        """Test that command line args override environment variables"""
        with patch.dict(os.environ, {"ZOTERO_API_KEY": "env_key"}):
            config = Config()
            args = MockArgs(api_key="arg_key", group_id="arg_group")

            result = config.validate_zotero_config(args)

            assert result["api_key"] == "arg_key"
            assert result["group_id"] == "arg_group"
