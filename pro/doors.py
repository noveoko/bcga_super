"""
Door transform helpers for game export. No bpy.

Builds hinge-origin door records from a wall polygon + Opening, for the
city_game.json sidecar and Blender door-leaf meshes.
"""
import math

from .openings import opening_from
from .rooms import _add, _centroid, _dot, _longest_edge_axis, _mul, _span_along


def door_record(poly, z0, opening, kind="interior", plot_id=None, inward=None):
    """
    One door leaf: origin at the left jamb (hinge), +Z up.

    inward: optional (dx, dy) unit vector into the room / building; if None,
    uses the wall's +perp.
    """
    o = opening_from(opening)
    length, edgeDir, _mid = _longest_edge_axis(poly)
    lo, hi = _span_along(poly, edgeDir)
    c = _centroid(poly)
    perp = (-edgeDir[1], edgeDir[0])
    # `offset` is measured from `lo` along the *original* edgeDir. Compute the
    # physical target position (t) in that original frame first, then, if we
    # flip the frame below, re-express that same physical point in the new
    # (reversed) frame by negating it -- rather than reusing the raw offset
    # against a flipped `lo`, which would place the hinge at the mirror-image
    # position along the wall instead of at the real opening.
    t = lo + o.offset
    if inward is not None:
        # flip edgeDir so hinge "left" matches inward cross up ≈ edge
        if _dot(perp, inward) < 0:
            perp = (-perp[0], -perp[1])
            edgeDir = (-edgeDir[0], -edgeDir[1])
            lo, hi = -hi, -lo
            t = -t
    hinge_xy = _add(c, _mul(edgeDir, t - _dot(c, edgeDir)))
    # sit hinge on the inner face of a thick wall when possible
    thick = 0.04
    hinge_xy = _add(hinge_xy, _mul(perp, 0.0))
    z = float(z0) + float(o.sill_height)
    yaw = math.atan2(edgeDir[1], edgeDir[0])
    return {
        "location": [round(hinge_xy[0], 4), round(hinge_xy[1], 4), round(z, 4)],
        "hinge_axis": [0.0, 0.0, 1.0],
        "forward": [round(perp[0], 4), round(perp[1], 4), 0.0],
        "edge": [round(edgeDir[0], 4), round(edgeDir[1], 4), 0.0],
        "yaw": round(yaw, 6),
        "swing_deg": 90.0,
        "width": round(float(o.width), 4),
        "height": round(float(o.height), 4),
        "thickness": thick,
        "kind": kind,
        "plot_id": plot_id,
    }


def game_sidecar(doors, buildings, player_start, lights_ref=None):
    named = []
    for i, d in enumerate(doors):
        e = dict(d)
        plot = e.get("plot_id")
        e["name"] = e.get("name") or "Door_%s_%d" % (plot if plot is not None else 0, i)
        named.append(e)
    doc = {
        "units": "m",
        "axis": "blender_z_up",
        "player_start": player_start,
        "doors": named,
        "buildings": buildings,
    }
    if lights_ref:
        doc["lights_ref"] = lights_ref
    return doc
