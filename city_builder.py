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

The rule file can read pro.context.cityBlock (set before each block is
generated) to vary height/style/color by that block's "density" (1.0 near
downtown, tapering to 0 at the city edge) -- see examples/city_building.py
for a worked example using choice()/chance()/switch() for this.
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
    parser.add_argument("--setback", type=float, default=3.0,
                        help="Shrink each building footprint toward its centroid (meters)")
    parser.add_argument("--skip-roads", action="store_true")
    parser.add_argument("--skip-ground", action="store_true")
    parser.add_argument("--max-blocks", type=int, default=None, help="Cap the number of blocks built (for quick previews)")
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
    elif role in ("church", "ratusz", "synagogue"):
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


def build_ground(radius):
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=radius * 1.25, depth=0.18, location=(0.0, 0.0, -0.14)
    )
    obj = bpy.context.object
    obj.name = "Ground"
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


def build_roads(layout, widthPrimary, widthSecondary):
    """
    Builds two curve objects (RoadsPrimary, RoadsSecondary), one spline per
    road segment of that hierarchy, each with a Geometry Nodes modifier
    turning it into a flat ribbon mesh of the appropriate width.
    """
    import bpy

    nodeGroup = _road_profile_node_group()
    widthSocketId = _width_socket_id(nodeGroup)
    matSocketId = _socket_id(nodeGroup, "Material")
    builtObjects = []
    materials = {
        "primary": _diffuse_material("CobblePrimary", (0.42, 0.39, 0.35), 0.92),
        "secondary": _diffuse_material("PackedEarth", (0.36, 0.31, 0.24), 0.95),
    }

    for hierarchy, width in (("primary", widthPrimary), ("secondary", widthSecondary)):
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


def build_blocks(layout, ruleFile, maxBlocks=None, setback=3.0):
    import bpy
    from pro import context as proContext
    import bpro
    from bpro.bl_util import create_footprint_from_points

    blocks = layout["blocks"]
    if maxBlocks is not None:
        blocks = blocks[:maxBlocks]

    proContext.blenderContext = bpy.context
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

        proContext.cityBlock = block
        polygon = _shrink_towards_centroid(
            block["polygon"], block["centroid"], _setback_for_role(role, setback)
        )
        create_footprint_from_points(bpy.context, polygon, offset=tuple(block["centroid"]))
        try:
            bpro.apply(ruleFile)
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


def build_plots(layout, ruleFile, maxPlots=None):
    import bpy
    from pro import context as proContext
    import bpro
    from bpro.bl_util import create_footprint_from_points

    plots = list(layout.get("plots") or [])
    if maxPlots is not None:
        plots = plots[:maxPlots]

    proContext.blenderContext = bpy.context
    built, failed = 0, 0
    prefixes = {
        "church": "Church", "ratusz": "Ratusz", "synagogue": "Synagogue",
        "cottage": "Cottage", "kamienica": "Kamienica", "villa": "Villa",
        "workshop": "Workshop", "barn": "Barn",
    }

    for i, plot in enumerate(plots):
        proContext.cityBlock = plot
        create_footprint_from_points(
            bpy.context, plot["polygon"], offset=tuple(plot["centroid"])
        )
        try:
            bpro.apply(ruleFile)
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
    _clear_scene()

    ruleFile = os.path.abspath(args.rule)
    if not os.path.isfile(ruleFile):
        print("ERROR: rule file not found: %s" % ruleFile, file=sys.stderr)
        sys.exit(1)

    plaza_blocks = [b for b in layout.get("blocks", []) if b.get("role") == "plaza"]
    for plaza in plaza_blocks:
        try:
            build_plaza(plaza)
        except Exception as e:
            print("WARNING: plaza failed: %s" % e, file=sys.stderr)

    if layout.get("plots"):
        built, failed = build_plots(layout, ruleFile, maxPlots=args.max_blocks)
        print("Built %d house(s), %d failed" % (built, failed))
    else:
        built, failed = build_blocks(
            layout, ruleFile, maxBlocks=args.max_blocks, setback=args.setback
        )
        print("Built %d block(s), %d failed" % (built, failed))

    if not args.skip_roads:
        roadObjects = build_roads(layout, args.road_width_primary, args.road_width_secondary)
        print("Built %d road curve object(s)" % len(roadObjects))

    if not args.skip_ground:
        radius = float(layout.get("radius") or 170.0)
        build_ground(radius)
        setup_scene(radius)
        print("Added ground, sun, and camera")

    _export(args.output)
    print("Wrote city to %s" % args.output)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
