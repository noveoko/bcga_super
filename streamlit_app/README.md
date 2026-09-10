# Streamlit apps

## Rule workshop (DSL → Blender preview)

Paste or upload a BCGA rule file, build a `.blend`, render a PNG preview, and
optionally save the rule into `examples/generated_rules/` for
`run_random_city.py`.

```bash
pip install -r streamlit_app/requirements.txt
# Blender on PATH, or: set BLENDER_EXECUTABLE=...
streamlit run streamlit_app/rule_workshop.py
```

No Gemini key required. Saved rules become `building_20.py`, `building_21.py`, …
(so regenerating presets 00–19 with `--force-rules` does not wipe them).

## Aerial photo -> BCGA rule file

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
streamlit run streamlit_app/app.py
```

### Gemini API key via Kryptic (recommended)

This repo already has `kryptic.json` (`proj_c2c4ecfa09b8` / `development`).

1. Install the [Kryptic daemon](https://kryptic.dev/download) and run `kryptic login`.
2. In the [dashboard](https://app.kryptic.dev), open this project → **development** → add secret **`GEMINI_API_KEY`** (value from [Google AI Studio](https://aistudio.google.com/apikey)).
3. From the repo root: `streamlit run streamlit_app/app.py` — `kryptic.inject()` loads the key into `os.environ` automatically.

Fallbacks: set `GEMINI_API_KEY` in your shell, or paste into the sidebar for one session.

### CI

`.github/workflows/ci.yml` can export vault secrets with a machine identity:

1. Create a machine identity in the Kryptic dashboard and copy the client id/secret.
2. Add GitHub repo secrets `KRYPTIC_CLIENT_ID` and `KRYPTIC_CLIENT_SECRET`.
3. The workflow runs `kryptic ci export --project proj_c2c4ecfa09b8 --env development` before any secret-dependent steps.

Pytest itself does not need Gemini; the export step is ready when you add smoke tests that call the API.

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
5. **Download** the resulting `rule.py`, then use **Build & preview in Blender**
   in the same page (needs Blender on PATH / `BLENDER_EXECUTABLE`) to produce a
   `.blend` + PNG. You can also **Save rule to town library** for
   `run_random_city.py`.

   Paste-only DSL → Blender (no photo/Gemini):  
   `streamlit run streamlit_app/rule_workshop.py`

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
