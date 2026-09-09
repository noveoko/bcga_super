from pro import context
from pro.rule_context import resolve_rule_context
from pro.openings import decompose_spans, opening_from, slice_wall_polygon

from .op_partition import _shape_from_poly, _shape_xy
from .shape import Shape2d
import pro.op_openings


class _ExtrudeDef:
    def __init__(self, depth):
        self.depth = float(depth)
        self.interior = False
        self.keepOriginal = False
        self.inheritMaterialAll = True
        self.inheritMaterialSide = True
        self.inheritMaterialExtruded = False
        self.alwaysAlongOriginal = False


def _extrude(shape, depth):
    if depth <= 1e-9:
        return
    shape.extrude(_ExtrudeDef(depth))


class Openings(pro.op_openings.Openings):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        if not isinstance(shape, Shape2d):
            return
        raw = getattr(shape, "openings", None) or []
        openings = [opening_from(o) for o in raw]
        if not openings:
            _extrude(shape, self.wall_height)
            return

        poly, z0 = _shape_xy(shape)
        from pro.rooms import _longest_edge_axis
        length, _edgeDir, _mid = _longest_edge_axis(poly)
        spans = decompose_spans(length, openings, min_pier=self.min_pier)
        if not any(s["kind"] == "gap" for s in spans):
            _extrude(shape, self.wall_height)
            return

        first = openings[0]
        sill = first.sill_height
        door_h = first.height
        head = min(self.wall_height, sill + door_h)
        lintel_h = self.wall_height - head
        mat = shape.face.material_index

        if lintel_h > 1e-6:
            lintel = _shape_from_poly(poly, z0 + head)
            lintel.face.material_index = mat
            _extrude(lintel, lintel_h)

        for span in spans:
            piece = slice_wall_polygon(poly, span["start"], span["end"])
            if not piece:
                continue
            if span["kind"] == "solid":
                pier = _shape_from_poly(piece, z0)
                pier.face.material_index = mat
                _extrude(pier, head)
            elif sill > 1e-6:
                band = _shape_from_poly(piece, z0)
                band.face.material_index = mat
                _extrude(band, sill)

        # Game-export door leaves: one record per gap
        from pro.doors import door_record
        from pro.rooms import _centroid, _sub, _norm
        plot = getattr(context, "cityBlock", None) or {}
        plot_id = plot.get("id") if isinstance(plot, dict) else None
        kind = getattr(shape, "door_kind", None) or "interior"
        inward = None
        if isinstance(plot, dict) and plot.get("centroid"):
            pc = plot["centroid"]
            wc = _centroid(poly)
            inward = _norm(_sub((pc[0], pc[1]), wc))
        doors = getattr(context, "gameDoors", None)
        if doors is None:
            ctx.gameDoors = []
            doors = ctx.gameDoors
        for span in spans:
            if span["kind"] != "gap":
                continue
            doors.append(
                door_record(
                    poly, z0, span["opening"],
                    kind=kind, plot_id=plot_id, inward=inward,
                )
            )

        ctx.facesForRemoval.append(shape.face)
