"""Specification for defining microwave terminals for the purpose of calculating transmission line impedance."""

from typing import Optional

import pydantic.v1 as pd

from ..base import Tidy3dBaseModel
from .path_spec import PathSpecTypes


class TerminalSpec(Tidy3dBaseModel):
    """
    Stores specifications for definition.

    Notes
    -----
    """

    voltage_spec: Optional[PathSpecTypes] = pd.Field(
        None,
        title="Voltage Integral",
        description="Definition of path integral for computing voltage.",
    )

    current_spec: Optional[PathSpecTypes] = pd.Field(
        None,
        title="Current Integral",
        description="Definition of contour integral for computing current.",
    )
