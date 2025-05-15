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
    v_integral = None
    if isinstance(path_spec, AxisAlignedPathSpec):
        v_integral = VoltageIntegralAxisAligned(**path_spec.dict(exclude={"type"}))
    elif isinstance(path_spec, PathSpec):
        v_integral = CustomVoltageIntegral2D(**path_spec.dict(exclude={"type"}))
    return v_integral


def make_current_integral(path_spec: PathSpecTypes) -> CurrentIntegralTypes:
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
    current_integrals = []
    for path_spec in composite_path_spec.path_specs:
        current_integrals.append(make_current_integral(path_spec))

    field_dict = composite_path_spec.dict(exclude={"type", "path_specs"})
    field_dict["current_integrals"] = current_integrals
    return CompositeCurrentIntegral(**field_dict)
