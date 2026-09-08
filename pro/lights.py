"""
Ceiling point-light placement. No bpy.

partition() calls this once per floor when lights=True. The result is a list
of world-space Point lights hanging under the slab, meant to be spawned as
Blender lamps/empties and written to a *.lights.json sidecar for Unreal.
"""
import math
import random as randomlib


MIN_AREA = 3.5
LARGE_AREA = 12.0
DEFAULT_DROP = 0.22
DEFAULT_DENSITY = (0.4, 0.75)
WARM = (1.0, 0.94, 0.82)
CANDELA = 600.0


def _span_axes(room):
    poly = room.get("polygon") or []
    if len(poly) < 2:
        return (1.0, 0.0), 1.0
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if dx >= dy:
        return (1.0, 0.0), dx
    return (0.0, 1.0), dy


def _record(x, y, z, room, z_floor, height, plot_id=None):
    area = float(room.get("area") or 0.0)
    radius = max(4.0, min(10.0, math.sqrt(max(area, 1.0)) * 1.2))
    return {
        "type": "Point",
        "location": [round(x, 4), round(y, 4), round(z, 4)],
        "intensity": CANDELA,
        "intensity_unit": "candela",
        "color": list(WARM),
        "radius": round(radius, 2),
        "cast_shadows": True,
        "z_floor": round(float(z_floor), 4),
        "height": round(float(height), 4),
        "area": round(area, 3),
        "role": room.get("role") or "room",
        "plot_id": plot_id,
    }


def place_ceiling_lights(
    rooms,
    z_floor,
    height,
    seed=None,
    drop=DEFAULT_DROP,
    min_area=MIN_AREA,
    large_area=LARGE_AREA,
    density_range=DEFAULT_DENSITY,
    rng=None,
    plot_id=None,
):
    """
    Pick a random subset of rooms on one floor and hang 1–2 point lights
    under the ceiling (z = z_floor + height - drop).

    Returns a list of light dicts (see _record). Empty if nothing qualifies.
    """
    if height is None or float(height) <= 0.05:
        return []
    if rng is None:
        rng = randomlib.Random(seed)
    z = float(z_floor) + float(height) - float(drop)
    regular, halls = [], []
    for room in rooms or []:
        area = float(room.get("area") or 0.0)
        if area < min_area:
            continue
        if (room.get("role") or "room") in ("hall", "corridor"):
            halls.append(room)
        else:
            regular.append(room)
    if not regular and not halls:
        return []

    density = rng.uniform(*density_range)
    chosen = []
    if regular:
        n = max(1, int(round(len(regular) * density)))
        n = min(n, len(regular))
        chosen.extend(rng.sample(regular, n))
    if halls:
        n_h = int(round(len(halls) * density * 0.5))
        n_h = min(n_h, len(halls))
        if n_h:
            chosen.extend(rng.sample(halls, n_h))

    lights = []
    for room in chosen:
        cx, cy = room["centroid"]
        lights.append(_record(cx, cy, z, room, z_floor, height, plot_id))
        if float(room.get("area") or 0.0) > large_area:
            axis, span = _span_axes(room)
            ox, oy = axis[0] * 0.25 * span, axis[1] * 0.25 * span
            lights.append(_record(cx + ox, cy + oy, z, room, z_floor, height, plot_id))
    return lights


def lights_sidecar(records):
    """JSON document Unreal (or any importer) can spawn PointLights from."""
    lights = []
    floors = sorted({r.get("z_floor") for r in records})
    floor_index = {z: i for i, z in enumerate(floors)}
    for i, r in enumerate(records):
        plot = r.get("plot_id")
        fi = floor_index.get(r.get("z_floor"), 0)
        name = "LIGHT_%s_%d_%d" % (plot if plot is not None else 0, fi, i)
        entry = dict(r)
        entry["name"] = name
        entry["floor"] = fi
        lights.append(entry)
    return {
        "units": "m",
        "axis": "blender_z_up",
        "lights": lights,
    }
