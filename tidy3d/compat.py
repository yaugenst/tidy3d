"""Compatibility layer for handling differences between package versions."""

try:
    from xarray.structure import alignment
except ImportError:
    from xarray.core import alignment

try:
    from typing import Self  # Python >= 3.11
except ImportError:  # Python <3.11
    from typing_extensions import Self

__all__ = ["alignment", "Self"]
