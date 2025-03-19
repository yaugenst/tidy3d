"""Sets the configuration of Tidy3D, can be changed with `td.config.config_name = new_val`.

The configuration can be loaded from:
1. Environment variables (highest priority)
2. Configuration file at the following locations (in order of precedence):
   - ~/.tidy3d/config (legacy location)
   - ~/.config/tidy3d/config (Linux/macOS XDG location)
   - %APPDATA%\\tidy3d\\config (Windows location)
3. Default values (lowest priority)

Key configuration options:
- apikey: API key for authenticating with Tidy3D web services
  * Can be set via SIMCLOUD_API_KEY environment variable
  * Example: export SIMCLOUD_API_KEY="your-api-key"

- ssl_verify: Whether to verify SSL certificates when making API calls
  * Can be set via TIDY3D_SSL_VERIFY environment variable
  * Example: export TIDY3D_SSL_VERIFY=0

- logging_level: Level of logging verbosity
  * Can be set via TIDY3D_LOGGING_LEVEL environment variable
  * Valid values: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"

- log_suppression: Whether to suppress repeated log messages
  * Can be set via TIDY3D_LOG_SUPPRESSION environment variable
  * Example: export TIDY3D_LOG_SUPPRESSION=0

Configuration files use YAML format. Example content:
```yaml
apikey: your-api-key
ssl_verify: true
logging_level: INFO
log_suppression: true
```

You can programmatically save and load configuration:
```python
import tidy3d as td

# Save current config to default location
td.config.save()

# Load config from a specific file
td.config.load('/path/to/config')

# Update settings at runtime
td.config.logging_level = "DEBUG"
```
"""

import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pydantic.v1 as pd
import yaml

from .log import DEFAULT_LEVEL, LogLevel, set_log_suppression, set_logging_level

# Constants - define here to avoid circular imports
SIMCLOUD_APIKEY = "SIMCLOUD_APIKEY"


# Configuration file paths
def get_config_paths() -> List[Path]:
    """Get list of possible configuration file paths in order of precedence.

    Returns
    -------
    List[Path]
        List of configuration file paths in order of precedence.
    """
    home = Path.home()

    # Legacy path (~/.tidy3d/config) has highest precedence
    legacy_config_dir = home / ".tidy3d"
    legacy_config_file = legacy_config_dir / "config"

    # XDG Base Directory paths
    if platform.system() == "Windows":
        # On Windows, use %APPDATA%\tidy3d\config
        xdg_config_dir = (
            Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))) / "tidy3d"
        )
    else:
        # On Unix systems, use ~/.config/tidy3d
        xdg_config_dir = home / ".config" / "tidy3d"

    xdg_config_file = xdg_config_dir / "config"

    # Return paths in order of precedence: legacy first, then XDG
    return [legacy_config_file, xdg_config_file]


# Get configuration directories and files
CONFIG_PATHS = get_config_paths()
CONFIG_FILE = CONFIG_PATHS[0]  # Legacy path as the default for backward compatibility


# Pydantic settings sources
def yaml_config_settings_source(settings: pd.BaseSettings) -> Dict[str, Any]:
    """Load configuration from YAML files.

    Checks multiple locations in order of precedence:
    1. Legacy location: ~/.tidy3d/config
    2. XDG location: ~/.config/tidy3d/config or %APPDATA%\\tidy3d\\config on Windows

    If a key is found in multiple files, the value from the first file wins.

    When a legacy format file is detected, it will be automatically converted to YAML format.

    Parameters
    ----------
    settings : BaseSettings
        The settings instance that is being created.

    Returns
    -------
    Dict[str, Any]
        Dictionary with configuration values from files.
    """
    # Track combined configuration from all files
    result = {}

    # Check each config path in order of precedence
    for config_path in CONFIG_PATHS:
        if not config_path.exists():
            continue

        try:
            # Try to load file content
            with open(config_path) as f:
                content = f.read()

            # If file contains '=' character, it might be in legacy format
            if "=" in content:
                file_config = _parse_legacy_format(content)

                # Automatically migrate legacy format to YAML
                if file_config:
                    try:
                        # Ensure directory exists
                        config_path.parent.mkdir(parents=True, exist_ok=True)

                        # Write YAML to file
                        with open(config_path, "w") as f:
                            yaml.safe_dump(file_config, f, default_flow_style=False)

                        print(f"Converted legacy format to YAML: {config_path}")
                    except Exception as e:
                        print(f"Warning: Failed to convert legacy format to YAML: {e}")
            else:
                # Otherwise, parse as YAML
                file_config = yaml.safe_load(content) or {}

            # Merge values - earlier paths (higher in precedence) win for each key
            if file_config:
                for key, value in file_config.items():
                    # Only set values that haven't been set by a higher precedence file
                    if key not in result:
                        result[key] = value

        except Exception as e:
            print(f"Warning: Failed to load config file {config_path}: {e}")

    return result


def _parse_legacy_format(content: str) -> Dict[str, Any]:
    """Parse legacy format config file (apikey = "value").

    Parameters
    ----------
    content : str
        File content in legacy format.

    Returns
    -------
    Dict[str, Any]
        Dictionary with configuration values.
    """
    config = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Handle quoted values
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            config[key] = value
        except ValueError:
            continue  # Skip malformed lines

    return config


class Tidy3dConfig(pd.BaseSettings):
    """Configuration of Tidy3D with settings for API and logging.

    This class manages all configuration values for Tidy3D and serves as the
    single source of truth for configuration. It can load from environment
    variables, configuration file, and provides default values.
    """

    class Config:
        """Config of the config."""

        extra = "forbid"
        validate_assignment = True
        env_file = None
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ) -> Tuple[pd.env_settings.SettingsSourceCallable, ...]:
            """Customize the sources used for settings values.

            Order of precedence (highest to lowest):
            1. init_settings: Values passed to the constructor
            2. env_settings: Environment variables
            3. yaml_config_settings_source: YAML config files
            4. file_secret_settings: Secret files (not used)
            """
            return (
                init_settings,
                env_settings,
                yaml_config_settings_source,
            )

    # API Key can be set via SIMCLOUD_API_KEY environment variable
    apikey: Optional[str] = pd.Field(
        None,
        title="API Key",
        description="The SimCloud API key for authentication with Tidy3D web services.",
        env=SIMCLOUD_APIKEY,
    )

    # Log settings
    logging_level: LogLevel = pd.Field(
        DEFAULT_LEVEL,
        title="Logging Level",
        description="The lowest level of logging output that will be displayed. "
        'Can be "DEBUG", "SUPPORT", "USER", INFO", "WARNING", "ERROR", or "CRITICAL". '
        'Note: "SUPPORT" and "USER" levels are only used in backend solver logging.',
        env="TIDY3D_LOGGING_LEVEL",
    )

    log_suppression: bool = pd.Field(
        True,
        title="Log suppression",
        description="Enable or disable suppression of certain log messages when they are repeated "
        "for several elements.",
        env="TIDY3D_LOG_SUPPRESSION",
    )

    # SSL verification for web API calls
    ssl_verify: bool = pd.Field(
        True,
        title="SSL Verification",
        description="Whether to verify SSL certificates when making API calls. "
        "Set to False to disable verification for self-signed certificates.",
        env="TIDY3D_SSL_VERIFY",
    )

    @pd.validator("logging_level", pre=True, always=True)
    def _set_logging_level(cls, val):
        """Set the logging level if logging_level is changed."""
        set_logging_level(val)
        return val

    @pd.validator("log_suppression", pre=True, always=True)
    def _set_log_suppression(cls, val):
        """Control log suppression when log_suppression is changed."""
        set_log_suppression(val)
        return val

    def save(self, path: Union[str, Path] = None) -> None:
        """Save current configuration to file.

        Parameters
        ----------
        path : Union[str, Path], optional
            Path to save configuration file. If None, uses default path (legacy ~/.tidy3d/config).
        """
        save_path = Path(path) if path else CONFIG_FILE

        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding None values
        config_dict = {k: v for k, v in self.dict().items() if v is not None}

        # Write YAML to file
        with open(save_path, "w") as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False)

        print(f"Configuration saved to {save_path}")

    def load(self, path: Union[str, Path] = None) -> None:
        """Reload configuration from file.

        Parameters
        ----------
        path : Union[str, Path], optional
            Path to configuration file. If None, checks all default paths in order of precedence.
        """
        if path:
            # If specific path provided, use it
            load_path = Path(path)
            if not load_path.exists():
                print(f"Config file {load_path} not found.")
                return

            try:
                # Read the specified file
                with open(load_path) as f:
                    content = f.read()

                # Parse according to format
                if "=" in content:
                    values = _parse_legacy_format(content)
                else:
                    values = yaml.safe_load(content) or {}

                # Update all fields from the loaded values
                for key, value in values.items():
                    setattr(self, key, value)

                print(f"Configuration loaded from {load_path}")

            except Exception as e:
                print(f"Error loading config from {load_path}: {e}")

        else:
            # No path specified, reload using Pydantic sources
            # Create a new settings instance and copy its values
            new_config = Tidy3dConfig()

            # Only copy values that come from settings sources, not default values
            # This allows a user to reset to file-based settings
            for field in self.__fields__:
                if hasattr(new_config, field):
                    field_value = getattr(new_config, field)
                    # Check if this field has a non-default value (exists in a config file or env)
                    if field in new_config.__fields_set__:
                        setattr(self, field, field_value)

            print("Configuration reloaded from environment and config files")


# Instance of the config that can be modified.
# On import, this will load settings from env vars and config file
config = Tidy3dConfig()
