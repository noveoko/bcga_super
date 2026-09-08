"""
Headless / batch entry point for BCGA.

Generates one or more buildings from a BCGA rule file without opening the
Blender GUI, and exports the result. Intended to be run as:

    blender --background --factory-startup --python generate.py -- \\
        --rule path/to/rule.py --output out.obj

Run `blender --background --python generate.py -- --help` for all options.

NOTE ON HEADLESS SAFETY:
Only object-level operators (mode_set, select_all, delete, duplicate,
transform_apply) are used here, none of which need an open 3D Viewport.
Anything that depends on a live UI area -- bpy.ops.view3d.*,
bpy.ops.screen.*, bpy.ops.wm.invoke_* (modal operators) -- is deliberately
never called from this script, since those raise
"RuntimeError: ... poll() failed, context is incorrect" in --background mode.
"""
import argparse
import os
import random
import sys


def parse_args(argv=None):
    """
    Parses CLI arguments. Split out from main() so it can be unit tested
    without importing bpy (this function has no Blender dependency).
    """
    if argv is None:
        argv = sys.argv[1:]
    # Blender passes its own args before "--"; only what's after belongs to us
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate BCGA building(s) from a rule file, headlessly.",
    )
    parser.add_argument(
        "--rule", required=True,
        help="Path to a BCGA rule .py file (e.g. examples/house_01.py)",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output file. Extension selects the format: "
             ".blend, .obj, .glb/.gltf, .fbx",
    )
    parser.add_argument(
        "--width", type=float, default=20,
        help="Footprint width in meters for the default rectangle base "
             "(ignored if the rule file replaces the footprint itself)",
    )
    parser.add_argument(
        "--depth", type=float, default=10,
        help="Footprint depth in meters for the default rectangle base",
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of building variants to generate side by side "
             "(useful with random() params in the rule file)",
    )
    parser.add_argument(
        "--spacing", type=float, default=5,
        help="Gap in meters between variants when --count > 1",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed, for reproducible variants",
    )
    parser.add_argument(
        "--export-json",
        help="Also write a resolved JSON description of the generated "
             "building(s) to this path (a single object for --count 1, "
             "a JSON array for --count > 1). See pro.base.Rule.to_dict().",
    )
    return parser.parse_args(argv)


def _clear_scene():
    import bpy
    bpy.ops.object.select_all(action="SELECT")
    if bpy.context.selected_objects:
        bpy.ops.object.delete()


def _export(output_path):
    import bpy
    ext = os.path.splitext(output_path)[1].lower()
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if ext == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
    elif ext == ".obj":
        # bpy.ops.export_scene.obj was removed in Blender 4.0;
        # wm.obj_export is the current (C++) exporter.
        bpy.ops.wm.obj_export(filepath=output_path, export_selected_objects=False)
    elif ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(filepath=output_path)
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=output_path)
    else:
        raise ValueError(
            "Unsupported --output extension '%s'. Use .blend, .obj, .glb, .gltf, or .fbx" % ext
        )


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    import bpy
    from pro import context as proContext
    import bpro

    proContext.blenderContext = bpy.context

    _clear_scene()

    ruleFile = os.path.abspath(args.rule)
    if not os.path.isfile(ruleFile):
        print("ERROR: rule file not found: %s" % ruleFile, file=sys.stderr)
        sys.exit(1)

    traces = [] if args.export_json else None
    proContext.allCeilingLights = []
    proContext.allGameDoors = []

    for i in range(max(1, args.count)):
        # bpro.apply() creates its own default rectangle footprint via
        # create_rectangle() whenever there's no valid single-face mesh
        # already selected/active, which is always true right after
        # _clear_scene(), so each iteration starts from a clean footprint.
        module, params = bpro.apply(ruleFile, trace=bool(args.export_json))

        if traces is not None:
            traces.append(proContext.buildingTrace)

        obj = bpy.context.object
        if obj is not None and args.count > 1:
            obj.location.x += i * (args.width + args.spacing)
            obj.name = "BCGA_%03d" % i

        # deselect so the next iteration's create_rectangle() fallback
        # in bpro.apply() doesn't try to reuse/delete this object
        bpy.ops.object.select_all(action="DESELECT")

    _export(args.output)

    if args.export_json:
        import json
        payload = traces[0] if args.count <= 1 else traces
        jsonPath = os.path.abspath(args.export_json)
        os.makedirs(os.path.dirname(jsonPath) or ".", exist_ok=True)
        with open(jsonPath, "w") as f:
            json.dump(payload, f, indent=2)
        print("Wrote building trace JSON to %s" % jsonPath)

    allLights = getattr(proContext, "allCeilingLights", None) or []
    if allLights:
        from pro.lights import lights_sidecar
        import json
        lightsPath = os.path.splitext(os.path.abspath(args.output))[0] + ".lights.json"
        with open(lightsPath, "w") as f:
            json.dump(lights_sidecar(allLights), f, indent=2)
        print("Wrote %d ceiling light(s) to %s" % (len(allLights), lightsPath))

    print("Wrote %d building(s) to %s" % (args.count, args.output))


if __name__ == "__main__":
    # allow "import bpro"/"import pro" to resolve when this script is run
    # from an arbitrary working directory via `blender -b -P generate.py`
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        # Blender exits 0 by default even on a Python exception unless we
        # exit explicitly, which would make CI/batch failures go unnoticed
        sys.exit(1)
