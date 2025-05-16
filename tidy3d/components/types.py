"""Defines 'types' that various fields can be"""

import numbers
from typing import Annotated, Any, Literal, Optional, Union

import numpy as np
from pydantic import (
    BeforeValidator,
    Field,
    NonNegativeFloat,
    PositiveFloat,
)
from pydantic.functional_serializers import PlainSerializer

try:
    from matplotlib.axes import Axes
except ImportError:
    Axes = None

from shapely.geometry.base import BaseGeometry

# type tag default name
TYPE_TAG_STR = "type"


def discriminated_union(union, discriminator=TYPE_TAG_STR):
    return Annotated[union, Field(discriminator=discriminator)]


""" Numpy Arrays """


def _from_complex_dict(v):
    if isinstance(v, dict) and "real" in v and "imag" in v:
        return np.asarray(v["real"]) + 1j * np.asarray(v["imag"])
    return v


def _coerce(v, *, dtype, ndim, shape, forbid_nan, scalar_to_1d):
    """Convert input to a NumPy array with constraints.

    Raises
    ------
    ValueError
        - If conversion to an array fails.
        - If the array ends up with dtype=object (unsupported element type).
        - If the number of dimensions or shape does not match the expectations.
        - If ``forbid_nan`` is ``True`` and the array contains NaN values.
    """
    try:
        arr = np.asarray(v) if dtype is None else np.asarray(v, dtype=dtype)
    except Exception as e:
        raise ValueError(f"cannot convert {type(v).__name__!r} to a NumPy array") from e
    if arr.dtype == np.dtype("object"):
        raise ValueError(f"unsupported element type {type(v).__name__!r} for array coercion")

    if arr.ndim == 0 and scalar_to_1d and ndim == 1:
        arr = arr.reshape(1)
    if ndim is not None and arr.ndim != ndim:
        raise ValueError(f"expected {ndim}-D, got {arr.ndim}-D")
    if shape is not None and tuple(arr.shape) != shape:
        raise ValueError(f"expected shape {shape}, got {tuple(arr.shape)}")
    if forbid_nan and np.any(np.isnan(arr)):
        raise ValueError("array contains NaN")
    return arr


def _auto_serializer(a, _):
    """Serializes numpy arrays and scalars for JSON."""
    if isinstance(a, complex) or (
        hasattr(np, "complexfloating") and isinstance(a, np.complexfloating)
    ):
        return {"real": float(a.real), "imag": float(a.imag)}
    if isinstance(a, np.ndarray):
        if np.iscomplexobj(a):
            return {"real": a.real.tolist(), "imag": a.imag.tolist()}
        else:
            return a.tolist()
    if isinstance(a, float) or (hasattr(np, "floating") and isinstance(a, np.floating)):
        return float(a)  # Ensure basic Python float
    if isinstance(a, int) or (hasattr(np, "integer") and isinstance(a, np.integer)):
        return int(a)  # Ensure basic Python int
    if hasattr(np, "number") and isinstance(a, np.number):
        return a.item()
    return a


def array_alias(
    *,
    dtype: Optional[type] = None,
    ndim: Optional[int] = None,
    shape: Optional[tuple[int, ...]] = None,
    forbid_nan: bool = True,
    scalar_to_1d: bool = False,
):
    """Return an `Annotated[np.ndarray, ...]` with checks."""
    validators = [
        BeforeValidator(_from_complex_dict),
        BeforeValidator(
            lambda v: _coerce(
                v,
                dtype=np.dtype(dtype) if dtype is not None else None,
                ndim=ndim,
                shape=shape,
                forbid_nan=forbid_nan,
                scalar_to_1d=scalar_to_1d,
            )
        ),
    ]

    serializer = PlainSerializer(_auto_serializer, when_used="json")

    return Annotated[np.ndarray, *validators, serializer]


ArrayLike = array_alias()

ArrayInt1D = array_alias(dtype=int, ndim=1, scalar_to_1d=True)

ArrayFloat = array_alias(dtype=float)
ArrayFloat1D = array_alias(dtype=float, ndim=1, scalar_to_1d=True)
ArrayFloat2D = array_alias(dtype=float, ndim=2)
ArrayFloat3D = array_alias(dtype=float, ndim=3)
ArrayFloat4D = array_alias(dtype=float, ndim=4)

ArrayComplex = array_alias(dtype=complex)
ArrayComplex1D = array_alias(dtype=complex, ndim=1, scalar_to_1d=True)
ArrayComplex2D = array_alias(dtype=complex, ndim=2)
ArrayComplex3D = array_alias(dtype=complex, ndim=3)
ArrayComplex4D = array_alias(dtype=complex, ndim=4)

TensorReal = array_alias(dtype=float, ndim=2, shape=(3, 3))
MatrixReal4x4 = array_alias(dtype=float, ndim=2, shape=(4, 4))

""" Complex Values """


def _parse_complex(v: Any) -> complex:
    if isinstance(v, complex):
        return v

    if isinstance(v, dict) and "real" in v and "imag" in v:
        return complex(v["real"], v["imag"])

    if isinstance(v, numbers.Number):
        return complex(v)

    if hasattr(v, "__complex__"):
        try:
            return complex(v.__complex__())
        except Exception:
            pass

    if isinstance(v, (list, tuple)) and len(v) == 2:
        return complex(v[0], v[1])

    return v


Complex = Annotated[
    complex,
    BeforeValidator(_parse_complex),
    PlainSerializer(
        lambda z, _: {"real": z.real, "imag": z.imag},
        when_used="json",
        return_type=dict,
    ),
]

""" symmetry """

Symmetry = Literal[0, -1, 1]
ScalarSymmetry = Literal[0, 1]

""" geometric """

Size1D = NonNegativeFloat
Size = tuple[Size1D, Size1D, Size1D]
Coordinate = tuple[float, float, float]
CoordinateOptional = tuple[Optional[float], Optional[float], Optional[float]]
Coordinate2D = tuple[float, float]
Bound = tuple[Coordinate, Coordinate]
GridSize = Union[PositiveFloat, tuple[PositiveFloat, ...]]
Axis = Literal[0, 1, 2]
Axis2D = Literal[0, 1]
Shapely = BaseGeometry
PlanePosition = Literal["bottom", "middle", "top"]
ClipOperationType = Literal["union", "intersection", "difference", "symmetric_difference"]
BoxSurface = Literal["x-", "x+", "y-", "y+", "z-", "z+"]
LengthUnit = Literal["nm", "μm", "um", "mm", "cm", "m"]

""" medium """

# custom medium
InterpMethod = Literal["nearest", "linear"]

PoleAndResidue = tuple[Complex, Complex]
PolesAndResidues = tuple[PoleAndResidue, ...]
FreqBoundMax = float
FreqBoundMin = float
FreqBound = tuple[FreqBoundMin, FreqBoundMax]

PermittivityComponent = Literal["xx", "xy", "xz", "yx", "yy", "yz", "zx", "zy", "zz"]

""" sources """

Polarization = Literal["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]
Direction = Literal["+", "-"]

""" monitors """

EMField = Literal["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]
FieldType = Literal["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]
FreqArray = ArrayFloat1D
ObsGridArray = ArrayFloat1D
PolarizationBasis = Literal["linear", "circular"]
AuxField = Literal["Nfx", "Nfy", "Nfz"]

""" plotting """

Ax = Axes
PlotVal = Literal["real", "imag", "abs"]
FieldVal = Literal["real", "imag", "abs", "abs^2", "phase"]
RealFieldVal = Literal["real", "abs", "abs^2"]
PlotScale = Literal["lin", "dB"]
ColormapType = Literal["divergent", "sequential", "cyclic"]

""" mode solver """

ModeSolverType = Literal["tensorial", "diagonal"]
EpsSpecType = Literal["diagonal", "tensorial_real", "tensorial_complex"]

""" mode tracking """

TrackFreq = Literal["central", "lowest", "highest"]

""" lumped elements"""

LumpDistType = Literal["off", "laterally_only", "on"]

""" dataset """

xyz = Literal["x", "y", "z"]
UnitsZBF = Literal["mm", "cm", "in", "m"]
