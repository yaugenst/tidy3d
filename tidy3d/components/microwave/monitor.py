"""Objects that define how data is recorded from simulations involving microwave devices."""

import pydantic.v1 as pydantic

from ..monitor import ModeSolverMonitor
from .terminal_spec import TerminalSpec


class TerminalModeSolverMonitor(ModeSolverMonitor):
    """:class:`Monitor` that stores the mode field profiles returned by the mode solver in the
    monitor plane.

    Example
    -------
    >>> mode_spec = ModeSpec(num_modes=3)
    >>> monitor = ModeSolverMonitor(
    ...     center=(1,2,3),
    ...     size=(2,2,0),
    ...     freqs=[200e12, 210e12],
    ...     mode_spec=mode_spec,
    ...     name='mode_monitor')
    """

    terminal_spec: TerminalSpec = pydantic.Field(
        TerminalSpec(),
        title="Terminal Specification",
        description="Parameters to that determines how terminals are defined.",
    )
