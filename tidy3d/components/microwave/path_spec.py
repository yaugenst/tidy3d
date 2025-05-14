"""Specifications for defining path integrals."""

from typing import Union

import pydantic.v1 as pd

from ...components.base import Tidy3dBaseModel
from ...components.geometry.base import Box
from ...exceptions import ValidationError
from ..types import ArrayFloat2D, Axis, Direction
from ..validators import assert_line_or_plane


class AxisAlignedPathSpec(Box):
    sign: Direction = pd.Field(
        ...,
        title="Direction of Contour Integral",
        description="Positive indicates current flowing in the positive normal axis direction.",
    )

    extrapolate_to_endpoints: bool = pd.Field(
        False,
        title="Extrapolate to Endpoints",
        description="This parameter is passed to :class:`AxisAlignedPathIntegral` objects when computing the contour integral.",
    )

    snap_contour_to_grid: bool = pd.Field(
        False,
        title="Snap Contour to Grid",
        description="This parameter is passed to :class:`AxisAlignedPathIntegral` objects when computing the contour integral.",
    )

    _line_plane_validator = assert_line_or_plane()


class PathSpec(Tidy3dBaseModel):
    vertices: ArrayFloat2D = pd.Field(
        ...,
        title="Current Integral",
        description="Definition of contour integral for computing current.",
    )

    axis: Axis = pd.Field(
        ..., title="Axis", description="Specifies dimension of the planar axis (0,1,2) -> (x,y,z)."
    )

    position: float = pd.Field(
        ...,
        title="Position",
        description="Position of the plane along the ``axis``.",
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
