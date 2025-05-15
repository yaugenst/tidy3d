"""Module for automatic determination of voltage and current integration paths."""

from itertools import chain

import shapely

from ..base import Tidy3dBaseModel
from ..geometry.base import Box, ClipOperation, Geometry
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
    """Automatically determines current integration paths based on structure geometry.

    This class analyzes the geometry of conductors in a simulation cross-section to determine
    appropriate paths for computing current line integrals. These paths are used
    in terminal impedance calculations and mode solving.

    The paths are chosen by:
    1. Finding and merging conductor surfaces that intersect with the plane
    2. Creating current paths that enclose individual conductors
    """

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
        prop_list = [is_conductor(structure.medium) for structure in structures]
        # merge geometries
        geos = merging_geometries_on_plane(geometry_list, plane, prop_list)
        conductor_geos = [item[1] for item in geos if item[0]]
        polygon_list = [ClipOperation.to_polygon_list(geo) for geo in conductor_geos]
        return list(chain.from_iterable(polygon_list))

    @staticmethod
    def create_current_path_specs(
        mode_plane: Box, structures: list[Structure], grid: Grid, field_data_colocated: bool = False
    ) -> tuple[CompositePathSpec, list[Shapely]]:
        """Creates path specifications for path integrals that encompass each isolated conductor in the modal plane.

        This method identifies isolated conductor geometries in the given plane and creates
        current paths that enclose each conductor. The paths are snapped to the simulation grid
        to ensure alignment with field data.

        Parameters
        ----------
        mode_plane : Box
            The cross-sectional plane where current paths are determined.
        structures : list[Structure]
            List of structures in the simulation.
        grid : Grid
            Simulation grid for snapping paths.
        field_data_colocated : bool
            Whether field data is colocated with grid points.

        Returns
        -------
            tuple[CompositePathSpec, list[Shapely]]: Composite path specification and list of merged conductor geometries.
        """

        def bounding_box_from_shapely(geom: Shapely, normal_axis, normal_center):
            """Helper to convert the shapely geometry bounds to a Box."""
            bounds = geom.bounds
            rmin = Geometry.unpop_axis(normal_center, (bounds[0], bounds[1]), normal_axis)
            rmax = Geometry.unpop_axis(normal_center, (bounds[2], bounds[3]), normal_axis)
            return Box.from_bounds(rmin, rmax)

        conductor_polygons = AutoPathSpec._get_isolated_conductors_as_shapely(
            mode_plane, structures
        )
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

        _, min_b = Geometry.pop_axis(mode_plane.bounds[0], normal_axis)
        _, max_b = Geometry.pop_axis(mode_plane.bounds[1], normal_axis)
        shapely_port = Geometry.make_shapely_box(min_b[0], min_b[1], max_b[0], max_b[1])
        shapely_port_boundary = shapely.LineString(shapely_port.exterior)

        current_integral_specs = []
        for shape in conductor_polygons:
            if not shapely_port_boundary.touches(shape):
                box = bounding_box_from_shapely(shape, normal_axis, mode_plane.center[normal_axis])
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

        for path_spec in current_integral_specs:
            assert not (
                AutoPathSpec._check_path_intersects_with_conductors(conductor_polygons, path_spec)
            ), "Cannot automate path setup."
        path_spec = CompositePathSpec(
            center=mode_plane.center,
            size=mode_plane.size,
            path_specs=current_integral_specs,
            sum_spec="split",
        )
        return path_spec, conductor_polygons

    @staticmethod
    def _check_path_intersects_with_conductors(polygon_list: Shapely, path: Box) -> bool:
        """Makes sure the path of the integral does not intersect with conductor shapes.

        Parameters
        ----------
        geos : Shapely
            Merged conductor geometries.
        path : Box
            Path specification.

        Returns
        -------
            bool: True if the path intersects with any conductor geometry, False otherwise.
        """
        normal_axis = path.size.index(0.0)
        min, max = path.bounds
        _, min = Geometry.pop_axis(min, normal_axis)
        _, max = Geometry.pop_axis(max, normal_axis)
        path_shapely = Geometry.make_shapely_box(min[0], min[1], max[0], max[1])
        for polygon in polygon_list:
            if path_shapely.touches(polygon):
                return True
        return False
