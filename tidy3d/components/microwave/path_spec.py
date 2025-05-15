"""Specifications for defining path integrals."""

from typing import Literal, Union

import pydantic.v1 as pd

from ...components.base import Tidy3dBaseModel
from ...components.geometry.base import Box
from ...exceptions import ValidationError
from ..types import ArrayFloat2D, Axis, Direction
from ..validators import assert_line_or_plane


class AxisAlignedPathSpec(Box):
    """Specification for axis-aligned line integrals or contour integrals (current or voltage).

    A line integral is specified by using setting a size with only one nonzero dimension,
    whereas a contour integral is specified by setting a size with two nonzero dimensions
    in which case the integral will be computed along the perimeter of the box.
    This class only stores the parameters needed to later instantiate
    a current or voltage path integral along an axis-aligned box.
    It does not perform any integration itself.
    """

    sign: Direction = pd.Field(
        ...,
        title="Direction of Line or Contour Integral",
        description="A positive signs corresponds with a counter-clockwise direction for contour integrals and in the positive axis direction for line integrals.",
    )

    extrapolate_to_endpoints: bool = pd.Field(
        True,
        title="Extrapolate to Endpoints",
        description="If True, field values will be extrapolated to line endpoints when computing the integral.",
    )

    snap_contour_to_grid: bool = pd.Field(
        True,
        title="Snap Contour to Grid",
        description="If True, the integration path will be snapped to the grid when computing the integral.",
    )

    _line_plane_validator = assert_line_or_plane()


class PathSpec(Tidy3dBaseModel):
    """Specification for a custom path integral (current or voltage).

    This class only stores the parameters needed to later instantiate
    a current or voltage path integral along an arbitrary path.
    It does not perform any integration itself.
    """

    vertices: ArrayFloat2D = pd.Field(
        ...,
        title="Path Vertices",
        description="Ordered list of vertices defining the integration path for current or voltage calculation.",
    )

    axis: Axis = pd.Field(
        ...,
        title="Normal Axis",
        description="Specifies the normal dimension (0,1,2) -> (x,y,z) for the plane containing the integration path.",
    )

    position: float = pd.Field(
        ...,
        title="Position",
        description="Position along the normal axis where the integration path lies.",
    )

    @pd.validator("vertices", always=True)
    def _correct_shape(cls, val):
        """Makes sure vertices size is correct."""
        # overall shape of vertices
        if val.shape[1] != 2:
            raise ValidationError(
                "'PathSpec.vertices' must be a 2 dimensional array shaped (N, 2). "
                f"Given array with shape of '{val.shape}'."
            )
        return val


PathSpecTypes = Union[AxisAlignedPathSpec, PathSpec]


class CompositePathSpec(Box):
    """Specification for a composite current integral.

    This class is used to set up a CompositeCurrentIntegral, which combines
    multiple current integrals. It does not perform any integration itself.
    """

    path_specs: list[PathSpecTypes] = pd.Field(
        ...,
        title="Path Specifications",
        description="Definition of the disjoint path specifications for each isolated contour integral.",
    )

    sum_spec: Literal["sum", "split"] = pd.Field(
        ...,
        title="Sum Specification",
        description="Determines the method used to combine the currents calculated by the different current integrals  defined by ``path_specs``."
        "``sum`` simply adds all currents, while ``split`` keeps contributions with opposite phase separate, which allows for isolating "
        "the current flowing in opposite directions. In ``split`` version, the current returned is the maximum of the two contributions.",
    )
