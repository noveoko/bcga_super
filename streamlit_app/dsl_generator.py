"""
Aerial/street photo -> BCGA rule file (.py), via the Gemini API.

This module is deliberately independent of Streamlit and of bpy, so it can
be unit tested directly (see tests/test_dsl_generator.py) and reused from a
CLI or a different UI. It has two jobs:

1. Turn a user-traced footprint + optional attribute hints into a prompt
   built on the operator contract in examples/IMAGE_TO_RULE_PROMPT.md, call
   Gemini with the cropped photo, and pin the model's BUILDING_WIDTH/
   BUILDING_DEPTH to the footprint the user actually traced (never trust
   the model's own visual size estimate once we have ground truth).

2. Statically validate what comes back -- syntax, the required `from pro
   import *` / `@rule def Begin()` shape, and (this is the part that isn't
   generic Python linting) a check for the exact hallucinated APIs
   IMAGE_TO_RULE_PROMPT.md calls out as the reason earlier attempts broke
   (`spawn_at`, `primitive_cube`, `comp`, `split_v`/`split_h`, `repeat_h`,
   `roof_hip`, `set_material`, `push`/`pop`), plus a check for rules that
   get called but never defined with @rule (the most common way an LLM
   silently invents an API: it "calls" a rule name that sounds plausible
   but was never written).

Nothing here talks to bpy or Blender. A file passing validate_rule_file()
is *structurally* sound -- it still has to actually run inside Blender to
be proven correct end to end; this only guarantees it won't fail for the
already-known reasons.
"""
import ast
import re

PROMPT_MD_PATH = "examples/IMAGE_TO_RULE_PROMPT.md"

# Mirrors the "Not available" list in IMAGE_TO_RULE_PROMPT.md. Kept as a
# separate constant (rather than re-parsing the markdown) so validation
# still works even if the prompt doc's wording changes.
BANNED_CALLS = {
    "primitive_cube", "comp", "split_v", "split_h", "repeat_h", "spawn_at",
    "roof_hip", "set_material", "push", "pop", "primitive_eyebrow_dormer",
    "extrude_moulding", "Init",
}

BANNED_IMPORTS = {"bpy", "numpy", "np"}

# The real operator surface from pro/__init__.py, plus a handful of
# builtins/keywords that legitimately appear as bare PascalCase-looking
# calls won't be confused with a hallucinated rule (none currently are,
# but keeping this explicit rather than a heuristic on capitalization
# alone avoids false positives if the DSL grows new lowercase operators).
KNOWN_OPERATORS = {
    "rectangle", "extrude", "extrude2", "split", "repeat", "color",
    "material", "texture", "delete", "join", "inset", "inset2",
    "hip_roof", "gable_roof", "round_corners", "chance", "switch",
    "choice", "copy", "translate", "partition", "stairwell", "openings",
    "flt", "rel", "param", "random",
}


class RuleFileError(ValueError):
    """Raised when a candidate rule file fails static validation. .problems
    holds every issue found (not just the first), so callers can show a
    complete list or feed it back to the model for a repair pass."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def pixel_polygon_to_meters(pixel_points, target_longest_side_m):
    """
    Converts a footprint the user traced on the cropped image (pixel
    coordinates, y growing downward) into a metric polygon centered on its
    own centroid, y flipped to the up-is-+y convention used throughout
    pro/city (block/plot polygons -- see pro/city/layout.py), scaled so its
    longest bounding-box side equals target_longest_side_m.

    This -- not the model's guess from the photo -- is what should become
    the authoritative BUILDING_WIDTH/BUILDING_DEPTH: the user's trace is
    ground truth, the model only fills in what it can't be given directly
    (storeys, material, ornament, roof style).
    """
    if len(pixel_points) < 3:
        raise ValueError("a footprint needs at least 3 points")
    xs = [p[0] for p in pixel_points]
    ys = [p[1] for p in pixel_points]
    w_px = max(xs) - min(xs)
    h_px = max(ys) - min(ys)
    longest_px = max(w_px, h_px)
    if longest_px <= 0:
        raise ValueError("footprint points are degenerate (zero extent)")
    scale = target_longest_side_m / longest_px
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    return [((px - cx) * scale, -(py - cy) * scale) for px, py in pixel_points]


def footprint_bbox_size_m(points_m):
    xs = [p[0] for p in points_m]
    ys = [p[1] for p in points_m]
    return (max(xs) - min(xs), max(ys) - min(ys))


def build_prompt(operator_contract_md, footprint_points_m, *, storeys=None,
                  role=None, material=None, phase=None, notes=None):
    """
    operator_contract_md: the full text of examples/IMAGE_TO_RULE_PROMPT.md
    (read by the caller -- kept as a parameter rather than read from disk
    here so this stays testable without touching the filesystem).
    """
    width_m, depth_m = footprint_bbox_size_m(footprint_points_m)
    known = []
    known.append(
        "BUILDING_WIDTH = %.2f and BUILDING_DEPTH = %.2f meters -- these come "
        "from a footprint the user traced on the photo and are GROUND TRUTH. "
        "Do not re-estimate them from the image; set the BUILDING_WIDTH / "
        "BUILDING_DEPTH constants to exactly these two numbers." % (width_m, depth_m)
    )
    if storeys:
        known.append("The building has %s storeys (user-confirmed, not a guess)." % storeys)
    if role:
        known.append(
            "Building type/role: %s. Let this steer massing, roof style, and "
            "whether a cellar and full stairs are appropriate (see the "
            "Floors/cellar/stairs section) -- e.g. a barn or shed should skip "
            "the cellar, a church or civic building should not." % role
        )
    if material:
        known.append(
            "Primary facade material: %s. Prefer the closest hex swatch from "
            "the Colors section, or sample an appropriate tone from the photo "
            "if it clearly differs." % material
        )
    if phase:
        phase_notes = {
            "initial": "Site is cleared/staked but not yet built -- if this is "
                       "genuinely pre-construction, a full building rule is not "
                       "appropriate; note that in a comment instead of inventing one.",
            "construction": "Building is mid-construction: represent exposed "
                             "framing / partial walls / missing roof sections "
                             "using ordinary split/extrude/delete, not an "
                             "invented scaffold operator.",
            "built": "Building is complete and in normal condition.",
            "damaged": "Building has visible damage: represent with missing "
                       "wall sections (split + delete), a partially removed "
                       "roof face, or darker/scorched color() swatches -- not "
                       "an invented damage operator.",
            "destroyed": "Building is largely collapsed: keep only the "
                         "remaining walls/foundation as geometry; do not emit "
                         "a full intact building.",
            "aged": "Building is old but intact: use weathered/desaturated "
                    "color() swatches rather than a bright fresh palette.",
        }
        known.append(
            "Construction phase: %s. %s" % (phase, phase_notes.get(phase, ""))
        )
    if notes:
        known.append("Additional notes from the user: %s" % notes)

    header = (
        "Everything below the divider is the fixed operator contract for "
        "this app; follow it exactly. Above the divider is what THIS "
        "specific building request already knows for certain -- treat those "
        "as hard constraints, not suggestions, and infer everything else "
        "from the attached photo per the 'Analysis to perform on the "
        "photo' section.\n\n" + "\n".join("- " + k for k in known) + "\n\n"
        + ("=" * 72) + "\n\n"
    )
    return header + operator_contract_md


def extract_code_block(model_text):
    """Strips a ```python ... ``` fence if present; returns raw text otherwise."""
    match = re.search(r"```(?:python)?\s*(.*?)```", model_text, re.S)
    source = match.group(1) if match else model_text
    return source.strip() + "\n"


def pin_footprint_dimensions(source, width_m, depth_m):
    """
    Belt-and-suspenders: even though the prompt tells the model the exact
    width/depth, rewrite the constants directly if present, so a generation
    can never silently drift from the footprint the user actually traced.
    No-ops (leaves the file untouched) if the model didn't use those exact
    constant names -- validate_rule_file will separately catch that.
    """
    source, n1 = re.subn(
        r"(?m)^BUILDING_WIDTH\s*=.*$", "BUILDING_WIDTH = %.3f" % width_m, source, count=1
    )
    source, n2 = re.subn(
        r"(?m)^BUILDING_DEPTH\s*=.*$", "BUILDING_DEPTH = %.3f" % depth_m, source, count=1
    )
    return source, (n1 == 1 and n2 == 1)


def _decorator_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def validate_rule_file(source):
    """
    Static, bpy-free validation of a candidate rule file. Raises
    RuleFileError (with a .problems list) if anything is wrong; returns
    True if the file is structurally sound. See module docstring for what
    this does and does not guarantee.
    """
    problems = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise RuleFileError(["not valid Python: %s" % e])

    if not re.search(r"(?m)^from pro import \*\s*$", source):
        problems.append("missing required first line `from pro import *`")

    rule_defs = set()
    called_names = set()
    banned_hits = set()
    banned_imports_hit = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if any(_decorator_name(d) == "rule" for d in node.decorator_list):
                rule_defs.add(node.name)
            self.generic_visit(node)

        def visit_Call(self, node):
            name = _call_name(node)
            if name:
                called_names.add(name)
                if name in BANNED_CALLS:
                    banned_hits.add(name)
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BANNED_IMPORTS:
                    banned_imports_hit.add(top)

        def visit_ImportFrom(self, node):
            if node.module and node.module.split(".")[0] in BANNED_IMPORTS:
                banned_imports_hit.add(node.module)

    Visitor().visit(tree)

    if "Begin" not in rule_defs:
        problems.append("no @rule-decorated `Begin` function found")

    if banned_hits:
        problems.append(
            "uses operator(s) this app does not have: %s (see the 'Not "
            "available' list in %s)" % (", ".join(sorted(banned_hits)), PROMPT_MD_PATH)
        )

    if banned_imports_hit:
        problems.append("banned import(s): %s" % ", ".join(sorted(banned_imports_hit)))

    undefined_rule_calls = {
        n for n in called_names
        if n[:1].isupper() and n not in rule_defs and n not in KNOWN_OPERATORS
    }
    if undefined_rule_calls:
        problems.append(
            "calls rule(s) that are never defined with @rule (likely a typo "
            "or a hallucinated rule name): %s" % ", ".join(sorted(undefined_rule_calls))
        )

    if problems:
        raise RuleFileError(problems)
    return True


def generate_rule_file(image_bytes, mime_type, footprint_points_m, *, storeys=None,
                        role=None, material=None, phase=None, notes=None,
                        operator_contract_md=None, api_key=None,
                        model="gemini-2.5-pro", max_repair_attempts=1):
    """
    Calls the Gemini API and returns a validated rule-file source string.

    Requires the `google-genai` package and network access to
    generativelanguage.googleapis.com (not available in every sandboxed
    environment -- this function is intentionally the only place in this
    module that touches either, so the rest of the module stays testable
    offline). Raises RuleFileError if validation still fails after
    max_repair_attempts repair round-trips (each one sends the model back
    its own broken output plus the specific problems found, and asks for a
    fix -- the same static checks that reject an initial draft double as
    the feedback that helps the model correct it).
    """
    from google import genai
    from google.genai import types

    if operator_contract_md is None:
        with open(PROMPT_MD_PATH, encoding="utf-8") as f:
            operator_contract_md = f.read()

    width_m, depth_m = footprint_bbox_size_m(footprint_points_m)
    prompt = build_prompt(
        operator_contract_md, footprint_points_m, storeys=storeys, role=role,
        material=material, phase=phase, notes=notes,
    )

    client = genai.Client(api_key=api_key)
    contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]

    last_error = None
    for attempt in range(max_repair_attempts + 1):
        response = client.models.generate_content(model=model, contents=contents)
        source = extract_code_block(response.text)
        source, _pinned = pin_footprint_dimensions(source, width_m, depth_m)
        try:
            validate_rule_file(source)
            return source
        except RuleFileError as e:
            last_error = e
            if attempt < max_repair_attempts:
                contents = contents + [
                    response.text,
                    "That file fails validation against the operator contract "
                    "above. Fix ALL of the following and re-emit the COMPLETE "
                    "corrected file (same rules as before): "
                    + "; ".join(e.problems),
                ]
    raise last_error
