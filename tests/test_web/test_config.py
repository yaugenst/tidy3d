"""Test the Tidy3D configuration system."""

import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import toml
from tidy3d.config import (
    CONFIG_PATHS,
    READ_CONFIG_PATHS,
    Tidy3dConfig,
    _convert_to_sectioned_config,
    _parse_legacy_format,
    toml_config_settings_source,
)


def test_config_defaults():
    """Test that the default configuration values are set correctly."""
    # Create a temporary config with defaults
    with patch("tidy3d.config.toml_config_settings_source", return_value={}):
        config = Tidy3dConfig()

        # Test direct properties
        assert config.apikey is None
        assert config.ssl_verify is True
        assert config.log_suppression is True

        # Test nested values
        assert config.auth.apikey is None
        assert config.logging.ssl_verify is True
        assert config.logging.suppression is True
        assert config.logging.level == "INFO"


def test_config_env_override():
    """Test that environment variables override defaults."""
    # Set environment variables
    os.environ["SIMCLOUD_APIKEY"] = "test_key_from_env"
    os.environ["TIDY3D_SSL_VERIFY"] = "False"

    try:
        # Create a new config (should pick up env vars)
        with patch("tidy3d.config.toml_config_settings_source", return_value={}):
            config = Tidy3dConfig()

            # Test direct properties
            assert config.apikey == "test_key_from_env"
            assert config.ssl_verify is False

            # Test nested values
            assert config.auth.apikey == "test_key_from_env"
            assert config.logging.ssl_verify is False
    finally:
        # Clean up environment to avoid affecting other tests
        del os.environ["SIMCLOUD_APIKEY"]
        del os.environ["TIDY3D_SSL_VERIFY"]


def test_config_save_load():
    """Test saving and loading configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "config.toml"

        # Create and save config
        with patch("tidy3d.config.toml_config_settings_source", return_value={}):
            config = Tidy3dConfig()
            config.auth.apikey = "test_save_key"
            config.logging.ssl_verify = False
            config.save(temp_config_path)

        # Verify the file exists and has correct content
        assert temp_config_path.exists()
        with open(temp_config_path) as f:
            content = f.read()
            toml_data = toml.loads(content)

        # Verify TOML structure
        assert "auth" in toml_data
        assert "logging" in toml_data
        assert toml_data["auth"]["apikey"] == "test_save_key"
        assert toml_data["logging"]["ssl_verify"] is False

        # Create a new config and load from the file
        with patch("tidy3d.config.toml_config_settings_source", return_value={}):
            new_config = Tidy3dConfig()
            new_config.load(temp_config_path)

            # Test direct properties
            assert new_config.apikey == "test_save_key"
            assert new_config.ssl_verify is False

            # Test nested values
            assert new_config.auth.apikey == "test_save_key"
            assert new_config.logging.ssl_verify is False


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

        # Test conversion to sectioned config
        sectioned = _convert_to_sectioned_config(parsed)
        assert "auth" in sectioned
        assert "logging" in sectioned
        assert sectioned["auth"]["apikey"] == "legacy_test_key"

        # Patch the settings source to use our file
        def mock_toml_source(settings):
            with open(temp_config_path) as f:
                content = f.read()
            flat_config = _parse_legacy_format(content)
            sectioned_config = _convert_to_sectioned_config(flat_config)

            # Flatten for Pydantic format with section.key
            result = {}
            for section, values in sectioned_config.items():
                for key, value in values.items():
                    result[f"{section}.{key}"] = value
            return result

        with patch("tidy3d.config.toml_config_settings_source", side_effect=mock_toml_source):
            config = Tidy3dConfig()
            assert config.apikey == "legacy_test_key"
            assert config.auth.apikey == "legacy_test_key"

        # Save it and verify it's now in TOML format
        with patch("tidy3d.config.toml_config_settings_source", return_value={}):
            config = Tidy3dConfig()
            config.auth.apikey = "legacy_test_key"
            config.save(temp_config_path)

        with open(temp_config_path) as f:
            content = f.read()
            toml_data = toml.loads(content)

        assert "auth" in toml_data
        assert toml_data["auth"]["apikey"] == "legacy_test_key"
        assert (
            "=" not in content or "=" in content and not content.startswith("apikey =")
        )  # Check it's TOML, not legacy format


def test_validation():
    """Test that configuration validation works."""
    # Test setting invalid logging level (should raise ValidationError)
    with patch("tidy3d.config.toml_config_settings_source", return_value={}):
        config = Tidy3dConfig()

        # Test with property accessor
        with pytest.raises(ValueError):
            config.logging_level = "INVALID_LEVEL"

        # Test with direct nested access
        with pytest.raises(ValueError):
            config.logging.level = "INVALID_LEVEL"


def test_config_paths():
    """Test the config paths are correct for each platform."""
    home = Path.home()

    # Legacy path should have .toml extension
    legacy_path = home / ".tidy3d" / "config.toml"
    assert str(CONFIG_PATHS["legacy"]) == str(legacy_path)

    # Old legacy path should not have extension
    old_legacy_path = home / ".tidy3d" / "config"
    assert str(CONFIG_PATHS["old_legacy"]) == str(old_legacy_path)

    # XDG path depends on platform
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        expected_xdg_path = appdata / "tidy3d" / "config.toml"
    else:
        expected_xdg_path = home / ".config" / "tidy3d" / "config.toml"

    assert str(CONFIG_PATHS["xdg"]) == str(expected_xdg_path)

    # Check read paths order
    assert str(READ_CONFIG_PATHS[0]) == str(legacy_path)  # Legacy with .toml first
    assert str(READ_CONFIG_PATHS[1]) == str(old_legacy_path)  # Old legacy without extension second
    assert str(READ_CONFIG_PATHS[2]) == str(expected_xdg_path)  # XDG third


def test_toml_config_settings_source():
    """Test the TOML settings source with multiple config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create temporary config paths
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_dir.mkdir()
        legacy_path = legacy_dir / "config.toml"

        old_legacy_dir = Path(temp_dir) / "old_legacy"
        old_legacy_dir.mkdir()
        old_legacy_path = old_legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_dir.mkdir()
        xdg_path = xdg_dir / "config.toml"

        # Mock READ_CONFIG_PATHS to point to our temp paths
        mock_paths = [legacy_path, old_legacy_path, xdg_path]
        mock_config_paths = {"legacy": legacy_path, "old_legacy": old_legacy_path, "xdg": xdg_path}

        # Case 1: Only XDG file exists with TOML sections
        with open(xdg_path, "w") as f:
            toml.dump({"auth": {"apikey": "xdg_key"}}, f)

        with (
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths),
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
        ):
            # Check the settings source directly
            config_dict = toml_config_settings_source(None)
            assert config_dict.get("auth.apikey") == "xdg_key"

        # Case 2: Both legacy and XDG exist, legacy should have precedence
        with open(legacy_path, "w") as f:
            toml.dump({"auth": {"apikey": "legacy_key"}}, f)

        with (
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths),
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
        ):
            # Check the settings source directly
            config_dict = toml_config_settings_source(None)
            assert config_dict.get("auth.apikey") == "legacy_key"

        # Case 3: Legacy has apikey, XDG has ssl_verify - both should be included
        with open(legacy_path, "w") as f:
            toml.dump({"auth": {"apikey": "legacy_key"}}, f)

        with open(xdg_path, "w") as f:
            toml.dump({"logging": {"ssl_verify": False}}, f)

        with (
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths),
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
        ):
            # Check the settings source directly
            config_dict = toml_config_settings_source(None)
            assert config_dict.get("auth.apikey") == "legacy_key"
            assert config_dict.get("logging.ssl_verify") is False

        # Case 4: Both have same key, legacy should win
        with open(legacy_path, "w") as f:
            toml.dump({"logging": {"ssl_verify": True}}, f)

        with open(xdg_path, "w") as f:
            toml.dump({"logging": {"ssl_verify": False}}, f)

        with (
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_paths),
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
        ):
            # Check the settings source directly
            config_dict = toml_config_settings_source(None)
            assert config_dict.get("logging.ssl_verify") is True


def test_legacy_format_conversion():
    """Test conversion of legacy format to TOML format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create paths that mimic our real ones
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_dir.mkdir()
        legacy_toml_path = legacy_dir / "config.toml"

        old_legacy_dir = Path(temp_dir) / "old_legacy"
        old_legacy_dir.mkdir()
        old_legacy_path = old_legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_dir.mkdir()
        xdg_path = xdg_dir / "config.toml"

        # Mock config paths
        mock_config_paths = {
            "legacy": legacy_toml_path,
            "old_legacy": old_legacy_path,
            "xdg": xdg_path,
        }
        mock_read_paths = [legacy_toml_path, old_legacy_path, xdg_path]

        # Create a legacy format file in the old legacy location
        with open(old_legacy_path, "w") as f:
            f.write('apikey = "conversion_test_key"\nssl_verify = "False"')

        # Call the settings source function with our mocked paths
        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.READ_CONFIG_PATHS", mock_read_paths),
        ):
            # This should trigger the conversion
            config_dict = toml_config_settings_source(None)

            # Verify the function returned the correct flattened values
            assert config_dict.get("auth.apikey") == "conversion_test_key"
            assert config_dict.get("logging.ssl_verify") == "False"  # Still a string at this point

            # Verify the backup was created
            assert (old_legacy_path.with_suffix(".old")).exists()

            # Verify the legacy TOML file was created
            assert legacy_toml_path.exists()

            # Verify it has the correct TOML structure
            with open(legacy_toml_path) as f:
                content = f.read()
                toml_data = toml.loads(content)

            assert "auth" in toml_data
            assert "logging" in toml_data
            assert toml_data["auth"]["apikey"] == "conversion_test_key"
            assert toml_data["logging"]["ssl_verify"] == "False"


def test_default_save_location():
    """Test that save() uses the correct default location."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock paths
        legacy_dir = Path(temp_dir) / "legacy"
        legacy_path = legacy_dir / "config.toml"

        old_legacy_dir = Path(temp_dir) / "old_legacy"
        old_legacy_path = old_legacy_dir / "config"

        xdg_dir = Path(temp_dir) / "xdg"
        xdg_path = xdg_dir / "config.toml"

        mock_config_paths = {"legacy": legacy_path, "old_legacy": old_legacy_path, "xdg": xdg_path}

        # Case 1: No existing config - should save to XDG location
        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.DEFAULT_CONFIG_FILE", xdg_path),
            patch("tidy3d.config.toml_config_settings_source", return_value={}),
        ):
            # Create and save a config
            config = Tidy3dConfig()
            config.auth.apikey = "xdg_save_test"
            config.save()

            # Verify it was saved to XDG path
            assert xdg_path.exists()
            with open(xdg_path) as f:
                content = f.read()
                toml_data = toml.loads(content)

            assert "auth" in toml_data
            assert toml_data["auth"]["apikey"] == "xdg_save_test"

            # Legacy path should not exist
            assert not legacy_path.exists()

        # Case 2: Existing legacy config - should save to legacy location
        # Create legacy directory and file
        legacy_dir.mkdir(parents=True, exist_ok=True)
        with open(legacy_path, "w") as f:
            toml.dump({"auth": {"apikey": "existing_legacy"}}, f)

        with (
            patch("tidy3d.config.CONFIG_PATHS", mock_config_paths),
            patch("tidy3d.config.DEFAULT_CONFIG_FILE", legacy_path),
            patch("tidy3d.config.toml_config_settings_source", return_value={}),
        ):
            # Create and save a config
            config = Tidy3dConfig()
            config.auth.apikey = "legacy_save_test"
            config.save()

            # Verify it was saved to legacy path
            assert legacy_path.exists()
            with open(legacy_path) as f:
                content = f.read()
                toml_data = toml.loads(content)

            assert "auth" in toml_data
            assert toml_data["auth"]["apikey"] == "legacy_save_test"


def test_config_reload():
    """Test reloading configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "config.toml"

        # Write test config in TOML format
        with open(temp_config_path, "w") as f:
            toml.dump({"auth": {"apikey": "reload_test_key"}}, f)

        # Create config with patched path
        def mock_toml_source(settings):
            with open(temp_config_path) as f:
                content = f.read()
                toml_data = toml.loads(content)

                # Flatten for Pydantic format with section.key
                result = {}
                for section, values in toml_data.items():
                    for key, value in values.items():
                        result[f"{section}.{key}"] = value

                return result

        with patch("tidy3d.config.toml_config_settings_source", side_effect=mock_toml_source):
            config = Tidy3dConfig()

            # Test both direct property and nested property
            assert config.apikey == "reload_test_key"
            assert config.auth.apikey == "reload_test_key"

            # Change the config
            config.auth.apikey = "changed_key"
            assert config.apikey == "changed_key"

            # Update the file
            with open(temp_config_path, "w") as f:
                toml.dump({"auth": {"apikey": "new_file_key"}}, f)

            # Reload should pick up the new value from file
            with patch("tidy3d.config.Tidy3dConfig") as mock_tidy3d_config:
                mock_instance = mock_tidy3d_config.return_value
                mock_instance.auth = type(
                    "obj",
                    (object,),
                    {
                        "apikey": "new_file_key",
                        "__fields__": {"apikey": None},
                        "__fields_set__": {"apikey"},
                    },
                )
                mock_instance.logging = type(
                    "obj", (object,), {"__fields__": {}, "__fields_set__": {}}
                )

                config.load()
                assert config.apikey == "new_file_key"
