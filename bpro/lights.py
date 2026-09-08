"""Spawn Blender POINT lamps + empties from ceiling-light records."""
import bpy

from pro.lights import lights_sidecar


def spawn_ceiling_lights(records, parent=None):
    """
    Create a POINT lamp (lookdev) and an Empty named LIGHT_* (survives FBX)
    for each record. Returns the sidecar document (names filled in).
    """
    sidecar = lights_sidecar(records)
    if not sidecar["lights"]:
        return sidecar
    col = bpy.data.collections.get("Lights")
    if col is None:
        col = bpy.data.collections.new("Lights")
        bpy.context.scene.collection.children.link(col)
    for rec in sidecar["lights"]:
        x, y, z = rec["location"]
        name = rec["name"]
        lamp_data = bpy.data.lights.new(name=name, type="POINT")
        lamp_data.energy = 50.0
        lamp_data.color = tuple(rec["color"])
        if hasattr(lamp_data, "shadow_soft_size"):
            lamp_data.shadow_soft_size = 0.15
        lamp = bpy.data.objects.new(name, lamp_data)
        lamp.location = (x, y, z)
        empty = bpy.data.objects.new(name + "_LOC", None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.12
        empty.location = (x, y, z)
        for obj in (lamp, empty):
            col.objects.link(obj)
            if parent is not None:
                obj.parent = parent
                obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return sidecar
