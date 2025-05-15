"""Factory functions for creating current and voltage path integrals from path specifications."""

from ...plugins.microwave import (
    CompositeCurrentIntegral,
    CurrentIntegralAxisAligned,
    CurrentIntegralTypes,
    CustomCurrentIntegral2D,
    CustomVoltageIntegral2D,
    VoltageIntegralAxisAligned,
    VoltageIntegralTypes,
)
from .path_spec import AxisAlignedPathSpec, CompositePathSpec, PathSpec, PathSpecTypes


def make_voltage_integral(path_spec: PathSpecTypes) -> VoltageIntegralTypes:
    """Create a voltage path integral from a path specification.

    Parameters
    ----------
    path_spec : PathSpecTypes
        Specification defining the path for voltage integration. Can be either an axis-aligned or
        custom path specification.

    Returns
    -------
    VoltageIntegralTypes
        Voltage path integral instance corresponding to the provided specification type.
    """
    v_integral = None
    if isinstance(path_spec, AxisAlignedPathSpec):
        v_integral = VoltageIntegralAxisAligned(**path_spec.dict(exclude={"type"}))
    elif isinstance(path_spec, PathSpec):
        v_integral = CustomVoltageIntegral2D(**path_spec.dict(exclude={"type"}))
    return v_integral


def make_current_integral(path_spec: PathSpecTypes) -> CurrentIntegralTypes:
    """Create a current path integral from a path specification.

    Parameters
    ----------
    path_spec : PathSpecTypes
        Specification defining the path for current integration. Can be either an axis-aligned,
        custom, or composite path specification.

    Returns
    -------
    CurrentIntegralTypes
        Current path integral instance corresponding to the provided specification type.
    """
    i_integral = None
    if path_spec is not None:
        if isinstance(path_spec, AxisAlignedPathSpec):
            i_integral = CurrentIntegralAxisAligned(**path_spec.dict(exclude={"type"}))
        elif isinstance(path_spec, PathSpec):
            i_integral = CustomCurrentIntegral2D(**path_spec.dict(exclude={"type"}))
        elif isinstance(path_spec, CompositePathSpec):
            i_integral = _make_composite_current_integral(path_spec)
    return i_integral


def _make_composite_current_integral(
    composite_path_spec: CompositePathSpec,
) -> CompositeCurrentIntegral:
    """Create a composite current path integral from a composite path specification.

    Parameters
    ----------
    composite_path_spec : CompositePathSpec
        Specification defining the composite path for current integration.

    Returns
    -------
    CompositeCurrentIntegral
        Composite current path integral instance corresponding to the provided specification type.
    """
    current_integrals = []
    for path_spec in composite_path_spec.path_specs:
        current_integrals.append(make_current_integral(path_spec))

    field_dict = composite_path_spec.dict(exclude={"type", "path_specs"})
    field_dict["current_integrals"] = current_integrals
    return CompositeCurrentIntegral(**field_dict)
