"""
Generate a random city layout, assign varied building rules, build a .blend.

    python run_random_city.py --output out/city.blend --seed 42

First run creates examples/generated_rules/building_00.py … building_19.py
(parameterized templates). Later runs reuse them unless --force-rules.

Requires: numpy/scipy for layout; blender on PATH for the .blend step.
"""
from __future__ import annotations

import argparse
import json
import os
import random as randomlib
import subprocess
import sys


def _repo_root():
    return os.path.abspath(os.path.dirname(__file__))


def _log(path, msg):
    print(msg)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def _run(cmd, log_path, cwd=None):
    _log(log_path, "$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd, cwd=cwd or _repo_root(), capture_output=True, text=True
    )
    if proc.stdout:
        _log(log_path, proc.stdout.rstrip())
    if proc.stderr:
        _log(log_path, proc.stderr.rstrip())
    if proc.returncode != 0:
        raise SystemExit("Command failed (%d): %s" % (proc.returncode, " ".join(cmd)))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Random city layout + building-rule pool → Blender .blend"
    )
    parser.add_argument("--output", default="out/random_city.blend",
                        help="Output .blend path (layout.json is written beside it)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Layout + rule-assignment + builder seed (random if omitted)")
    parser.add_argument("--style", choices=("organic", "polish"), default="organic")
    parser.add_argument("--blocks", type=int, default=40)
    parser.add_argument("--radius", type=float, default=150.0)
    parser.add_argument("--max-blocks", type=int, default=None,
                        help="Cap plots/blocks built (preview)")
    parser.add_argument("--generate-water", action="store_true")
    parser.add_argument("--num-rivers", type=int, default=1)
    parser.add_argument("--num-lakes", type=int, default=1)
    parser.add_argument("--num-ponds", type=int, default=2)
    parser.add_argument("--force-rules", action="store_true",
                        help="Regenerate examples/generated_rules/building_*.py")
    parser.add_argument("--rules-dir", default=None,
                        help="Rule pool directory (default: examples/generated_rules)")
    parser.add_argument("--blender", default=os.environ.get("BLENDER_EXECUTABLE") or "blender")
    parser.add_argument("--skip-roads", action="store_true")
    parser.add_argument("--skip-ground", action="store_true")
    parser.add_argument("--skip-water", action="store_true")
    parser.add_argument("--layout-only", action="store_true",
                        help="Write annotated layout.json only (no Blender)")
    args = parser.parse_args(argv)

    root = _repo_root()
    sys.path.insert(0, root)
    from pro.city.building_rules import (
        annotate_layout_rules,
        default_rules_dir,
        ensure_building_rules,
    )

    seed = args.seed if args.seed is not None else randomlib.randint(1, 10**9)
    out_blend = args.output if os.path.isabs(args.output) else os.path.join(root, args.output)
    out_dir = os.path.dirname(out_blend) or "."
    os.makedirs(out_dir, exist_ok=True)
    layout_path = os.path.join(out_dir, "layout.json")
    log_path = os.path.join(out_dir, "random_city.log")
    open(log_path, "w").close()

    rules_dir = args.rules_dir or default_rules_dir(root)
    _log(log_path, "=== Rule pool (%s) ===" % rules_dir)
    rules = ensure_building_rules(rules_dir, count=20, force=args.force_rules)
    _log(log_path, "Using %d building rules (seed=%s)" % (len(rules), seed))

    _log(log_path, "=== Layout ===")
    layout_cmd = [
        sys.executable, os.path.join(root, "pro", "city", "layout.py"),
        "--output", layout_path,
        "--seed", str(seed),
        "--blocks", str(args.blocks),
        "--radius", str(args.radius),
        "--style", args.style,
    ]
    if args.generate_water:
        layout_cmd.extend([
            "--generate-water",
            "--num-rivers", str(args.num_rivers),
            "--num-lakes", str(args.num_lakes),
            "--num-ponds", str(args.num_ponds),
        ])
    _run(layout_cmd, log_path, cwd=root)

    with open(layout_path, encoding="utf-8") as f:
        layout = json.load(f)
    annotate_layout_rules(layout, rules, seed=seed)
    with open(layout_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    n_rules = sum(
        1 for b in (layout.get("plots") or layout.get("blocks") or [])
        if b.get("rule")
    )
    _log(log_path, "Annotated %d buildable items with rule paths → %s" % (n_rules, layout_path))

    if args.layout_only:
        _log(log_path, "Layout-only mode; skipping Blender.")
        return

    _log(log_path, "=== Blender build ===")
    fallback_rule = rules[0]
    blender_cmd = [
        args.blender, "--background", "--factory-startup",
        "--python", os.path.join(root, "city_builder.py"),
        "--",
        "--layout", layout_path,
        "--rule", fallback_rule,
        "--output", out_blend,
        "--seed", str(seed),
    ]
    if args.max_blocks is not None:
        blender_cmd.extend(["--max-blocks", str(args.max_blocks)])
    if args.skip_roads:
        blender_cmd.append("--skip-roads")
    if args.skip_ground:
        blender_cmd.append("--skip-ground")
    if args.skip_water:
        blender_cmd.append("--skip-water")
    _run(blender_cmd, log_path, cwd=root)

    _log(log_path, "Done.")
    _log(log_path, "  layout: %s" % layout_path)
    _log(log_path, "  blend:  %s" % out_blend)
    _log(log_path, "  log:    %s" % log_path)


if __name__ == "__main__":
    main()
