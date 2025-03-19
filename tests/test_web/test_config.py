"""Test the Tidy3D configuration system."""

import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from tidy3d.config import (
    CONFIG_PATHS,
    DEFAULT_CONFIG_FILE,
    READ_CONFIG_PATHS,
    Tidy3dConfig,
    _parse_legacy_format,
    yaml_config_settings_source,
)


def test_config_defaults():
    """Test that the default configuration values are set correctly."""
    # Create a temporary config with defaults
    with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
        config = Tidy3dConfig()

        assert config.apikey is None
        assert config.ssl_verify is True
        assert config.log_suppression is True


def test_config_env_override():
    """Test that environment variables override defaults."""
    # Set environment variables
    os.environ["SIMCLOUD_APIKEY"] = "test_key_from_env"
    os.environ["TIDY3D_SSL_VERIFY"] = "False"

    try:
        # Create a new config (should pick up env vars)
        with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
            config = Tidy3dConfig()

            assert config.apikey == "test_key_from_env"
            assert config.ssl_verify is False
    finally:
        # Clean up environment to avoid affecting other tests
        del os.environ["SIMCLOUD_APIKEY"]
        del os.environ["TIDY3D_SSL_VERIFY"]


def test_config_save_load():
    """Test saving and loading configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "config"

        # Create and save config
        with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
            config = Tidy3dConfig(apikey="test_save_key", ssl_verify=False)
            config.save(temp_config_path)

        # Verify the file exists and has correct content
        assert temp_config_path.exists()
        with open(temp_config_path) as f:
            yaml_content = yaml.safe_load(f)

        assert yaml_content["apikey"] == "test_save_key"
        assert yaml_content["ssl_verify"] is False

        # Create a new config and load from the file
        with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
            new_config = Tidy3dConfig()
            new_config.load(temp_config_path)

            assert new_config.apikey == "test_save_key"
            assert new_config.ssl_verify is False


def test_legacy_format_parsing():
    """Test parsing legacy format config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "config"

        # Write a legacy format config
        with open(temp_config_path, "w") as f:
            f.write('apikey = "legacy_test_key"')

        # Test the parser function directly
        with open(temp_config_path) as f:
            content = f.read()

        parsed = _parse_legacy_format(content)
        assert parsed["apikey"] == "legacy_test_key"

        # Patch the settings source to use our file
        def mock_yaml_source(settings):
            with open(temp_config_path) as f:
                content = f.read()
            return _parse_legacy_format(content)

        with patch("tidy3d.config.yaml_config_settings_source", side_effect=mock_yaml_source):
            config = Tidy3dConfig()
            assert config.apikey == "legacy_test_key"

        # Save it and verify it's now in YAML format
        with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
            config = Tidy3dConfig(apikey="legacy_test_key")
            config.save(temp_config_path)

        with open(temp_config_path) as f:
            content = f.read()

        assert "apikey: legacy_test_key" in content
        assert "=" not in content  # No more legacy format


def test_validation():
    """Test that configuration validation works."""
    # Test setting invalid logging level (should raise ValidationError)
    with patch("tidy3d.config.yaml_config_settings_source", return_value={}):
        config = Tidy3dConfig()

        with pytest.raises(ValueError):
            config.logging_level = "INVALID_LEVEL"


def test_config_paths():
    """Test the config paths are correct for each platform."""
    home = Path.home()

    # Legacy path
    legacy_path = home / ".tidy3d" / "config"
    assert str(CONFIG_PATHS["legacy"]) == str(legacy_path)

    # XDG path depends on platform
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        expected_xdg_path = appdata / "tidy3d" / "config"
    else:
        expected_xdg_path = home / ".config" / "tidy3d" / "config"

    assert str(CONFIG_PATHS["xdg"]) == str(expected_xdg_path)

    # Default config file should be XDG path
    assert str(DEFAULT_CONFIG_FILE) == str(expected_xdg_path)

    # Read paths should have legacy first, then XDG
    assert str(READ_CONFIG_PATHS[0]) == str(legacy_path)
    assert str(READ_CONFIG_PATHS[1]) == str(expected_xdg_path)


def test_yaml_config_settings_source():
    """Test the YAML settings source with multiple config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create temporary config paths
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_dir.mkdir()
        legacy_path = legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_dir.mkdir()
        xdg_path = xdg_dir / "config"

        # Mock READ_CONFIG_PATHS to point to our temp paths
        mock_paths = [legacy_path, xdg_path]

        # Case 1: Only XDG file exists
        with open(xdg_path, "w") as f:
            yaml.safe_dump({"apikey": "xdg_key"}, f)

        with patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths):
            # Check the settings source directly
            config_dict = yaml_config_settings_source(None)
            assert config_dict.get("apikey") == "xdg_key"

        # Case 2: Both exist, legacy should have precedence
        with open(legacy_path, "w") as f:
            yaml.safe_dump({"apikey": "legacy_key"}, f)

        with patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths):
            # Check the settings source directly
            config_dict = yaml_config_settings_source(None)
            assert config_dict.get("apikey") == "legacy_key"

        # Case 3: Legacy has apikey, XDG has ssl_verify - both should be included
        with open(legacy_path, "w") as f:
            yaml.safe_dump({"apikey": "legacy_key"}, f)

        with open(xdg_path, "w") as f:
            yaml.safe_dump({"ssl_verify": False}, f)

        with patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths):
            # Check the settings source directly
            config_dict = yaml_config_settings_source(None)
            assert config_dict.get("apikey") == "legacy_key"
            assert config_dict.get("ssl_verify") is False

        # Case 4: Both have same key, legacy should win
        with open(legacy_path, "w") as f:
            yaml.safe_dump({"ssl_verify": True}, f)

        with open(xdg_path, "w") as f:
            yaml.safe_dump({"ssl_verify": False}, f)

        with patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths):
            # Check the settings source directly
            config_dict = yaml_config_settings_source(None)
            assert config_dict.get("ssl_verify") is True


def test_legacy_format_conversion():
    """Test conversion of legacy format to YAML without location migration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create paths that mimic our real ones
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_dir.mkdir()
        legacy_path = legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_dir.mkdir()
        xdg_path = xdg_dir / "config"

        # Mock config paths
        mock_config_paths = {"legacy": legacy_path, "xdg": xdg_path}
        mock_read_paths = [legacy_path, xdg_path]

        # Create a legacy format file in the legacy location
        with open(legacy_path, "w") as f:
            f.write('apikey = "conversion_test_key"\nssl_verify = "False"')

        # Call the settings source function with our mocked paths
        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_read_paths),
        ):
            # This should trigger the conversion
            config_dict = yaml_config_settings_source(None)

            # Verify the function returned the correct values
            assert config_dict.get("apikey") == "conversion_test_key"
            assert config_dict.get("ssl_verify") == "False"  # Still a string at this point

            # Verify the legacy file was converted to YAML format
            with open(legacy_path) as f:
                legacy_content = f.read()

            assert "apikey: conversion_test_key" in legacy_content
            assert "ssl_verify: 'False'" in legacy_content
            assert "=" not in legacy_content

            # Verify the file was NOT migrated to XDG location
            assert not xdg_path.exists()


def test_default_save_location():
    """Test that save() uses the correct default location."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock paths
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_path = legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_path = xdg_dir / "config"

        mock_config_paths = {"legacy": legacy_path, "xdg": xdg_path}

        # Case 1: No existing config - should save to XDG location
        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.DEFAULT_CONFIG_FILE", xdg_path),
            patch("tidy3d.config.yaml_config_settings_source", return_value={}),
        ):
            # Create and save a config
            config = Tidy3dConfig(apikey="xdg_save_test")
            config.save()

            # Verify it was saved to XDG path
            assert xdg_path.exists()
            with open(xdg_path) as f:
                content = yaml.safe_load(f)

            assert content["apikey"] == "xdg_save_test"

            # Legacy path should not exist
            assert not legacy_path.exists()

        # Case 2: Existing legacy config - should save to legacy location
        # Create legacy directory and file
        legacy_dir.mkdir()
        with open(legacy_path, "w") as f:
            yaml.safe_dump({"apikey": "existing_legacy"}, f)

        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.DEFAULT_CONFIG_FILE", legacy_path),
            patch("tidy3d.config.yaml_config_settings_source", return_value={}),
        ):
            # Create and save a config
            config = Tidy3dConfig(apikey="legacy_save_test")
            config.save()

            # Verify it was saved to legacy path
            assert legacy_path.exists()
            with open(legacy_path) as f:
                content = yaml.safe_load(f)

            assert content["apikey"] == "legacy_save_test"


def test_config_reload():
    """Test reloading configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "config"

        # Write test config
        with open(temp_config_path, "w") as f:
            yaml.safe_dump({"apikey": "reload_test_key"}, f)

        # Create config with patched path
        def mock_yaml_source(settings):
            with open(temp_config_path) as f:
                return yaml.safe_load(f) or {}

        with patch("tidy3d.config.yaml_config_settings_source", side_effect=mock_yaml_source):
            config = Tidy3dConfig()
            assert config.apikey == "reload_test_key"

            # Change the config and reload
            config.apikey = "changed_key"
            assert config.apikey == "changed_key"

            # Update the file
            with open(temp_config_path, "w") as f:
                yaml.safe_dump({"apikey": "new_file_key"}, f)

            # Reload should pick up the new value from file
            with patch("tidy3d.config.Tidy3dConfig") as mock_tidy3d_config:
                mock_instance = mock_tidy3d_config.return_value
                mock_instance.apikey = "new_file_key"
                mock_instance.__fields__ = {"apikey": None}
                mock_instance.__fields_set__ = {"apikey"}

                config.load()
                assert config.apikey == "new_file_key"
