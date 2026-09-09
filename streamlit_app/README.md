# Aerial photo -> BCGA rule file

A Streamlit front end for turning a photo of one building into a runnable
BCGA rule (`.py`) file: upload, crop to the building, trace its approximate
footprint, tag what you already know (floors, type, material, condition),
and generate.

This is the first stage of a longer-term aerial-image -> playable Unreal
world pipeline; see the conversation/design notes for the full list of
missing pieces (footprint auto-extraction, georeferencing, elevation
wiring, damage/phase geometry, per-building rule selection at city scale).
This piece answers "how does one building's photo become a rule file
someone can actually run," nothing more yet.

## Setup

```bash
pip install -r streamlit_app/requirements.txt
export GEMINI_API_KEY=...   # https://aistudio.google.com/apikey
streamlit run streamlit_app/app.py
```

(The API key can also be pasted into the sidebar for just that session
instead of being set as an environment variable.)

## What it does

1. **Upload + crop** — draw a box around the building of interest so the
   model only sees that building, not the whole scene.
2. **Trace the footprint** — click each corner of the building's outline in
   image order. You also give your best estimate of its longest side in
   meters; the traced shape is scaled to match. This traced footprint is
   treated as *ground truth* — the generated rule file's
   `BUILDING_WIDTH`/`BUILDING_DEPTH` are pinned to exactly it (see
   `dsl_generator.pin_footprint_dimensions`), not re-guessed from the photo.
3. **Tag what you know** — floors, building type, material, condition/phase
   (built / initial / construction / damaged / destroyed / aged). These
   become hard constraints in the prompt, not hints the model can ignore.
4. **Generate** — calls Gemini with the cropped photo and the operator
   contract from `examples/IMAGE_TO_RULE_PROMPT.md` (the same document
   written for pasting into a model by hand; this reuses it programmatically
   instead of reinventing the prompt). The response is statically validated
   before you see it (see below) — if it fails, the app automatically sends
   the model its own broken output plus the exact problems found and asks
   for a fix, up to the configured number of repair attempts.
5. **Download** the resulting `rule.py` and run it, e.g.:
   ```bash
   blender --background --factory-startup --python generate.py -- \
       --rule rule.py --output out/building.blend
   ```

## Why validation matters here

`IMAGE_TO_RULE_PROMPT.md` exists because earlier hand-driven attempts at
this invented APIs the app doesn't have (`primitive_cube`, `comp`,
`spawn_at`, `split_v`, `roof_hip`, `set_material`, ...). Telling the model
not to do that in a prompt helps, but doesn't guarantee it. `dsl_generator.
validate_rule_file()` is a static (no bpy needed) check that:

- confirms the file is valid Python and has `from pro import *` and an
  `@rule`-decorated `Begin()`,
- flags any use of the specific hallucinated operators listed in that doc,
- flags any bare `PascalCase()` call that looks like a rule reference but
  was never defined with `@rule` — the most common way a model invents an
  API without using a banned function name at all (a typo'd or
  never-written rule).

A file passing this is *structurally* sound; it still has to actually run
inside Blender to be proven fully correct end to end (this check has no
bpy dependency, so it can't verify real geometry results) — but it
eliminates the exact class of failure this whole prompt doc was written to
prevent, before you spend a Blender run finding out by hand.

See `tests/test_dsl_generator.py` for the test suite covering the footprint
math, prompt assembly, and every banned-operator/undefined-rule case above
(runs offline, no Gemini/Streamlit/bpy needed: `pytest tests/test_dsl_generator.py`).
