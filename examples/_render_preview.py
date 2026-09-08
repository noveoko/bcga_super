"""One-shot preview render for a generated .blend. Usage:
blender --background file.blend --python examples/_render_preview.py -- --output out/preview.png
"""
import math
import os
import sys

import bpy
from mathutils import Vector


def _argv():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def _parse():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--height", type=int, default=900)
    return p.parse_args(_argv())


def main():
    args = _parse()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh to render")
    # bbox of all meshes
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            mins.x, mins.y, mins.z = min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)
            maxs.x, maxs.y, maxs.z = max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)
    center = (mins + maxs) / 2.0
    size = maxs - mins
    # postcard view: look at the front (-Y), slightly from the right and above
    dist = max(size.x, size.y, size.z) * 1.7
    cam_loc = Vector((center.x + dist * 0.35, center.y - dist * 1.15, center.z + dist * 0.28))
    bpy.ops.object.camera_add(location=tuple(cam_loc))
    cam = bpy.context.object
    cam.rotation_euler = (center - cam_loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    cam.data.clip_end = 500
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(center.x + 8, center.y - 12, center.z + 18))
    sun = bpy.context.object
    sun.data.energy = 4.0
    sun.rotation_euler = (0.7, 0.15, 0.4)
    bpy.ops.object.light_add(type="SUN", location=(center.x - 10, center.y + 6, center.z + 10))
    fill = bpy.context.object
    fill.data.energy = 1.1

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.62, 0.68, 0.74, 1.0)
        bg.inputs[1].default_value = 0.85

    scene = bpy.context.scene
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    if "BLENDER_EEVEE_NEXT" in engines:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in engines:
        scene.render.engine = "BLENDER_EEVEE"
    else:
        scene.render.engine = "CYCLES"
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.filepath = os.path.abspath(args.output)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("Wrote preview", scene.render.filepath)


if __name__ == "__main__":
    main()
