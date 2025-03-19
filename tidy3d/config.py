"""Sets the configuration of Tidy3D, can be changed with `td.config.config_name = new_val`.

The configuration can be loaded from:
1. Environment variables (highest priority)
2. Configuration file at the following locations (in order of precedence):
   - ~/.tidy3d/config.toml (legacy location)
   - ~/.config/tidy3d/config.toml (Linux/macOS XDG location)
   - %APPDATA%\\tidy3d\\config.toml (Windows location)
3. Default values (lowest priority)

Key configuration options:
- [auth]
  - apikey: API key for authenticating with Tidy3D web services
    * Can be set via SIMCLOUD_API_KEY environment variable
    * Example: export SIMCLOUD_API_KEY="your-api-key"

- [logging]
  - level: Level of logging verbosity
    * Can be set via TIDY3D_LOGGING_LEVEL environment variable
    * Valid values: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
  - suppression: Whether to suppress repeated log messages
    * Can be set via TIDY3D_LOG_SUPPRESSION environment variable
    * Example: export TIDY3D_LOG_SUPPRESSION=0
  - ssl_verify: Whether to verify SSL certificates when making API calls
    * Can be set via TIDY3D_SSL_VERIFY environment variable
    * Example: export TIDY3D_SSL_VERIFY=0

Configuration files use TOML format. Example content:
```toml
[auth]
apikey = "your-api-key"

[logging]
level = "INFO"
suppression = true
ssl_verify = true
```

You can programmatically save and load configuration:
```python
import tidy3d as td

# Save current config to default location
td.config.save()

# Load config from a specific file
td.config.load('/path/to/config.toml')

# Update settings at runtime
td.config.logging.level = "DEBUG"
```
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import pydantic.v1 as pd
import toml

from .log import DEFAULT_LEVEL, LogLevel, set_log_suppression, set_logging_level

# Constants - define here to avoid circular imports
SIMCLOUD_APIKEY = "SIMCLOUD_APIKEY"


# Configuration file paths
def get_config_paths() -> Dict[str, Path]:
    """Get dictionary of possible configuration file paths.

    Returns
    -------
    Dict[str, Path]
        Dictionary of configuration file paths with keys: 'legacy', 'xdg'
    """
    home = Path.home()

    # Legacy path (~/.tidy3d/config.toml)
    legacy_config_dir = home / ".tidy3d"
    legacy_config_file = legacy_config_dir / "config.toml"

    # Old legacy path without extension
    old_legacy_config_file = legacy_config_dir / "config"

    # XDG Base Directory paths
    if platform.system() == "Windows":
        # On Windows, use %APPDATA%\tidy3d\config.toml
        xdg_config_dir = (
            Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))) / "tidy3d"
        )
    else:
        # On Unix systems, use ~/.config/tidy3d
        xdg_config_dir = home / ".config" / "tidy3d"

    xdg_config_file = xdg_config_dir / "config.toml"

    return {
        "legacy": legacy_config_file,
        "xdg": xdg_config_file,
        "old_legacy": old_legacy_config_file,
    }


# Get configuration directories and files
CONFIG_PATHS = get_config_paths()

# For new configurations, use XDG path by default
# For existing configurations, use the existing location
# This ensures backward compatibility while moving forward with XDG
if CONFIG_PATHS["legacy"].exists():
    DEFAULT_CONFIG_FILE = CONFIG_PATHS["legacy"]
elif CONFIG_PATHS["old_legacy"].exists():
    # If old format exists, we'll migrate but still use the legacy location
    DEFAULT_CONFIG_FILE = CONFIG_PATHS["legacy"]
else:
    DEFAULT_CONFIG_FILE = CONFIG_PATHS["xdg"]

# For reading, check legacy first, then old legacy, then XDG
READ_CONFIG_PATHS = [CONFIG_PATHS["legacy"], CONFIG_PATHS["old_legacy"], CONFIG_PATHS["xdg"]]


# Pydantic settings sources
def toml_config_settings_source(settings: pd.BaseSettings) -> Dict[str, Any]:
    """Load configuration from TOML files.

    Checks multiple locations in order of precedence:
    1. Legacy location: ~/.tidy3d/config.toml
    2. Old legacy location: ~/.tidy3d/config (no extension)
    3. XDG location: ~/.config/tidy3d/config.toml or %APPDATA%\\tidy3d\\config.toml on Windows

    If a key is found in multiple files, the value from the first file wins.

    When a legacy format file without .toml extension is detected, it will be:
    1. Backed up with .old extension
    2. Converted to TOML format with proper sections
    Legacy configs will remain in the legacy location but be converted to TOML.
    New configs will be saved to the XDG location.

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
    for config_path in READ_CONFIG_PATHS:
        if not config_path.exists():
            continue

        try:
            # Check if it's the old format (no extension)
            is_old_format = config_path == CONFIG_PATHS["old_legacy"]

            if is_old_format:
                with open(config_path) as f:
                    content = f.read()

                # Parse according to content
                if "=" in content:
                    # Legacy key=value format
                    file_config = _parse_legacy_format(content)
                else:
                    # Might be YAML or other format, try to parse as TOML first
                    try:
                        file_config = toml.loads(content)
                    except Exception:
                        # Not TOML, skip this file
                        continue

                if file_config:
                    try:
                        # Back up the old file
                        backup_path = Path(str(config_path) + ".old")
                        shutil.copy2(config_path, backup_path)
                        print(f"Backed up original config to {backup_path}")

                        # Convert flat dict to sectioned TOML
                        sectioned_config = _convert_to_sectioned_config(file_config)

                        # Save to new TOML file in the same location but with .toml extension
                        new_toml_path = CONFIG_PATHS["legacy"]
                        new_toml_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(new_toml_path, "w") as f:
                            toml.dump(sectioned_config, f)

                        print(f"Migrated config from {config_path} to {new_toml_path}")

                        # Populate result with the sectioned config values
                        # Flatten sectioned config for Pydantic
                        for section, values in sectioned_config.items():
                            for key, value in values.items():
                                # Use section.key format for Pydantic
                                flat_key = f"{section}.{key}"
                                if flat_key not in result:
                                    result[flat_key] = value
                    except Exception as e:
                        print(f"Warning: Failed to migrate legacy config: {e}")
            else:
                # It's a TOML file, parse it
                with open(config_path) as f:
                    content = f.read()

                try:
                    toml_data = toml.loads(content)

                    # Flatten sections for Pydantic
                    for section, values in toml_data.items():
                        for key, value in values.items():
                            # Use section.key format for Pydantic
                            flat_key = f"{section}.{key}"
                            if flat_key not in result:
                                result[flat_key] = value
                except Exception as e:
                    print(f"Warning: Failed to parse TOML file {config_path}: {e}")

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


def _convert_to_sectioned_config(flat_config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Convert a flat config dict to a sectioned config dict.

    Parameters
    ----------
    flat_config : Dict[str, Any]
        Flat dictionary with configuration values.

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Dictionary with sections as keys and configuration values as nested dicts.
    """
    sectioned_config = {
        "auth": {},
        "logging": {},
    }

    # Map keys to sections
    section_mapping = {
        "apikey": "auth",
        "logging_level": "logging",
        "level": "logging",
        "log_suppression": "logging",
        "suppression": "logging",
        "ssl_verify": "logging",
    }

    # Map old keys to new keys
    key_mapping = {"logging_level": "level", "log_suppression": "suppression"}

    for key, value in flat_config.items():
        section = section_mapping.get(key, "auth")  # Default to auth section

        # Transform key if needed
        new_key = key_mapping.get(key, key)

        sectioned_config[section][new_key] = value

    return sectioned_config


class LoggingConfig(pd.BaseModel):
    """Configuration for logging settings."""

    level: LogLevel = pd.Field(
        DEFAULT_LEVEL,
        title="Logging Level",
        description="The lowest level of logging output that will be displayed. "
        'Can be "DEBUG", "SUPPORT", "USER", INFO", "WARNING", "ERROR", or "CRITICAL". '
        'Note: "SUPPORT" and "USER" levels are only used in backend solver logging.',
        env="TIDY3D_LOGGING_LEVEL",
    )

    suppression: bool = pd.Field(
        True,
        title="Log suppression",
        description="Enable or disable suppression of certain log messages when they are repeated "
        "for several elements.",
        env="TIDY3D_LOG_SUPPRESSION",
    )

    ssl_verify: bool = pd.Field(
        True,
        title="SSL Verification",
        description="Whether to verify SSL certificates when making API calls. "
        "Set to False to disable verification for self-signed certificates.",
        env="TIDY3D_SSL_VERIFY",
    )

    @pd.validator("level", pre=True, always=True)
    def _set_logging_level(cls, val):
        """Set the logging level if level is changed."""
        set_logging_level(val)
        return val

    @pd.validator("suppression", pre=True, always=True)
    def _set_log_suppression(cls, val):
        """Control log suppression when suppression is changed."""
        set_log_suppression(val)
        return val


class AuthConfig(pd.BaseModel):
    """Configuration for authentication settings."""

    apikey: Optional[str] = pd.Field(
        None,
        title="API Key",
        description="The SimCloud API key for authentication with Tidy3D web services.",
        env=SIMCLOUD_APIKEY,
    )


class Tidy3dConfig(pd.BaseSettings):
    """Configuration of Tidy3D with settings for API and logging.

    This class manages all configuration values for Tidy3D and serves as the
    single source of truth for configuration. It can load from environment
    variables, configuration file, and provides default values.
    """

    auth: AuthConfig = AuthConfig()
    logging: LoggingConfig = LoggingConfig()

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
            3. toml_config_settings_source: TOML config files
            4. file_secret_settings: Secret files (not used)
            """
            return (
                init_settings,
                env_settings,
                toml_config_settings_source,
            )

    def save(self, path: Union[str, Path] = None) -> None:
        """Save current configuration to file.

        Parameters
        ----------
        path : Union[str, Path], optional
            Path to save configuration file. If None, uses default path:
            - Legacy location (~/.tidy3d/config.toml) if it already exists
            - XDG location for new configurations
        """
        save_path = Path(path) if path else DEFAULT_CONFIG_FILE

        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to nested dict for TOML
        config_dict = {
            "auth": self.auth.dict(exclude_unset=True, exclude_none=True),
            "logging": self.logging.dict(exclude_unset=True, exclude_none=True),
        }

        # Remove empty sections
        config_dict = {k: v for k, v in config_dict.items() if v}

        # Write TOML to file
        with open(save_path, "w") as f:
            toml.dump(config_dict, f)

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

                # Parse as TOML
                try:
                    toml_data = toml.loads(content)

                    # Update auth section if it exists
                    if "auth" in toml_data:
                        for key, value in toml_data["auth"].items():
                            setattr(self.auth, key, value)

                    # Update logging section if it exists
                    if "logging" in toml_data:
                        for key, value in toml_data["logging"].items():
                            setattr(self.logging, key, value)

                    print(f"Configuration loaded from {load_path}")
                except Exception as e:
                    print(f"Error parsing TOML from {load_path}: {e}")

            except Exception as e:
                print(f"Error loading config from {load_path}: {e}")

        else:
            # No path specified, reload using Pydantic sources
            # Create a new settings instance
            new_config = Tidy3dConfig()

            # Copy auth values
            for field in self.auth.__fields__:
                if hasattr(new_config.auth, field):
                    field_value = getattr(new_config.auth, field)
                    if field in new_config.auth.__fields_set__:
                        setattr(self.auth, field, field_value)

            # Copy logging values
            for field in self.logging.__fields__:
                if hasattr(new_config.logging, field):
                    field_value = getattr(new_config.logging, field)
                    if field in new_config.logging.__fields_set__:
                        setattr(self.logging, field, field_value)

            print("Configuration reloaded from environment and config files")

    # Legacy property accessors for backward compatibility
    @property
    def apikey(self) -> Optional[str]:
        """Get or set the API key."""
        return self.auth.apikey

    @apikey.setter
    def apikey(self, value: Optional[str]) -> None:
        self.auth.apikey = value

    @property
    def logging_level(self) -> LogLevel:
        """Get or set the logging level."""
        return self.logging.level

    @logging_level.setter
    def logging_level(self, value: LogLevel) -> None:
        self.logging.level = value

    @property
    def log_suppression(self) -> bool:
        """Get or set log suppression."""
        return self.logging.suppression

    @log_suppression.setter
    def log_suppression(self, value: bool) -> None:
        self.logging.suppression = value

    @property
    def ssl_verify(self) -> bool:
        """Get or set SSL verification."""
        return self.logging.ssl_verify

    @ssl_verify.setter
    def ssl_verify(self, value: bool) -> None:
        self.logging.ssl_verify = value


# Instance of the config that can be modified.
# On import, this will load settings from env vars and config file
config = Tidy3dConfig()
