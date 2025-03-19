"""Constants for the CLI."""

import os
from os.path import expanduser

# Determine Tidy3D base directory using platform-specific logic
TIDY3D_BASE_DIR = os.getenv("TIDY3D_BASE_DIR", f"{expanduser('~')}")

# Legacy directory (highest precedence)
if os.access(TIDY3D_BASE_DIR, os.W_OK):
    TIDY3D_DIR = f"{TIDY3D_BASE_DIR}/.tidy3d"
else:
    TIDY3D_DIR = "/tmp/.tidy3d"

# Ensure the legacy directory exists (for backward compatibility)
os.makedirs(TIDY3D_DIR, exist_ok=True)

# Legacy config file path
CONFIG_FILE = TIDY3D_DIR + "/config"

# Legacy credential file path
CREDENTIAL_FILE = TIDY3D_DIR + "/auth.json"
