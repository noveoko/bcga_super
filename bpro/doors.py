"""Spawn Blender door-leaf meshes from door records."""
import math

import bpy
import mathutils


def _door_mesh(name, width, height, thickness):
    mesh = bpy.data.meshes.new(name)
    w, h, t = float(width), float(height), float(thickness)
    # hinge at origin; leaf in +X (along wall), thin in +Y (swing), +Z up
    verts = [
        (0, -t / 2, 0), (w, -t / 2, 0), (w, t / 2, 0), (0, t / 2, 0),
        (0, -t / 2, h), (w, -t / 2, h), (w, t / 2, h), (0, t / 2, h),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def spawn_door_leaves(records, parent=None):
    if not records:
        return []
    col = bpy.data.collections.get("Doors")
    if col is None:
        col = bpy.data.collections.new("Doors")
        bpy.context.scene.collection.children.link(col)
    spawned = []
    for i, rec in enumerate(records):
        plot = rec.get("plot_id")
        name = rec.get("name") or "Door_%s_%d" % (plot if plot is not None else 0, i)
        rec = dict(rec)
        rec["name"] = name
        mesh = _door_mesh(name, rec["width"], rec["height"], rec.get("thickness", 0.04))
        obj = bpy.data.objects.new(name, mesh)
        x, y, z = rec["location"]
        obj.location = (x, y, z)
        edge = rec.get("edge") or (1.0, 0.0, 0.0)
        yaw = rec.get("yaw")
        if yaw is None:
            yaw = math.atan2(edge[1], edge[0])
        obj.rotation_euler = (0.0, 0.0, float(yaw))
        col.objects.link(obj)
        if parent is not None:
            obj.parent = parent
            obj.matrix_parent_inverse = parent.matrix_world.inverted()
        spawned.append(rec)
    return spawned
