"""Dealing with time specifications for DeviceSimulation"""

import pydantic.v1 as pd

from ....constants import KELVIN, SECOND
from ...base import Tidy3dBaseModel


class UnsteadySpec(Tidy3dBaseModel):
    """Defines an unsteady specification

    Example
    --------
    >>> import tidy3d as td
    >>> time_spec = td.UnsteadySpec(
    ...     time_step=0.01,
    ...     total_time_steps=200,
    ...     output_fr=50,
    ... )
    """

    time_step: pd.PositiveFloat = pd.Field(
        ...,
        title="Time-step",
        description="Time step taken for each iteration of the time integration loop.",
        units=SECOND,
    )

    total_time_steps: pd.PositiveInt = pd.Field(
        ...,
        title="Total time steps",
        description="Specifies the total number of time steps run during the simulation.",
    )

    output_fr: pd.PositiveInt = pd.Field(
        1,
        title="Output frequency",
        description="Determines how often output files will be written. I.e., an output "
        "file will be written every 'output_fr' time steps.",
    )


class UnsteadyHeatAnalysis(Tidy3dBaseModel):
    """
    Configures relevant unsteady-state heat simulation parameters.

    Example
    -------
    >>> import tidy3d as td
    >>> time_spec = td.UnsteadyHeatAnalysis(
    ...     initial_temperature=300,
    ...     unsteady_spec=td.UnsteadySpec(
    ...         time_step=0.01,
    ...         total_time_steps=200,
    ...         output_fr=50,
    ...     ),
    ... )
    """

    initial_temperature: pd.PositiveFloat = pd.Field(
        ...,
        title="Initial temperature.",
        description="Initial value for the temperature field.",
        units=KELVIN,
    )

    unsteady_spec: UnsteadySpec = pd.Field(
        ...,
        title="Unsteady specification",
        description="Time step and total time steps for the unsteady simulation.",
    )
