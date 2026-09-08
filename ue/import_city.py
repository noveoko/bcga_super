"""
Unreal Editor Python: import a BCGA game-export city into the open project.

Run from UnrealEditor-Cmd:

  UnrealEditor-Cmd.exe CityFPS.uproject -unattended ^
    -ExecutePythonScript=".../ue/import_city.py" -- ^
    --fbx out/playable/city.fbx --game-json out/playable/city.game.json ^
    --lights-json out/playable/city.lights.json

Requires (one-time in the First Person project):
  - Editor Scripting Utilities
  - Python Editor Script Plugin
  - Blueprint /Game/City/BP_CityDoor with a StaticMesh component and a
    custom event OpenClose that swings yaw by SwingDegrees around local Z
    (see docs/PLAYABLE_CITY.md). If BP_CityDoor is missing, doors are
    spawned as plain StaticMeshActors (no interact).
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _parse():
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--game-json", required=True)
    p.add_argument("--lights-json", default=None)
    p.add_argument("--scale", type=float, default=100.0, help="meters → centimeters")
    p.add_argument("--flip-y", action="store_true", help="Apply (X,-Y,Z) Blender→UE flip")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def _to_ue(loc, scale, flip_y):
    x, y, z = loc[0], loc[1], loc[2]
    if flip_y:
        y = -y
    return (x * scale, y * scale, z * scale)


def main():
    args = _parse()
    with open(args.game_json, encoding="utf-8") as f:
        game = json.load(f)
    lights = {"lights": []}
    if args.lights_json and os.path.isfile(args.lights_json):
        with open(args.lights_json, encoding="utf-8") as f:
            lights = json.load(f)

    if args.dry_run:
        print("dry-run fbx=", args.fbx)
        print("doors=", len(game.get("doors") or []))
        print("lights=", len(lights.get("lights") or []))
        print("player_start=", game.get("player_start"))
        return

    import unreal

    fbx = os.path.abspath(args.fbx)
    dest = "/Game/City/Meshes"
    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = dest
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    print("Imported", fbx, "→", dest)

    # Point lights
    for rec in lights.get("lights") or []:
        loc = _to_ue(rec["location"], args.scale, args.flip_y)
        light = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.PointLight.static_class(), unreal.Vector(*loc)
        )
        if light:
            light.set_actor_label(rec.get("name") or "CeilingLight")
            comp = light.point_light_component
            if comp:
                color = rec.get("color") or [1, 1, 1]
                comp.set_editor_property("intensity", float(rec.get("intensity") or 600))
                comp.set_editor_property(
                    "light_color",
                    unreal.LinearColor(color[0], color[1], color[2], 1.0),
                )
                if hasattr(comp, "set_attenuation_radius"):
                    comp.set_attenuation_radius(float(rec.get("radius") or 7.0) * args.scale)

    # Player start
    ps = game.get("player_start") or [0, 0, 0.15, 0]
    ps_loc = _to_ue(ps[:3], args.scale, args.flip_y)
    yaw = float(ps[3] if len(ps) > 3 else 0.0) * (180.0 / 3.14159265)
    if args.flip_y:
        yaw = -yaw
    start = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.PlayerStart.static_class(), unreal.Vector(*ps_loc)
    )
    if start:
        start.set_actor_rotation(unreal.Rotator(0.0, yaw, 0.0), False)
        start.set_actor_label("BCGA_PlayerStart")

    # Doors — prefer BP_CityDoor, else static mesh actor at hinge
    door_bp = unreal.load_asset("/Game/City/BP_CityDoor")
    for rec in game.get("doors") or []:
        loc = _to_ue(rec["location"], args.scale, args.flip_y)
        yaw = float(rec.get("yaw") or 0.0) * (180.0 / 3.14159265)
        if args.flip_y:
            yaw = -yaw
        rot = unreal.Rotator(0.0, yaw, 0.0)
        if door_bp:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
                door_bp, unreal.Vector(*loc), rot
            )
        else:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.StaticMeshActor.static_class(), unreal.Vector(*loc), rot
            )
        if actor:
            actor.set_actor_label(rec.get("name") or "Door")

    unreal.EditorLevelLibrary.save_current_level()
    print("City import complete. PIE from the First Person map.")


if __name__ == "__main__":
    main()
