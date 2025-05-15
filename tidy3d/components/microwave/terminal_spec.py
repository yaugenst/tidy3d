"""Specification for defining microwave terminals for the purpose of calculating transmission line impedance."""

from typing import Optional, Union

import pydantic.v1 as pd

from ..base import Tidy3dBaseModel
from .path_spec import CompositePathSpec, PathSpecTypes


class TerminalSpec(Tidy3dBaseModel):
    """Specification for computing transmission line voltages and currents in mode solvers.

    The TerminalSpec class determines how the transmission line impedance is calculated in a mode solver.
    It defines the line integral paths used to compute voltage and current in the transmission line.

    Users may supply their own voltage and current path specifications to control where these integrals
    are evaluated. If neither voltage nor current specs are provided, an automatic choice of paths will
    be made based on the simulation geometry and context.

    Notes
    -----
    - When no paths are specified, the automatic path selection attempts to find suitable integration
      contours that intersect conductor boundaries.
    - The voltage and current paths together define how the characteristic impedance of the transmission
      line will be calculated.
    """

    voltage_spec: Optional[PathSpecTypes] = pd.Field(
        None,
        title="Voltage Integration Path",
        description="Path specification for voltage line integral calculation.",
    )

    current_spec: Optional[Union[PathSpecTypes, CompositePathSpec]] = pd.Field(
        None,
        title="Current Integration Path",
        description="Path specification for current line integral calculation.",
    )
