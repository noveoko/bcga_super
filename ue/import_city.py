"""
Unreal Editor Python: import a BCGA game-export city into the open project.

Run from UnrealEditor-Cmd:

  UnrealEditor-Cmd.exe CityGame.uproject -unattended ^
    -ExecutePythonScript=".../ue/import_city.py" -- ^
    --fbx out/playable/city.fbx --game-json out/playable/city.game.json ^
    --lights-json out/playable/city.lights.json --view third-person

Requires (one-time in the Unreal project):
  - Editor Scripting Utilities
  - Python Editor Script Plugin
  - A Third Person *or* First Person template (see --view; default is
    third-person). The importer sets World Settings GameMode when it can
    find a matching Blueprint.
  - Blueprint /Game/City/BP_CityDoor (also accepts /Game/BP_CityDoor) with
    a StaticMesh component and interact that swings yaw by SwingDegrees
    around local Z. If missing, doors spawn as StaticMeshActors (no interact).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys


VIEW_THIRD_PERSON = "third-person"
VIEW_FIRST_PERSON = "first-person"
DEFAULT_VIEW = VIEW_THIRD_PERSON

# Typical UE5 template GameMode Blueprint paths (without _C suffix).
GAME_MODE_CANDIDATES = {
    VIEW_THIRD_PERSON: (
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode",
        "/Game/ThirdPersonBP/Blueprints/BP_ThirdPersonGameMode",
        "/Game/TP/Blueprints/BP_ThirdPersonGameMode",
    ),
    VIEW_FIRST_PERSON: (
        "/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode",
        "/Game/FirstPersonBP/Blueprints/BP_FirstPersonGameMode",
        "/Game/FP/Blueprints/BP_FirstPersonGameMode",
    ),
}

DOOR_BLUEPRINT_CANDIDATES = (
    "/Game/City/BP_CityDoor",
    "/Game/BP_CityDoor",
)

CITY_LEVEL_PATH = "/Game/City/Lvl_City"
CITY_MESH_DEST = "/Game/City/Meshes"

# Meshes we spawn as world geometry. Door leaves are spawned as actors from
# game.json instead (so they can swing); cameras/lights are JSON or unused.
_SKIP_MESH_PREFIXES = (
    "door_",
    "door",
    "camera",
    "sun",
    "light",
    "lamp",
    "playerstart",
    "player_start",
)


def _tokenize_command_line(cmdline):
    """Split a Windows/Unreal command line, stripping quotes."""
    if not cmdline:
        return []
    tokens = shlex.split(cmdline, posix=False)
    return [t.strip().strip('"') for t in tokens if t.strip()]


def import_argv(argv=None, cmdline=None):
    """
    Args for this script. Unreal's -ExecutePythonScript does not put the
    tokens after `--` into sys.argv; they only exist on the editor command
    line (unreal.SystemLibrary.get_command_line()).
    """
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if any(a == "--fbx" or a.startswith("--fbx=") for a in argv):
        return argv
    if cmdline is None:
        try:
            import unreal
            cmdline = unreal.SystemLibrary.get_command_line()
        except Exception:
            cmdline = ""
    tokens = _tokenize_command_line(cmdline)
    if "--" in tokens:
        tokens = tokens[tokens.index("--") + 1:]
    return tokens


def _parse(argv=None, cmdline=None):
    argv = import_argv(argv, cmdline=cmdline)
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--game-json", required=True)
    p.add_argument("--lights-json", default=None)
    p.add_argument("--scale", type=float, default=100.0, help="meters → centimeters")
    p.add_argument("--flip-y", action="store_true", help="Apply (X,-Y,Z) Blender→UE flip")
    p.add_argument(
        "--view",
        choices=(VIEW_THIRD_PERSON, VIEW_FIRST_PERSON),
        default=DEFAULT_VIEW,
        help="Possess a Third Person (default) or First Person GameMode if the "
             "template Blueprint exists in this project.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--level", default=CITY_LEVEL_PATH,
                   help="Content path for the city map (created/overwritten).")
    return p.parse_args(argv)


def _to_ue(loc, scale, flip_y):
    x, y, z = loc[0], loc[1], loc[2]
    if flip_y:
        y = -y
    return (x * scale, y * scale, z * scale)


def mesh_short_name(asset_path):
    """'/Game/City/Meshes/Kamienica_012.Kamienica_012' → 'Kamienica_012'."""
    return asset_path.rsplit(".", 1)[-1].rsplit("/", 1)[-1]


def is_world_mesh_name(name):
    """True if this imported static mesh should be spawned as scenery."""
    n = (name or "").strip()
    if not n:
        return False
    lower = n.lower()
    for prefix in _SKIP_MESH_PREFIXES:
        if lower.startswith(prefix):
            return False
    return True


def door_blueprint_candidates():
    return DOOR_BLUEPRINT_CANDIDATES


def game_mode_candidates(view):
    return GAME_MODE_CANDIDATES.get(view) or ()


def main(argv=None):
    args = _parse(argv)
    with open(args.game_json, encoding="utf-8") as f:
        game = json.load(f)
    lights = {"lights": []}
    if args.lights_json and os.path.isfile(args.lights_json):
        with open(args.lights_json, encoding="utf-8") as f:
            lights = json.load(f)

    if args.dry_run:
        print("dry-run fbx=", args.fbx)
        print("view=", args.view)
        print("doors=", len(game.get("doors") or []))
        print("lights=", len(lights.get("lights") or []))
        print("player_start=", game.get("player_start"))
        print("game_mode_candidates=", list(game_mode_candidates(args.view)))
        return

    import unreal

    fbx = os.path.abspath(args.fbx)
    dest = CITY_MESH_DEST
    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = dest
    task.automated = True
    task.save = True
    task.replace_existing = True
    try:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("import_animations", False)
        sm = options.get_editor_property("static_mesh_import_data")
        if sm:
            sm.set_editor_property("combine_meshes", False)
            sm.set_editor_property("auto_generate_collision", False)
            # Vertices stay in meters; actor scale below applies --scale.
            if hasattr(sm, "set_editor_property"):
                try:
                    sm.set_editor_property("import_uniform_scale", 1.0)
                except Exception:
                    pass
        task.options = options
    except Exception as e:
        print("WARNING: could not configure FbxImportUI (%s); using importer defaults" % e)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported_paths = list(task.get_editor_property("imported_object_paths") or [])
    print("Imported", fbx, "→", dest, "(%d assets)" % len(imported_paths))

    mesh_by_name = {}
    world_meshes = []
    for path in imported_paths:
        short_name = mesh_short_name(path)
        mesh_by_name[short_name] = path
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.StaticMesh) and is_world_mesh_name(short_name):
            world_meshes.append(asset)

    def _find_door_mesh(door_name):
        path = mesh_by_name.get(door_name)
        if not path:
            return None
        asset = unreal.load_asset(path)
        return asset if isinstance(asset, unreal.StaticMesh) else None

    # Empty city map so we do not dump actors onto the template playground.
    try:
        unreal.EditorLevelLibrary.new_level(args.level)
        print("Created level", args.level)
    except Exception as e:
        print("WARNING: could not create %s (%s); spawning into the current map" % (args.level, e))

    spawned_world = 0
    mesh_extent = _max_mesh_extent(world_meshes)
    mesh_scale = actor_scale_from_mesh_extent(mesh_extent, args.scale)
    print("Mesh extent=%.1f, actor scale=%.3f (sidecar locations still ×%.0f)" % (
        mesh_extent, mesh_scale, args.scale,
    ))
    actor_scale = unreal.Vector(mesh_scale, mesh_scale, mesh_scale)
    for mesh in world_meshes:
        _set_complex_as_simple(mesh)
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor.static_class(), unreal.Vector(0.0, 0.0, 0.0)
        )
        if not actor:
            continue
        actor.set_actor_label(mesh.get_name())
        actor.set_actor_scale3d(actor_scale)
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        if comp:
            comp.set_static_mesh(mesh)
            try:
                comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
                comp.set_editor_property("collision_profile_name", "BlockAll")
            except Exception:
                pass
        spawned_world += 1
    print("Spawned %d world mesh actor(s) (buildings/roads/ground)" % spawned_world)

    _spawn_daylight()

    # Point lights
    for rec in lights.get("lights") or []:
        loc = _to_ue(rec["location"], args.scale, args.flip_y)
        try:
            light = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.PointLight.static_class(), unreal.Vector(*loc)
            )
        except Exception as e:
            print("WARNING: could not spawn light:", e)
            continue
        if light:
            light.set_actor_label(rec.get("name") or "CeilingLight")
            comp = light.point_light_component
            if comp:
                color = rec.get("color") or [1, 1, 1]
                try:
                    comp.set_editor_property("intensity", float(rec.get("intensity") or 600))
                except Exception:
                    pass
                _set_point_light_color(comp, color)
                try:
                    if hasattr(comp, "set_attenuation_radius"):
                        comp.set_attenuation_radius(float(rec.get("radius") or 7.0) * args.scale)
                except Exception:
                    pass

    # Player start — JSON z is often 0.15 m (15 UU after ×100), which puts the
    # first-person camera inside the ground mesh (black screen in PIE).
    ps = game.get("player_start") or [0, 0, 1.8, 0]
    ps_loc = list(_to_ue(ps[:3], args.scale, args.flip_y))
    ps_loc[2] = max(ps_loc[2], 180.0)
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
    door_bp = None
    for bp_path in door_blueprint_candidates():
        door_bp = unreal.load_asset(bp_path)
        if door_bp:
            print("Using door Blueprint", bp_path)
            break
    if not door_bp:
        print(
            "WARNING: no BP_CityDoor at %s — doors will not be interactable"
            % ", ".join(door_blueprint_candidates())
        )

    missing_mesh = []
    for rec in game.get("doors") or []:
        loc = _to_ue(rec["location"], args.scale, args.flip_y)
        yaw = float(rec.get("yaw") or 0.0) * (180.0 / 3.14159265)
        if args.flip_y:
            yaw = -yaw
        rot = unreal.Rotator(0.0, yaw, 0.0)
        name = rec.get("name") or "Door"
        if door_bp:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
                door_bp, unreal.Vector(*loc), rot
            )
        else:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.StaticMeshActor.static_class(), unreal.Vector(*loc), rot
            )
        if actor:
            actor.set_actor_label(name)
            door_mesh = _find_door_mesh(name)
            if door_mesh:
                _set_complex_as_simple(door_mesh)
                comp = actor.get_component_by_class(unreal.StaticMeshComponent)
                if comp:
                    comp.set_static_mesh(door_mesh)
                else:
                    missing_mesh.append(name + " (no StaticMeshComponent found)")
            else:
                missing_mesh.append(name)
    if missing_mesh:
        print("WARNING: could not assign door mesh for %d door(s): %s" % (
            len(missing_mesh), ", ".join(missing_mesh[:10]) + (" ..." if len(missing_mesh) > 10 else "")
        ))

    gm_path = _apply_view_mode(unreal, args.view)
    if gm_path:
        print("Set GameMode from", gm_path, "(%s)" % args.view)
    else:
        print(
            "WARNING: no %s GameMode Blueprint found. Looked at: %s. "
            "Create a UE5 %s template project, or pass --view %s."
            % (
                args.view,
                ", ".join(game_mode_candidates(args.view)),
                "Third Person" if args.view == VIEW_THIRD_PERSON else "First Person",
                VIEW_FIRST_PERSON if args.view == VIEW_THIRD_PERSON else VIEW_THIRD_PERSON,
            )
        )

    try:
        unreal.EditorLevelLibrary.save_current_level()
    except Exception as e:
        print("WARNING: save_current_level failed:", e)
    print("City import complete. Open %s and PIE (%s)." % (args.level, args.view))


def actor_scale_from_mesh_extent(max_extent, location_scale=100.0):
    """
    Blender FBX often already stores centimeters. Scaling those actors by
    100 again makes a 160 m town 16 km across and leaves the pawn inside
    a giant ground mesh (PIE = black). If the largest mesh is already
    bigger than ~5 m in UU, treat it as centimeters and spawn at scale 1.
    """
    if max_extent >= 500.0:
        return 1.0
    return float(location_scale)


def _max_mesh_extent(meshes):
    best = 0.0
    for mesh in meshes:
        try:
            bounds = mesh.get_bounds()
            ext = bounds.box_extent
            size = max(abs(ext.x), abs(ext.y), abs(ext.z)) * 2.0
            if size > best:
                best = size
        except Exception:
            try:
                box = mesh.get_bounding_box()
                size = max(
                    abs(box.max.x - box.min.x),
                    abs(box.max.y - box.min.y),
                    abs(box.max.z - box.min.z),
                )
                if size > best:
                    best = size
            except Exception:
                pass
    return best


def _spawn_daylight():
    """new_level() is an empty map: no sun/sky → Lumen PIE is a black void."""
    import unreal
    sun = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.DirectionalLight.static_class(), unreal.Vector(0.0, 0.0, 5000.0)
    )
    if sun:
        sun.set_actor_label("BCGA_Sun")
        sun.set_actor_rotation(unreal.Rotator(-40.0, 35.0, 0.0), False)
        try:
            comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
            if comp:
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_editor_property("intensity", 10.0)
                try:
                    comp.set_editor_property("atmosphere_sunlight", True)
                except Exception:
                    pass
        except Exception as e:
            print("WARNING: could not configure DirectionalLight:", e)

    atmo = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkyAtmosphere.static_class(), unreal.Vector(0.0, 0.0, 0.0)
    )
    if atmo:
        atmo.set_actor_label("BCGA_SkyAtmosphere")

    sky = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkyLight.static_class(), unreal.Vector(0.0, 0.0, 2000.0)
    )
    if sky:
        sky.set_actor_label("BCGA_SkyLight")
        try:
            comp = sky.get_component_by_class(unreal.SkyLightComponent)
            if comp:
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_editor_property("real_time_capture", True)
                comp.set_editor_property("intensity", 1.0)
        except Exception as e:
            print("WARNING: could not configure SkyLight:", e)

    try:
        fog = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.ExponentialHeightFog.static_class(), unreal.Vector(0.0, 0.0, 0.0)
        )
        if fog:
            fog.set_actor_label("BCGA_Fog")
    except Exception:
        pass
    print("Spawned sun / sky atmosphere / skylight")


def _set_point_light_color(comp, color):
    """UE5 LightColor is a Color (0–255), not LinearColor."""
    import unreal
    r, g, b = float(color[0]), float(color[1]), float(color[2])
    if max(r, g, b) <= 1.0:
        ri, gi, bi = int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
    else:
        ri, gi, bi = int(round(r)), int(round(g)), int(round(b))
    try:
        comp.set_editor_property("light_color", unreal.Color(ri, gi, bi, 255))
        return
    except Exception:
        pass
    try:
        if hasattr(comp, "set_light_color"):
            comp.set_light_color(unreal.LinearColor(r if r <= 1 else r / 255.0,
                                                    g if g <= 1 else g / 255.0,
                                                    b if b <= 1 else b / 255.0, 1.0))
    except Exception as e:
        print("WARNING: could not set light color:", e)


def _set_complex_as_simple(mesh):
    """Hollow houses need per-triangle collision, not a convex hull."""
    try:
        import unreal
        body = mesh.get_editor_property("body_setup")
        if body is None:
            return
        body.set_editor_property(
            "collision_trace_flag",
            unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE,
        )
    except Exception as e:
        print("WARNING: could not set complex-as-simple on", getattr(mesh, "get_name", lambda: mesh)(), e)


def _apply_view_mode(unreal, view):
    for path in game_mode_candidates(view):
        exists = False
        try:
            exists = unreal.EditorAssetLibrary.does_asset_exist(path)
        except Exception:
            exists = bool(unreal.load_asset(path))
        if not exists:
            continue
        cls = None
        try:
            cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
        except Exception:
            cls = unreal.load_asset(path)
        if cls is None:
            continue
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
            settings = world.get_world_settings()
            settings.set_editor_property("default_game_mode", cls)
            return path
        except Exception as e:
            print("WARNING: found %s but could not set World Settings GameMode: %s" % (path, e))
            return path
    return None


if __name__ == "__main__":
    main()
