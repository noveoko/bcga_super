"""Pure 2D geometry (vector + polygon). Never imports rooms/openings/ops.

Note: pro.geometry (singular module) is GeometryContext for the 3D apply path.
"""
from .vector import _add, _cross, _dot, _len, _mul, _norm, _sub
from .polygon import (
	_AREA_EPS,
	_SPAN_EPS,
	_centroid,
	_clip_half,
	_clip_polygon,
	_dedupe_ring,
	_edge_inward,
	_halfplane_quad,
	_inset_convex,
	_longest_edge_axis,
	_point_in_convex,
	_polygon_area,
	_span_along,
	_valid_poly,
	_width_depth,
)

__all__ = [
	"_add",
	"_sub",
	"_mul",
	"_dot",
	"_cross",
	"_len",
	"_norm",
	"_AREA_EPS",
	"_SPAN_EPS",
	"_centroid",
	"_polygon_area",
	"_point_in_convex",
	"_clip_polygon",
	"_dedupe_ring",
	"_halfplane_quad",
	"_clip_half",
	"_valid_poly",
	"_edge_inward",
	"_inset_convex",
	"_longest_edge_axis",
	"_span_along",
	"_width_depth",
]
