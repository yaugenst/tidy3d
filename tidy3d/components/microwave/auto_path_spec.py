"""Specification for defining microwave terminals for the purpose of calculating transmission line impedance."""

import shapely

from ..base import Tidy3dBaseModel
from ..geometry.base import Box, Geometry
from ..geometry.utils import (
    SnapBehavior,
    SnapLocation,
    SnappingSpec,
    merging_geometries_on_plane,
    snap_box_to_grid,
)
from ..grid.grid import Grid
from ..structure import Structure
from ..types import Shapely
from .path_spec import AxisAlignedPathSpec, CompositePathSpec


class AutoPathSpec(Tidy3dBaseModel):
    @staticmethod
    def _get_isolated_conductors_as_shapely(
        plane: Box, structures: list[Structure]
    ) -> list[Shapely]:
        """Find and merge all structures representing conductors that intersect the `plane`"""
        from ..medium import LossyMetalMedium, Medium

        def is_conductor(med: Medium) -> bool:
            return med.is_pec or isinstance(med, LossyMetalMedium)

        geometry_list = [structure.geometry for structure in structures]
        # For metal, we don't distinguish between LossyMetal and PEC,
        # so they'll be merged to PEC. Other materials are considered as dielectric.
        geometry_list = [
            structure.geometry for structure in structures if is_conductor(structure.medium)
        ]
        # merge geometries
        geos = merging_geometries_on_plane(geometry_list, plane, [True] * len(geometry_list))
        return [item[1] for item in geos]

    @staticmethod
    def _create_current_paths(
        mode_plane: Box, structures: list[Structure], grid: Grid, field_data_colocated: bool = False
    ) -> tuple[CompositePathSpec, list[Shapely]]:
        """Creates the current path integrals that encompass each isolated conductor in the modal plane."""

        def bounding_box_from_shapely(geom: Shapely, normal_axis, normal_center):
            """Helper to convert the shapely geometry bounds to a Box."""
            bounds = geom.bounds
            rmin = Geometry.unpop_axis(normal_center, (bounds[0], bounds[1]), normal_axis)
            rmax = Geometry.unpop_axis(normal_center, (bounds[2], bounds[3]), normal_axis)
            return Box.from_bounds(rmin, rmax)

        merged_geos = AutoPathSpec._get_isolated_conductors_as_shapely(mode_plane, structures)
        normal_axis = mode_plane.size.index(0.0)
        # Get desired snapping behavior of box enclosed conductors.
        # Ideally, just large enough to coincide with the H field positions outside of the conductor.
        # So about a half grid cell, when the metal boundary is coincident with grid boundaries.
        behavior = [SnapBehavior.Expand] * 3
        location = [SnapLocation.Center] * 3
        behavior[normal_axis] = SnapBehavior.Off
        margin = (0, 0, 0)
        if field_data_colocated:
            # To avoid interpolated H field near metal surface
            margin = (2, 2, 2)
        snap_spec = SnappingSpec(location=location, behavior=behavior, margin=margin)

        min_b = mode_plane.bounds[0]
        max_b = mode_plane.bounds[1]
        shapely_port = Geometry.make_shapely_box(min_b[1], min_b[2], max_b[1], max_b[2])
        shapely_port_boundary = shapely.LineString(shapely_port.exterior)

        current_integral_specs = []
        for shape in merged_geos:
            if not shapely_port_boundary.touches(shape):
                box = bounding_box_from_shapely(shape, normal_axis, min_b[0])
                size = list(box.size)
                box = box.updated_copy(size=size)
                box_snapped = snap_box_to_grid(grid, box, snap_spec)
                path_spec = AxisAlignedPathSpec(
                    center=box_snapped.center,
                    size=box_snapped.size,
                    sign="+",
                    extrapolate_to_endpoints=False,
                    snap_contour_to_grid=True,
                )
                current_integral_specs.append(path_spec)
                print(box_snapped.bounds)
        for path_spec in current_integral_specs:
            assert not any(
                AutoPathSpec._check_path_intersects_with_conductors(merged_geos, path_spec)
            ), "Cannot automate path setup."
        path_spec = CompositePathSpec(
            center=mode_plane.center,
            size=mode_plane.size,
            path_specs=current_integral_specs,
            sum_spec="split",
        )
        return path_spec, merged_geos

    @staticmethod
    def _check_path_intersects_with_conductors(geos: Shapely, path: Box) -> bool:
        """Makes sure the path of the integral does not intersect with conductor shapes."""
        normal_axis = path.size.index(0.0)
        min, max = path.bounds
        _, min = Geometry.pop_axis(min, normal_axis)
        _, max = Geometry.pop_axis(max, normal_axis)
        path_shapely = Geometry.make_shapely_box(min[0], min[1], max[0], max[1])
        return path_shapely.touches(geos)
