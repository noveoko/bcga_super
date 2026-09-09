"""
Builds a full organic city in Blender from a layout JSON (see
pro/city/layout.py) and a BCGA rule file.

Two-step workflow, matching generate.py's own split of concerns (pure
layout computation vs. Blender geometry generation):

    # Step 1 (ordinary Python, needs numpy+scipy -- NOT run inside Blender):
    python3 pro/city/layout.py --output /tmp/city.json --blocks 80 --radius 250 --seed 1

    # Step 2 (inside Blender; does NOT need numpy/scipy):
    blender --background --factory-startup --python city_builder.py -- \\
        --layout /tmp/city.json --rule examples/city_building.py --output /tmp/city.blend

Each building is applied inside a GenerationSession with
session.set_city_block(...). Rule files should read plot metadata via
city_block() inside Begin() (see examples/city_building.py); legacy
module-level context.cityBlock reads still work when the rule is reloaded.
"""
import argparse
import json
import os
import sys


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        prog="city_builder.py",
        description="Build a full organic city from a layout JSON and a BCGA rule file.",
    )
    parser.add_argument("--layout", required=True, help="Path to a layout JSON from pro/city/layout.py")
    parser.add_argument("--rule", required=True, help="BCGA rule .py file used for every block (see context.cityBlock)")
    parser.add_argument("--output", required=True, help="Output .blend/.obj/.glb/.fbx file")
    parser.add_argument("--road-width-primary", type=float, default=8.0)
    parser.add_argument("--road-width-secondary", type=float, default=4.5)
    parser.add_argument("--road-width-local", type=float, default=3.0,
                        help="Width for 'local' hierarchy roads, used when the layout was "
                             "generated with road_classification='functional' (arterial/"
                             "collector/local) instead of the default primary/secondary scheme")
    parser.add_argument("--setback", type=float, default=3.0,
                        help="Shrink each building footprint toward its centroid (meters)")
    parser.add_argument("--skip-roads", action="store_true")
    parser.add_argument("--skip-ground", action="store_true")
    parser.add_argument("--terrain-seed", type=int, default=0,
                        help="Seed for the ground's cosmetic surface noise (independent of the "
                             "layout seed; same seed -> same bumps)")
    parser.add_argument("--max-blocks", type=int, default=None, help="Cap the number of blocks built (for quick previews)")
    parser.add_argument(
        "--game-export", action="store_true",
        help="Also write city_game.json + apply road modifiers and prefer FBX-ready meshes "
             "for Unreal (doors, lights, player_start sidecars)",
    )
    return parser.parse_args(argv)


def _clear_scene():
    import bpy
    bpy.ops.object.select_all(action="SELECT")
    if bpy.context.selected_objects:
        bpy.ops.object.delete()


def _road_profile_node_group():
    """
    Builds (or reuses) a Geometry Nodes group that turns a curve into a
    flat ribbon mesh of a given width: Curve to Mesh with a straight-line
    profile perpendicular to the curve, scaled by a "Width" group input.
    Verified independently to produce correct, exactly-width-wide ribbon
    geometry (see the accompanying test suite).
    """
    import bpy

    existing = bpy.data.node_groups.get("BCGA_RoadProfile")
    if existing is not None:
        return existing

    ng = bpy.data.node_groups.new("BCGA_RoadProfile", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Width", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    group_in = ng.nodes.new("NodeGroupInput")
    group_out = ng.nodes.new("NodeGroupOutput")
    curve_to_mesh = ng.nodes.new("GeometryNodeCurveToMesh")
    curve_line = ng.nodes.new("GeometryNodeCurvePrimitiveLine")
    set_mat = ng.nodes.new("GeometryNodeSetMaterial")
    mul_neg = ng.nodes.new("ShaderNodeMath")
    mul_neg.operation = "MULTIPLY"
    mul_neg.inputs[1].default_value = -0.5
    mul_pos = ng.nodes.new("ShaderNodeMath")
    mul_pos.operation = "MULTIPLY"
    mul_pos.inputs[1].default_value = 0.5
    combine_start = ng.nodes.new("ShaderNodeCombineXYZ")
    combine_end = ng.nodes.new("ShaderNodeCombineXYZ")

    ng.links.new(group_in.outputs["Geometry"], curve_to_mesh.inputs["Curve"])
    ng.links.new(group_in.outputs["Width"], mul_neg.inputs[0])
    ng.links.new(group_in.outputs["Width"], mul_pos.inputs[0])
    ng.links.new(mul_neg.outputs[0], combine_start.inputs["X"])
    ng.links.new(mul_pos.outputs[0], combine_end.inputs["X"])
    ng.links.new(combine_start.outputs["Vector"], curve_line.inputs["Start"])
    ng.links.new(combine_end.outputs["Vector"], curve_line.inputs["End"])
    ng.links.new(curve_line.outputs["Curve"], curve_to_mesh.inputs["Profile Curve"])
    ng.links.new(curve_to_mesh.outputs["Mesh"], set_mat.inputs["Geometry"])
    ng.links.new(group_in.outputs["Material"], set_mat.inputs["Material"])
    ng.links.new(set_mat.outputs["Geometry"], group_out.inputs["Geometry"])
    return ng


def _socket_id(node_group, name, in_out="INPUT"):
    for item in node_group.interface.items_tree:
        if item.name == name and item.in_out == in_out:
            return item.identifier
    raise RuntimeError("node group has no '%s' %s socket" % (name, in_out))


def _width_socket_id(node_group):
    return _socket_id(node_group, "Width")


def _diffuse_material(name, rgb, roughness=0.85):
    import bpy
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _shrink_towards_centroid(polygon, centroid, setback):
    import math
    if setback <= 0 or len(polygon) < 3:
        return polygon
    cx, cy = centroid
    avg = sum(math.hypot(x - cx, y - cy) for x, y in polygon) / len(polygon)
    if avg <= 1e-6:
        return polygon
    scale = max(0.4, min(0.92, 1.0 - setback / avg))
    return [[cx + scale * (x - cx), cy + scale * (y - cy)] for x, y in polygon]


def _extrude_mesh(obj, height):
    import bmesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if hasattr(bm.faces, "ensure_lookup_table"):
        bm.faces.ensure_lookup_table()
    result = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    verts = [g for g in result["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=verts, vec=(0.0, 0.0, height))
    bm.to_mesh(mesh)
    bm.free()


def _setback_for_role(role, defaultSetback):
    return {
        "plaza": 0.0,
        "church": max(defaultSetback, 4.0),
        "synagogue": max(defaultSetback, 3.5),
        "ratusz": max(2.0, defaultSetback * 0.75),
        "kamienica": max(2.0, defaultSetback * 0.8),
        "cottage": defaultSetback + 2.0,
    }.get(role, defaultSetback)


def build_plaza(block):
    import bpy
    from bpro.bl_util import create_footprint_from_points

    create_footprint_from_points(
        bpy.context, block["polygon"], offset=tuple(block["centroid"])
    )
    obj = bpy.context.object
    obj.name = "Rynek_%03d" % block["id"]
    _extrude_mesh(obj, 0.08)
    mat = _diffuse_material("RynekCobble", (0.46, 0.43, 0.38), 0.94)
    obj.data.materials.append(mat)
    cx, cy = block["centroid"]
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16, radius=0.7, depth=1.15, location=(cx, cy, 0.58)
    )
    well = bpy.context.object
    well.name = "RynekWell"
    well.data.materials.append(_diffuse_material("WellStone", (0.40, 0.38, 0.35), 0.9))
    wood = _diffuse_material("StallWood", (0.45, 0.32, 0.18), 0.9)
    cloth = _diffuse_material("StallCloth", (0.55, 0.22, 0.18), 0.85)
    # two rows of market stalls on the square
    for i, (sx, sy) in enumerate((
        (-8, -6), (-2.5, -6), (3, -6), (8.5, -6),
        (-8, 7), (-2.5, 7), (3, 7), (8.5, 7),
    )):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx + sx, cy + sy, 0.55))
        stall = bpy.context.object
        stall.name = "Stall_%02d" % i
        stall.scale = (1.6, 1.1, 0.9)
        stall.data.materials.append(wood if i % 2 == 0 else cloth)
    bpy.ops.object.select_all(action="DESELECT")
    return obj


def _wall_height(plot):
    storeys = int(plot.get("storeys") or 2)
    extra = 1.6 if plot.get("role") == "church" else 0.0
    ground = 4.2 if plot.get("role") == "church" else 3.45
    return 0.4 + ground + max(0, storeys - 1) * 3.15 + 0.25 + extra


def add_chimneys(plot):
    """Brick stacks near the ridge. Skip barns (already low) rarely."""
    import bpy
    import math

    role = plot.get("role")
    if role == "barn":
        count = 1
    elif role in ("church", "ratusz", "synagogue", "school"):
        count = 2
    elif role == "karczma":
        count = 2
    else:
        count = 1 if int(plot.get("storeys") or 1) == 1 else 2

    poly = plot["polygon"]
    if len(poly) < 4:
        return
    p0, p1, p3 = poly[0], poly[1], poly[3]
    wall_h = _wall_height(plot)
    span = min(float(plot.get("width") or 10), float(plot.get("depth") or 10))
    roof_h = wall_h + 0.32 * span * math.tan(math.radians(38))
    brick = _diffuse_material("ChimneyBrick", (0.42, 0.22, 0.16), 0.9)

    for i in range(count):
        along = (i + 1) / (count + 1)
        # 55% back from the street edge, along the frontage
        fx = p0[0] + along * (p1[0] - p0[0])
        fy = p0[1] + along * (p1[1] - p0[1])
        bx = fx + 0.55 * (p3[0] - p0[0])
        by = fy + 0.55 * (p3[1] - p0[1])
        h = 1.5 + 0.35 * i
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, roof_h + h * 0.45))
        chim = bpy.context.object
        chim.name = "Chimney_%03d_%d" % (plot.get("id", 0), i)
        chim.scale = (0.22, 0.28, h * 0.5)
        chim.data.materials.append(brick)
    bpy.ops.object.select_all(action="DESELECT")


def _ground_noise(x, y, seed):
    """
    Small, high-frequency, deterministic dressing so the ground reads as
    real dirt/turf rather than a flat plate. This is deliberately NOT the
    same terrain model used for city-layout siting decisions
    (pro/city/terrain.py's SyntheticTerrain, which works at a much larger
    amplitude/wavelength for road-cost weighting and civic siting) -- this
    one is purely cosmetic, tuned so its bumps are visible at building/
    plot scale (a few meters) without ever competing with the soil-mound
    bump at a wall base or looking like actual hills.
    """
    import math
    phase = (seed % 97) * 0.61
    return (
        0.06 * math.sin(x * 0.9 + phase) * math.cos(y * 0.7 - phase)
        + 0.035 * math.sin((x - y) * 1.6 + phase * 1.3)
        + 0.02 * math.sin(x * 3.1 - phase) * math.cos(y * 2.7 + phase)
    )


def _point_in_polygon(px, py, poly):
    """Standard even-odd ray-cast point-in-polygon test, poly = [(x, y), ...]."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_at_y = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x_at_y:
                inside = not inside
    return inside


def _point_to_segment_dist(px, py, ax, ay, bx, by):
    import math
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _dist_to_polygon(px, py, poly):
    n = len(poly)
    return min(
        _point_to_segment_dist(px, py, poly[i][0], poly[i][1], poly[(i + 1) % n][0], poly[(i + 1) % n][1])
        for i in range(n)
    )


def _prep_footprints(footprints):
    """Precompute a bounding circle per footprint so _soil_mound can cheaply
    skip buildings that are nowhere near a given ground vertex."""
    import math
    prepped = []
    for poly in footprints or []:
        pts = [(p[0], p[1]) for p in poly]
        if len(pts) < 3:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        bbox_r = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
        prepped.append((pts, cx, cy, bbox_r))
    return prepped


def _soil_mound(x, y, prepped_footprints, height=0.22, reach=1.5):
    """
    Real soil settles and mounds slightly against a building's foundation,
    then tapers back down to grade a meter or so out -- it doesn't stop
    dead at the wall line the way a flat ground plane implies. Approximate
    that with an ease-out bump that peaks at each footprint's wall line
    (height) and fades to 0 by `reach` meters out. Points inside a
    footprint are left untouched (hidden under that building's own floor,
    so raising them there would only risk poking the ground mesh through
    the floor for no visible benefit).

    height/reach defaults are tuned to read clearly once the ground disk
    has ~0.5–0.7 m vertex spacing (see build_ground subdiv targeting);
    a 12 cm / 0.9 m mound on a 3 m-spaced mesh is effectively invisible.
    """
    bump = 0.0
    for poly, cx, cy, bbox_r in prepped_footprints:
        if (x - cx) ** 2 + (y - cy) ** 2 > (bbox_r + reach) ** 2:
            continue
        if _point_in_polygon(x, y, poly):
            continue
        d = _dist_to_polygon(x, y, poly)
        if d < reach:
            t = d / reach
            bump = max(bump, height * (1.0 - t) ** 2)
    return bump


def _prep_roads(roads, widthPrimary, widthSecondary, widthLocal):
    import math
    prepped = []
    for r in roads or []:
        (x1, y1), (x2, y2) = r["start"], r["end"]
        half_w = _road_width_for_hierarchy(r.get("hierarchy"), widthPrimary, widthSecondary, widthLocal) / 2.0
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        half_len = math.hypot(x2 - x1, y2 - y1) / 2.0
        prepped.append((x1, y1, x2, y2, half_w, cx, cy, half_len))
    return prepped


def _road_clearance(x, y, prepped_roads, shoulder=0.6):
    """
    0..1 multiplier applied to the ground's noise/mound at (x, y): 0 right
    under a road bed (roads are graded flat -- they must not show the
    ground's cosmetic bumps, and a soil mound would make no sense running
    down the middle of a street), ramping linearly back up to 1 over
    `shoulder` meters past the road's edge so the transition isn't a hard
    seam.
    """
    factor = 1.0
    for x1, y1, x2, y2, half_w, cx, cy, half_len in prepped_roads:
        reach = half_len + half_w + shoulder
        if (x - cx) ** 2 + (y - cy) ** 2 > reach * reach:
            continue
        edge = _point_to_segment_dist(x, y, x1, y1, x2, y2) - half_w
        if edge <= 0:
            return 0.0
        if edge < shoulder:
            factor = min(factor, edge / shoulder)
    return factor


def build_ground(radius, footprints=None, roads=None, road_widths=None, seed=0):
    """
    Ground disk under the whole town. Two things are sculpted into it
    (previously it was a perfectly flat plate):

    - `_ground_noise`: subtle, deterministic undulation everywhere, so the
      ground doesn't read as a sheet of glass.
    - `_soil_mound`: a small rise hugging the outside of every building
      footprint, tapering back to grade over `reach` meters -- mimicking
      how soil actually settles/mounds against a foundation instead of the
      ground stopping dead at the wall with a knife-edge gap.

    - `_road_clearance`: suppresses both of the above back to 0 under every
      road bed (plus a short shoulder past its edge) -- roads are graded
      flat, so without this a road ribbon sitting at a fixed z could end up
      floating above, or half-buried in, a bumpy/mounded patch of ground
      that has no idea a road runs through it.

    `footprints` is the same list of (x, y) polygons already used to build
    each block/plot, and `roads` the same `layout["roads"]` segments (each
    a dict with "start"/"end"/"hierarchy") used to build the road ribbons --
    both already in world-space, matching this disk's coordinate frame (see
    create_footprint_from_points, which places building meshes at their
    absolute polygon coordinates). `road_widths` is an optional
    (primary, secondary, local) tuple matching the widths build_roads() was
    actually called with, so the flattened corridor lines up with the real
    road mesh instead of guessing a width.
    """
    import bpy
    import bmesh
    import math

    disk_r = radius * 1.25
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=disk_r, depth=0.18, location=(0.0, 0.0, -0.14)
    )
    obj = bpy.context.object
    obj.name = "Ground"

    prepped = _prep_footprints(footprints)
    wp, ws, wl = road_widths or (8.0, 4.5, 3.0)
    prepped_roads = _prep_roads(roads, wp, ws, wl)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    top_z = max(v.co.z for v in bm.verts)
    top_faces = [f for f in bm.faces if all(abs(v.co.z - top_z) < 1e-4 for v in f.verts)]
    if top_faces:
        # Cap starts as one n-gon. Poke + subdivide until top-edge spacing
        # is fine enough that the ~1.5 m soil-mound band actually contains
        # vertices (3 levels left ~3.3 m spacing -- mounds were invisible).
        target_spacing = 0.55
        rim_edge = (2.0 * math.pi * disk_r) / 48.0
        levels = max(3, int(math.ceil(math.log2(max(rim_edge / target_spacing, 1.0)))))
        # Cap runaway cost on huge radii (each level ~4x top faces).
        levels = min(levels, 7)
        bmesh.ops.poke(bm, faces=top_faces)
        top_faces = [f for f in bm.faces if all(abs(v.co.z - top_z) < 1e-4 for v in f.verts)]
        for _ in range(levels):
            top_edges = list({e for f in top_faces for e in f.edges})
            bmesh.ops.subdivide_edges(bm, edges=top_edges, cuts=1, use_grid_fill=True)
            top_faces = [f for f in bm.faces if all(abs(v.co.z - top_z) < 1e-4 for v in f.verts)]

    for v in bm.verts:
        if abs(v.co.z - top_z) < 1e-4:
            x, y = v.co.x, v.co.y
            clearance = _road_clearance(x, y, prepped_roads)
            dz = (_ground_noise(x, y, seed) + _soil_mound(x, y, prepped)) * clearance
            v.co.z += dz

    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.append(_diffuse_material("TownGround", (0.33, 0.40, 0.26), 0.95))
    bpy.ops.object.select_all(action="DESELECT")
    return obj


def setup_scene(radius):
    import bpy
    bpy.ops.object.light_add(
        type="SUN",
        location=(radius * 0.35, -radius * 0.55, radius * 0.9),
        rotation=(0.85, 0.18, 0.35),
    )
    sun = bpy.context.object
    sun.name = "Sun"
    sun.data.energy = 3.2
    if hasattr(sun.data, "angle"):
        sun.data.angle = 0.02
    bpy.ops.object.light_add(
        type="SUN",
        location=(-radius * 0.4, radius * 0.5, radius * 0.7),
        rotation=(0.55, -0.3, 2.4),
    )
    fill = bpy.context.object
    fill.name = "FillSun"
    fill.data.energy = 0.9
    from mathutils import Vector
    cam_loc = Vector((radius * 1.18, -radius * 1.41, radius * 0.91))
    bpy.ops.object.camera_add(location=tuple(cam_loc))
    cam = bpy.context.object
    cam.name = "CityCamera"
    cam.rotation_euler = (Vector((0.0, 0.0, 5.0)) - cam_loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = 0.5
    cam.data.clip_end = max(2000.0, radius * 8)
    cam.data.lens = 28
    bpy.context.scene.camera = cam
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.60, 0.66, 0.74, 1.0)
        bg.inputs[1].default_value = 0.75
    bpy.ops.object.select_all(action="DESELECT")


def _road_width_for_hierarchy(hierarchy, widthPrimary, widthSecondary, widthLocal):
    """
    Single source of truth for hierarchy -> road width, shared by
    build_roads (actual road mesh) and build_ground (so it can flatten a
    matching-width corridor into the terrain instead of guessing).
    """
    widths = {
        "primary": widthPrimary, "arterial": widthPrimary,
        "secondary": widthSecondary, "collector": widthSecondary,
        "local": widthLocal,
    }
    return widths.get(hierarchy, widthSecondary)


def build_roads(layout, widthPrimary, widthSecondary, widthLocal=3.0):
    """
    Builds one curve object per road hierarchy present in the layout, each
    with a Geometry Nodes modifier turning it into a flat ribbon mesh of
    the appropriate width.

    Supports both the default two-tier scheme (primary/secondary, from
    generate_city_layout's distance-based classification) and the
    three-tier functional scheme (arterial/collector/local, produced when
    the layout was generated with road_classification="functional" --
    see pro/city/layout.py's _classify_roads_functional). Any hierarchy
    value actually present in layout["roads"] that isn't in the style
    table below falls back to the "secondary"/"collector" styling rather
    than being silently dropped.
    """
    import bpy

    nodeGroup = _road_profile_node_group()
    widthSocketId = _width_socket_id(nodeGroup)
    matSocketId = _socket_id(nodeGroup, "Material")
    builtObjects = []

    styles = {
        "primary": dict(width=widthPrimary, color=(0.42, 0.39, 0.35), matName="CobblePrimary"),
        "arterial": dict(width=widthPrimary, color=(0.42, 0.39, 0.35), matName="CobblePrimary"),
        "secondary": dict(width=widthSecondary, color=(0.36, 0.31, 0.24), matName="PackedEarth"),
        "collector": dict(width=widthSecondary, color=(0.36, 0.31, 0.24), matName="PackedEarth"),
        "local": dict(width=widthLocal, color=(0.33, 0.29, 0.24), matName="LocalLane"),
    }
    fallback = dict(width=widthSecondary, color=(0.36, 0.31, 0.24), matName="PackedEarth")
    hierarchiesPresent = sorted({r["hierarchy"] for r in layout["roads"]})
    materials = {
        h: _diffuse_material(styles.get(h, fallback)["matName"], styles.get(h, fallback)["color"], 0.92)
        for h in hierarchiesPresent
    }

    for hierarchy in hierarchiesPresent:
        width = styles.get(hierarchy, fallback)["width"]
        segments = [r for r in layout["roads"] if r["hierarchy"] == hierarchy]
        if not segments:
            continue

        curveData = bpy.data.curves.new("Roads_%s" % hierarchy, type="CURVE")
        curveData.dimensions = "3D"
        for seg in segments:
            spline = curveData.splines.new("POLY")
            spline.points.add(1)  # POLY splines start with 1 point; add 1 more for 2 total
            (x1, y1), (x2, y2) = seg["start"], seg["end"]
            spline.points[0].co = (x1, y1, 0.02, 1)
            spline.points[1].co = (x2, y2, 0.02, 1)

        curveObj = bpy.data.objects.new("Roads_%s" % hierarchy, curveData)
        bpy.context.collection.objects.link(curveObj)
        mat = materials[hierarchy]
        if curveData.materials:
            curveData.materials[0] = mat
        else:
            curveData.materials.append(mat)
        mod = curveObj.modifiers.new("RoadProfile", "NODES")
        mod.node_group = nodeGroup
        mod[widthSocketId] = width
        mod[matSocketId] = mat
        builtObjects.append(curveObj)

    return builtObjects


def build_blocks(layout, ruleFile, maxBlocks=None, setback=3.0, session=None):
    import bpy
    from bpro.bl_util import create_footprint_from_points

    if session is None:
        raise ValueError("build_blocks requires a GenerationSession")

    blocks = layout["blocks"]
    if maxBlocks is not None:
        blocks = blocks[:maxBlocks]

    session.set_blender_context(bpy.context)
    built, failed = 0, 0

    for block in blocks:
        role = block.get("role")
        if role == "plaza":
            try:
                build_plaza(block)
                built += 1
            except Exception as e:
                print("WARNING: failed to generate plaza %d: %s" % (block["id"], e), file=sys.stderr)
                failed += 1
            continue

        session.set_city_block(block)
        polygon = _shrink_towards_centroid(
            block["polygon"], block["centroid"], _setback_for_role(role, setback)
        )
        create_footprint_from_points(bpy.context, polygon, offset=tuple(block["centroid"]))
        try:
            session.apply(ruleFile)
        except Exception as e:
            print("WARNING: failed to generate block %d: %s" % (block["id"], e), file=sys.stderr)
            failed += 1
            continue
        obj = bpy.context.object
        if obj is not None:
            prefix = {
                "church": "Church",
                "ratusz": "Ratusz",
                "synagogue": "Synagogue",
                "cottage": "Cottage",
                "kamienica": "Kamienica",
            }.get(role, "Block")
            obj.name = "%s_%03d" % (prefix, block["id"])
        built += 1
        bpy.ops.object.select_all(action="DESELECT")

    return built, failed


def build_plots(layout, ruleFile, maxPlots=None, session=None):
    import bpy
    from bpro.bl_util import create_footprint_from_points

    if session is None:
        raise ValueError("build_plots requires a GenerationSession")

    plots = list(layout.get("plots") or [])
    if maxPlots is not None:
        plots = plots[:maxPlots]

    session.set_blender_context(bpy.context)
    built, failed = 0, 0
    prefixes = {
        "church": "Church", "ratusz": "Ratusz", "synagogue": "Synagogue",
        "cottage": "Cottage", "kamienica": "Kamienica", "villa": "Villa",
        "workshop": "Workshop", "barn": "Barn",
        "karczma": "Karczma", "apteka": "Apteka", "school": "School",
    }

    for i, plot in enumerate(plots):
        session.set_city_block(plot)
        create_footprint_from_points(
            bpy.context, plot["polygon"], offset=tuple(plot["centroid"])
        )
        try:
            session.apply(ruleFile)
        except Exception as e:
            print("WARNING: failed to generate plot %d: %s" % (plot.get("id", i), e), file=sys.stderr)
            failed += 1
            bpy.ops.object.select_all(action="DESELECT")
            continue
        obj = bpy.context.object
        if obj is not None:
            obj.name = "%s_%03d" % (prefixes.get(plot.get("role"), "House"), plot.get("id", i))
        try:
            add_chimneys(plot)
        except Exception as e:
            print("WARNING: chimney failed on plot %d: %s" % (plot.get("id", i), e), file=sys.stderr)
        built += 1
        if built % 40 == 0:
            print("... %d houses" % built)
        bpy.ops.object.select_all(action="DESELECT")

    return built, failed


def _apply_modifiers_for_export():
    """Bake Geometry Nodes / modifiers so FBX gets real meshes (roads)."""
    import bpy
    for obj in list(bpy.data.objects):
        if not obj.modifiers:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.convert(target="MESH")
        except Exception:
            for mod in list(obj.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception:
                    pass
    bpy.ops.object.select_all(action="DESELECT")


def _player_start(layout):
    import math
    plaza = next((b for b in layout.get("blocks", []) if b.get("role") == "plaza"), None)
    if plaza and plaza.get("centroid"):
        cx, cy = float(plaza["centroid"][0]), float(plaza["centroid"][1])
    else:
        cx = cy = 0.0
    target = None
    best = 1e18
    for p in layout.get("plots") or []:
        if p.get("role") not in ("kamienica", "ratusz", "villa") and p.get("frontage") not in ("shop", "civic"):
            continue
        pc = p.get("centroid") or [0, 0]
        d = (pc[0] - cx) ** 2 + (pc[1] - cy) ** 2
        if d < best:
            best = d
            target = p
    yaw = 0.0
    if target and target.get("centroid"):
        yaw = math.atan2(target["centroid"][1] - cy, target["centroid"][0] - cx)
    return [round(cx, 4), round(cy, 4), 0.15, round(yaw, 6)]


def _buildings_meta(layout):
    out = []
    for p in layout.get("plots") or []:
        out.append({
            "name": "%s_%03d" % ((p.get("role") or "House").title(), p.get("id", 0)),
            "plot_id": p.get("id"),
            "storeys": p.get("storeys"),
            "role": p.get("role"),
        })
    return out


def _export(outputPath):
    import bpy
    ext = os.path.splitext(outputPath)[1].lower()
    outputPath = os.path.abspath(outputPath)
    os.makedirs(os.path.dirname(outputPath) or ".", exist_ok=True)
    if ext == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=outputPath)
    elif ext == ".obj":
        bpy.ops.wm.obj_export(filepath=outputPath, export_selected_objects=False)
    elif ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(filepath=outputPath)
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=outputPath)
    else:
        raise ValueError("Unsupported --output extension '%s'" % ext)


def main():
    args = parse_args()

    with open(args.layout) as f:
        layout = json.load(f)

    import bpy
    from pro.session import GenerationSession

    _clear_scene()

    ruleFile = os.path.abspath(args.rule)
    if not os.path.isfile(ruleFile):
        print("ERROR: rule file not found: %s" % ruleFile, file=sys.stderr)
        sys.exit(1)

    with GenerationSession(blender_context=bpy.context) as session:
        plaza_blocks = [b for b in layout.get("blocks", []) if b.get("role") == "plaza"]
        for plaza in plaza_blocks:
            try:
                build_plaza(plaza)
            except Exception as e:
                print("WARNING: plaza failed: %s" % e, file=sys.stderr)

        if layout.get("plots"):
            built, failed = build_plots(
                layout, ruleFile, maxPlots=args.max_blocks, session=session
            )
            print("Built %d house(s), %d failed" % (built, failed))
        else:
            built, failed = build_blocks(
                layout, ruleFile, maxBlocks=args.max_blocks, setback=args.setback,
                session=session,
            )
            print("Built %d block(s), %d failed" % (built, failed))

        if not args.skip_roads:
            roadObjects = build_roads(layout, args.road_width_primary, args.road_width_secondary, args.road_width_local)
            print("Built %d road curve object(s)" % len(roadObjects))

        if not args.skip_ground:
            radius = float(layout.get("radius") or 170.0)
            footprints = [
                b["polygon"] for b in (layout.get("plots") or layout.get("blocks") or [])
                if b.get("polygon")
            ]
            road_widths = (args.road_width_primary, args.road_width_secondary, args.road_width_local)
            build_ground(
                radius, footprints=footprints, roads=layout.get("roads"),
                road_widths=road_widths, seed=args.terrain_seed,
            )
            setup_scene(radius)
            print(
                "Added ground, sun, and terrain (soil-mounded around %d building(s), "
                "flattened under %d road segment(s))"
                % (len(footprints), len(layout.get("roads") or []))
            )

        if args.game_export:
            _apply_modifiers_for_export()
            print("Applied modifiers for game export")

        _export(args.output)

        base = os.path.splitext(os.path.abspath(args.output))[0]
        cityLights = list(session.all_ceiling_lights)
        doors = list(session.all_game_doors)

    lightsPath = None
    if cityLights:
        from pro.lights import lights_sidecar
        lightsPath = base + ".lights.json"
        with open(lightsPath, "w") as f:
            json.dump(lights_sidecar(cityLights), f, indent=2)
        print("Wrote %d ceiling light(s) to %s" % (len(cityLights), lightsPath))

    if args.game_export:
        from pro.doors import game_sidecar
        gamePath = base + ".game.json"
        with open(gamePath, "w") as f:
            json.dump(
                game_sidecar(
                    doors,
                    _buildings_meta(layout),
                    _player_start(layout),
                    lights_ref=os.path.basename(lightsPath) if lightsPath else None,
                ),
                f,
                indent=2,
            )
        print("Wrote %d door(s) + player_start to %s" % (len(doors), gamePath))
        # Always emit an FBX next to the chosen output for Unreal Interchange
        if not args.output.lower().endswith(".fbx"):
            fbxPath = base + ".fbx"
            _export(fbxPath)
            print("Wrote Unreal mesh FBX to %s" % fbxPath)

    print("Wrote city to %s" % args.output)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
