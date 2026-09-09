"""
Orchestrate: Polish-town layout → Blender game export → (optional) Unreal import.

    python pipeline/run_city_fps.py --seed 1927 --max-plots 40 --output out/playable

Requires: numpy, scipy, blender on PATH.
Unreal import only runs when --ue-project is set and UnrealEditor-Cmd is available.
"""
from __future__ import annotations

import argparse
import os
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


def main():
    parser = argparse.ArgumentParser(description="Build a playable Unreal FPS city from BCGA")
    parser.add_argument("--seed", type=int, default=1927)
    parser.add_argument("--max-plots", type=int, default=40)
    parser.add_argument("--output", default="out/playable", help="Output directory")
    parser.add_argument("--rule", default="examples/polish_town_1927.py")
    parser.add_argument("--radius", type=float, default=160.0)
    parser.add_argument("--blocks", type=int, default=48)
    parser.add_argument("--ue-project", default=None, help="Path to CityFPS.uproject to auto-import")
    parser.add_argument("--unreal-cmd", default=None, help="UnrealEditor-Cmd.exe path")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--flip-y", action="store_true",
                         help="Apply (X,-Y,Z) Blender→UE flip when placing doors/lights/player start "
                              "(see docs/PLAYABLE_CITY.md step 5 — pass this if the imported town looks mirrored)")
    parser.add_argument("--scale", type=float, default=100.0, help="meters → centimeters, forwarded to Unreal import")
    args = parser.parse_args()

    root = _repo_root()
    out_dir = os.path.join(root, args.output)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "pipeline.log")
    open(log_path, "w").close()

    layout_path = os.path.join(out_dir, "layout.json")
    blend_path = os.path.join(out_dir, "city.blend")
    rule_path = os.path.join(root, args.rule)

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
    _run([
        args.blender, "--background", "--factory-startup",
        "--python", os.path.join(root, "city_builder.py"),
        "--",
        "--layout", layout_path,
        "--rule", rule_path,
        "--output", blend_path,
        "--max-blocks", str(args.max_plots),
        "--game-export",
    ], log_path)

    game_json = os.path.splitext(blend_path)[0] + ".game.json"
    lights_json = os.path.splitext(blend_path)[0] + ".lights.json"
    fbx_path = os.path.splitext(blend_path)[0] + ".fbx"
    _log(log_path, "Artifacts:")
    for p in (layout_path, blend_path, fbx_path, game_json, lights_json):
        _log(log_path, "  %s %s" % ("OK" if os.path.isfile(p) else "MISSING", p))

    if not args.ue_project:
        _log(log_path, "")
        _log(log_path, "Blender game export done. Next (one-time UE setup):")
        _log(log_path, "  1. Create a UE5 First Person project")
        _log(log_path, "  2. Enable Editor Scripting + Python Editor Script Plugin")
        _log(log_path, "  3. Create BP_CityDoor (see docs/PLAYABLE_CITY.md)")
        _log(log_path, "  4. Re-run with --ue-project path\\to\\CityFPS.uproject")
        return

    _log(log_path, "=== Stage 3: Unreal import ===")
    unreal = args.unreal_cmd or os.environ.get("UNREAL_EDITOR_CMD") or "UnrealEditor-Cmd"
    import_script = os.path.join(root, "ue", "import_city.py")
    import_args = [
        unreal, args.ue_project, "-unattended",
        "-ExecutePythonScript=%s" % import_script,
        "--",
        "--fbx", fbx_path,
        "--game-json", game_json,
        "--lights-json", lights_json,
        "--scale", str(args.scale),
    ]
    if args.flip_y:
        import_args.append("--flip-y")
    _run(import_args, log_path)
    _log(log_path, "Unreal import finished. Open the project and PIE.")
    if not args.flip_y:
        _log(log_path, "If the town looks mirrored in PIE, re-run this command with --flip-y.")


if __name__ == "__main__":
    main()
