"""Helpers for automatic setup of path integrals."""

from typing import Literal, Union

import numpy as np
import pydantic.v1 as pd
import xarray as xr

from ...components.data.monitor_data import FieldTimeData
from ...components.geometry.base import Box
from ...components.geometry.utils import SnapBehavior, SnapLocation, SnappingSpec, snap_box_to_grid
from ...components.grid.grid import Grid
from ...components.lumped_element import LinearLumpedElement
from ...components.types import Ax, Direction
from ...components.viz import add_ax_if_none
from ...exceptions import DataError
from .custom_path_integrals import (
    CustomCurrentIntegral2D,
)
from .path_integrals import (
    CurrentIntegralAxisAligned,
    IntegralResultTypes,
    MonitorDataTypes,
    VoltageIntegralAxisAligned,
)

BaseCurrentIntegralTypes = Union[CurrentIntegralAxisAligned, CustomCurrentIntegral2D]


def path_integrals_from_lumped_element(
    lumped_element: LinearLumpedElement, grid: Grid, polarity: Direction = "+"
) -> tuple[VoltageIntegralAxisAligned, CurrentIntegralAxisAligned]:
    """Helper to create a :class:`.VoltageIntegralAxisAligned` and :class:`.CurrentIntegralAxisAligned`
    from a supplied :class:`.LinearLumpedElement`. Takes into account any snapping the lumped element
    undergoes using the supplied :class:`.Grid`.

    Parameters
    ----------
    lumped_element : :class:`.LinearLumpedElement`
        Position along the voltage axis of the positive terminal.
    grid : :class:`.Grid`
        Position along the voltage axis of the negative terminal.
    polarity : Direction
        Choice for defining voltage. When positive, the terminal of the lumped element with
        the greatest coordinate is considered the positive terminal.
    Returns
    -------
    VoltageIntegralAxisAligned
        The created path integral for computing voltage between the two terminals of the :class:`.LinearLumpedElement`.
    CurrentIntegralAxisAligned
        The created path integral for computing current flowing through the :class:`.LinearLumpedElement`.
    """

    # Quick access to voltage and the primary current axis
    V_axis = lumped_element.voltage_axis
    I_axis = lumped_element.lateral_axis

    # The exact position of the lumped element after any possible snapping
    lumped_element_box = lumped_element._create_box_for_network(grid=grid)

    V_size = [0, 0, 0]
    V_size[V_axis] = lumped_element_box.size[V_axis]
    voltage_integral = VoltageIntegralAxisAligned(
        center=lumped_element_box.center,
        size=V_size,
        sign=polarity,
        extrapolate_to_endpoints=True,
        snap_path_to_grid=True,
    )

    # Snap the current integral to a box that encloses the element along the lateral and normal axes
    # using the closest positions of the magnetic field
    snap_location = [SnapLocation.Center] * 3
    snap_behavior = [SnapBehavior.Expand] * 3
    # Don't need to snap along voltage axis, since it will already be snapped from the lumped element's box
    snap_behavior[V_axis] = SnapBehavior.Off
    snap_spec = SnappingSpec(location=snap_location, behavior=snap_behavior)

    I_size = [0, 0, 0]
    I_size[I_axis] = lumped_element_box.size[I_axis]
    current_box = Box(center=lumped_element_box.center, size=I_size)
    current_box = snap_box_to_grid(grid, current_box, snap_spec)
    # Convention is current flows from plus to minus terminals
    current_sign = "-" if polarity == "+" else "+"
    current_integral = CurrentIntegralAxisAligned(
        center=current_box.center,
        size=current_box.size,
        sign=current_sign,
        snap_contour_to_grid=True,
        extrapolate_to_endpoints=True,
    )

    return (voltage_integral, current_integral)


class CompositeCurrentIntegral(Box):
    current_integrals: tuple[BaseCurrentIntegralTypes, ...] = pd.Field(
        ...,
        title="Current Integrals",
        description="Definition of contour integrals, each representing a disjoint closed path.",
    )

    sum_spec: Literal["sum", "split"] = pd.Field(
        ...,
        title="Sum Specification",
        description="Determines the method used to combine the currents calculated by the different current integrals in ``current_integrals``."
        "``sum`` simply adds all currents, while ``split`` keeps contributions with opposite phase separate, which allows for isolating "
        "the current flowing in opposite directions. In ``split`` version, the current returned is the maximum of the two contributions.",
    )

    def compute_current(self, em_field: MonitorDataTypes) -> IntegralResultTypes:
        """Compute current flowing in loop defined by the outer edge of a rectangle."""
        if isinstance(em_field, FieldTimeData) and self.sum_spec == "split":
            raise DataError(
                "Only frequency domain field data is supported when using the 'split' sum_spec. "
                "Either switch the sum_spec to 'sum' or supply frequency domain data."
            )

        # Initialize arrays with first current term
        first_term = self.current_integrals[0].compute_current(em_field)
        current_in_phase = xr.zeros_like(first_term)
        current_out_phase = xr.zeros_like(first_term)

        # Get reference phase from first non-zero current
        phase_reference = None
        for path in self.current_integrals:
            term = path.compute_current(em_field)
            if np.any(abs(term) > 0):
                phase_reference = np.angle(term)
                break
        assert phase_reference is not None, "No non-zero current found"

        # Accumulate currents based on phase comparison
        for path in self.current_integrals:
            term = path.compute_current(em_field)
            if np.all(abs(term) == 0):
                continue

            # Compare phase to reference
            phase_diff = np.angle(term) - phase_reference
            # Wrap phase difference to [-pi, pi]
            phase_diff = np.mod(phase_diff + np.pi, 2 * np.pi) - np.pi

            # Check phase consistency across frequencies
            freq_axis = term.get_axis_num("f")
            consistent_phase = np.all(
                np.logical_or(
                    abs(phase_diff) <= np.pi / 2,  # in phase
                    abs(phase_diff) > np.pi / 2,  # out of phase
                ),
                axis=freq_axis,
            )
            assert np.all(consistent_phase), "Phase alignment must be consistent across frequencies"

            # Add to in-phase or out-of-phase current
            is_in_phase = abs(phase_diff) <= np.pi / 2
            current_in_phase += xr.where(is_in_phase, term, 0)
            current_out_phase += xr.where(~is_in_phase, term, 0)

        if self.sum_spec == "sum":
            return CurrentIntegralAxisAligned._set_data_array_attributes(
                current_in_phase + current_out_phase
            )

        # For split mode, return the larger magnitude current
        freq_axis = current_in_phase.get_axis_num("f")
        consistent_over_frequency = np.all(
            np.logical_or(
                abs(current_in_phase) >= abs(current_out_phase),
                abs(current_in_phase) < abs(current_out_phase),
            ),
            axis=freq_axis,
        )
        assert np.all(
            consistent_over_frequency
        ), "Magnitude comparison must be consistent across frequencies"

        current = xr.where(
            abs(current_in_phase) >= abs(current_out_phase), current_in_phase, current_out_phase
        )
        return CurrentIntegralAxisAligned._set_data_array_attributes(current)

    @add_ax_if_none
    def plot(
        self,
        x: float = None,
        y: float = None,
        z: float = None,
        ax: Ax = None,
        **path_kwargs,
    ) -> Ax:
        """Plot path integral at single (x,y,z) coordinate.

        Parameters
        ----------
        x : float = None
            Position of plane in x direction, only one of x,y,z can be specified to define plane.
        y : float = None
            Position of plane in y direction, only one of x,y,z can be specified to define plane.
        z : float = None
            Position of plane in z direction, only one of x,y,z can be specified to define plane.
        ax : matplotlib.axes._subplots.Axes = None
            Matplotlib axes to plot on, if not specified, one is created.
        **path_kwargs
            Optional keyword arguments passed to the matplotlib plotting of the line.
            For details on accepted values, refer to
            `Matplotlib's documentation <https://tinyurl.com/36marrat>`_.

        Returns
        -------
        matplotlib.axes._subplots.Axes
            The supplied or created matplotlib axes.
        """
        for current_integral in self.current_integrals:
            ax = current_integral.plot(x=x, y=y, z=z, ax=ax, **path_kwargs)
        return ax
