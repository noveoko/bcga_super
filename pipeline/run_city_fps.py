"""
Orchestrate: Polish-town layout → Blender game export → (optional) Unreal import.

    python pipeline/run_city.py --seed 1927 --output out/playable

Requires: numpy, scipy, blender on PATH.
Unreal import only runs when --ue-project is set and UnrealEditor-Cmd is available.

Default playable character is Unreal Third Person. Pass --view first-person
for a First Person template project.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _log(path, msg):
    print(msg)
    with open(path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _run(cmd, log_path, env=None):
    _log(log_path, "$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=_repo_root(), env=env, capture_output=True, text=True)
    if proc.stdout:
        _log(log_path, proc.stdout.rstrip())
    if proc.stderr:
        _log(log_path, proc.stderr.rstrip())
    if proc.returncode != 0:
        raise SystemExit("Command failed (%d): %s" % (proc.returncode, " ".join(cmd)))


def _resolve_blender(blender):
    if blender and os.path.isfile(blender):
        return blender
    found = shutil.which(blender or "blender")
    if not found:
        raise SystemExit(
            "blender not found (%r). Pass --blender path\\to\\blender.exe or put it on PATH."
            % (blender,)
        )
    return found


def _resolve_unreal(unreal_cmd):
    if unreal_cmd and os.path.isfile(unreal_cmd):
        return unreal_cmd
    env = os.environ.get("UNREAL_EDITOR_CMD")
    if env and os.path.isfile(env):
        return env
    found = shutil.which(unreal_cmd or "UnrealEditor-Cmd")
    if not found:
        raise SystemExit(
            "UnrealEditor-Cmd not found. Pass --unreal-cmd "
            r'"C:\Program Files\Epic Games\UE_5.x\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"'
        )
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Build a playable Unreal city from BCGA (third-person by default)"
    )
    parser.add_argument("--seed", type=int, default=1927)
    parser.add_argument(
        "--max-plots", type=int, default=None,
        help="Cap plots built (preview). Default: every plot in the layout.",
    )
    parser.add_argument("--output", default="out/playable", help="Output directory")
    parser.add_argument("--rule", default="examples/polish_town_1927.py")
    parser.add_argument("--radius", type=float, default=160.0)
    parser.add_argument("--blocks", type=int, default=48)
    parser.add_argument("--ue-project", default=None, help="Path to a .uproject to auto-import")
    parser.add_argument("--unreal-cmd", default=None, help="UnrealEditor-Cmd.exe path")
    parser.add_argument("--blender", default="blender")
    parser.add_argument(
        "--view", choices=("third-person", "first-person"), default="third-person",
        help="Unreal character: third-person (default) or first-person. "
             "The .uproject must be created from that UE5 template so the GameMode exists.",
    )
    parser.add_argument("--flip-y", action="store_true",
                         help="Apply (X,-Y,Z) Blender→UE flip when placing doors/lights/player start "
                              "(see docs/PLAYABLE_CITY.md — pass this if the imported town looks mirrored)")
    parser.add_argument("--scale", type=float, default=100.0, help="meters → centimeters, forwarded to Unreal import")
    args = parser.parse_args()

    root = _repo_root()
    out_dir = os.path.join(root, args.output)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "pipeline.log")
    open(log_path, "w").close()

    blender = _resolve_blender(args.blender)

    layout_path = os.path.join(out_dir, "layout.json")
    blend_path = os.path.join(out_dir, "city.blend")
    rule_path = os.path.join(root, args.rule)
    if not os.path.isfile(rule_path):
        raise SystemExit("rule file not found: %s" % rule_path)

    _log(log_path, "=== Stage 1: layout ===")
    _run([
        sys.executable, os.path.join(root, "pro", "city", "layout.py"),
        "--style", "polish",
        "--output", layout_path,
        "--seed", str(args.seed),
        "--radius", str(args.radius),
        "--blocks", str(args.blocks),
    ], log_path)

    _log(log_path, "=== Stage 2: Blender game export ===")
    blender_cmd = [
        blender, "--background", "--factory-startup",
        "--python", os.path.join(root, "city_builder.py"),
        "--",
        "--layout", layout_path,
        "--rule", rule_path,
        "--output", blend_path,
        "--seed", str(args.seed),
        "--game-export",
    ]
    if args.max_plots is not None:
        blender_cmd.extend(["--max-blocks", str(args.max_plots)])
    _run(blender_cmd, log_path)

    game_json = os.path.splitext(blend_path)[0] + ".game.json"
    lights_json = os.path.splitext(blend_path)[0] + ".lights.json"
    fbx_path = os.path.splitext(blend_path)[0] + ".fbx"
    _log(log_path, "Artifacts:")
    missing = []
    for p in (layout_path, blend_path, fbx_path, game_json):
        ok = os.path.isfile(p)
        _log(log_path, "  %s %s" % ("OK" if ok else "MISSING", p))
        if not ok:
            missing.append(p)
    lights_ok = os.path.isfile(lights_json)
    _log(log_path, "  %s %s" % ("OK" if lights_ok else "MISSING", lights_json))
    if missing:
        raise SystemExit("Blender game export did not write: %s" % ", ".join(missing))

    if not args.ue_project:
        _log(log_path, "")
        _log(log_path, "Blender game export done. Next (one-time UE setup):")
        _log(log_path, "  1. Create a UE5 Third Person project (or First Person, then --view first-person)")
        _log(log_path, "  2. Enable Editor Scripting + Python Editor Script Plugin")
        _log(log_path, "  3. Create BP_CityDoor at /Game/City/BP_CityDoor (see docs/PLAYABLE_CITY.md)")
        _log(log_path, "  4. Re-run with --ue-project path\\to\\CityGame.uproject")
        _log(log_path, "     Default view is third-person; pass --view first-person for FPS.")
        return

    if not os.path.isfile(args.ue_project):
        raise SystemExit("ue-project not found: %s" % args.ue_project)

    _log(log_path, "=== Stage 3: Unreal import (%s) ===" % args.view)
    unreal = _resolve_unreal(args.unreal_cmd)
    # Forward slashes: Unreal's -ExecutePythonScript= treats `\u` in a
    # Windows `...\ue\import_city.py` path as a Unicode escape and looks
    # for a garbled filename (LogPython: Could not load Python file).
    import_script = os.path.join(root, "ue", "import_city.py").replace("\\", "/")
    import_args = [
        unreal, args.ue_project, "-unattended",
        "-ExecutePythonScript=%s" % import_script,
        "--",
        "--fbx", fbx_path,
        "--game-json", game_json,
        "--scale", str(args.scale),
        "--view", args.view,
    ]
    if lights_ok:
        import_args.extend(["--lights-json", lights_json])
    if args.flip_y:
        import_args.append("--flip-y")
    _run(import_args, log_path)
    _log(log_path, "Unreal import finished. Open /Game/City/Lvl_City and PIE (%s)." % args.view)
    if not args.flip_y:
        _log(log_path, "If the town looks mirrored in PIE, re-run this command with --flip-y.")


if __name__ == "__main__":
    main()
