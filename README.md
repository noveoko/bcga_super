# BCGA Super

Fork of [vvoovv/bcga](https://github.com/vvoovv/bcga): Computer Generated Architecture for Blender. Buildings are Python **rule files** (a CGA-style shape grammar). This fork adds headless generation, a city layout pipeline, and a 1927 Polish-town example that places **street-aligned houses**, not one pyramid per Voronoi cell.

Tested with **Blender 5.1** on Windows. Layout generation is ordinary Python (no `bpy`).

## What it does

1. **Single building** — apply a rule to a rectangular footprint, export `.blend` / `.obj` / `.glb` / `.fbx`.
2. **City** — Voronoi streets → JSON layout → one mesh per plot in Blender, plus roads, ground, sun, camera.
3. **1927 Polish miasteczko** — Magdeburg-plan **rynek**, parcels along street edges (~7–14 × 8–16 m), kamienice / cottages / workshops / barns / church / ratusz / synagogue, metric façades, gable/hip roofs, shopfronts, chimneys.

## Requirements

| Piece | Needs |
|---|---|
| Layout JSON (`pro/city/layout.py`) | Python 3.11+, `numpy`, `scipy` |
| `city_builder.py` / `generate.py` | `blender` on `PATH` (or `BLENDER_EXECUTABLE`) |
| TUI (`bcga_tui.py`) | `pip install rich`, plus Blender |
| Tests | `pip install pytest numpy scipy` |

```powershell
pip install numpy scipy pytest rich
```

## Generate a 1927 Polish town

Two steps. Layout is **not** run inside Blender.

```powershell
mkdir out -ErrorAction SilentlyContinue

python -c "from pro.city.layout import generate_polish_town_layout, save_city_layout; save_city_layout(generate_polish_town_layout(seed=1927), 'out/polish_town_1927.json')"

blender --background --factory-startup --python city_builder.py -- --layout out/polish_town_1927.json --rule examples/polish_town_1927.py --output out/polish_town_1927.blend
```

Open `out/polish_town_1927.blend`. `--max-blocks N` builds only the first N houses (preview). `--skip-roads` / `--skip-ground` skip the cobble ribbons and ground disk.

Same layout CLI:

```powershell
python pro/city/layout.py --style polish --output out/polish_town_1927.json --seed 1927
```

Each **plot** is a 4-vertex rectangle; vertex 0→1 is the street edge, so the rule’s `front` is the street façade. `context.cityBlock` is that plot (`role`, `roof`, `wall`, `frontage`, `storeys`, `width`, `depth`).

## Generate one building

```powershell
blender --background --factory-startup --python generate.py -- --rule examples/polish_town_1927.py --output out/house.blend --width 10 --depth 12 --seed 1927
```

`--count 4 --spacing 6` lays variants side by side. `--export-json trace.json` writes a `bcga-trace` generation record (authored random/choice/param sources plus resolved values; see `docs/CONTEXT.md` Priority 6).

## Random city (one command)

Layout + a pool of 20 building styles → one `.blend`:

```powershell
python run_random_city.py --output out/city.blend --seed 42
```

First run writes `examples/generated_rules/building_00.py` … `building_19.py` (reused later unless `--force-rules`). Each plot/block gets a random rule from that pool. Options: `--style polish`, `--blocks 40`, `--radius 150`, `--generate-water`, `--max-blocks 20` (preview), `--layout-only`.

### Rule workshop (Streamlit)

Paste/upload a DSL rule → Blender `.blend` + PNG preview; optionally save into the town rule pool:

```powershell
streamlit run streamlit_app/rule_workshop.py
```

See `streamlit_app/README.md`.

## Generic organic city

Voronoi blocks without parceling (one building per cell — the old demo):

```powershell
python pro/city/layout.py --output out/city.json --blocks 40 --radius 150 --seed 1
blender --background --factory-startup --python city_builder.py -- --layout out/city.json --rule examples/city_building.py --output out/city.blend
```

`examples/city_building.py` reads density via `city_block()` inside `Begin()` (1 at center, 0 at the edge) and varies height / colour / roof. Prefer that over module-level `context.cityBlock` — see `docs/CONTEXT.md` (Phase 5).

### Rivers, streams, creeks, lakes, ponds & watersheds

`pro/city/water.py` adds water features to a layout. Any road that crosses a river/stream/creek/lake/pond gets automatically split, and the piece over the water is tagged `"bridge": True` so `city_builder.py` builds an actual elevated bridge (deck + piers + railings) there instead of a road running into the water.

```powershell
python pro/city/layout.py --output out/city.json --blocks 60 --radius 200 --seed 1 \
    --generate-water --num-rivers 1 --num-lakes 1 --num-ponds 2
blender --background --factory-startup --python city_builder.py -- --layout out/city.json --rule examples/city_building.py --output out/city.blend
```

`--num-streams` / `--num-creeks` / `--num-watersheds` add the other feature types (a watershed is a catchment boundary, not open water, so it doesn't get bridged by default). `--river-width` / `--stream-width` / `--creek-width` set bank-to-bank width in meters, and `--bridge-margin` controls how far a bridge extends past the water's edge. Pass `--skip-water` to `city_builder.py` to build the layout without water/bridge geometry even if the layout JSON has a `"water"` list.

## Blender addon

This repo is still a Blender addon (`bl_info` in `__init__.py`; operators live in `addon.py`).

1. Clone or copy the folder into Blender’s addons directory, **or** *Edit → Preferences → Add-ons → Install* from the repo zip.
2. Enable **BCGA**.
3. 3D View sidebar → **BCGA**: set a footprint, pick a rule `.py` (text block or external file), **Apply**.

Rule params with `param(..., group=..., unit=...)` show grouped in the Apply panel.

## Terminal UI

Iterate on rule files without opening the Blender GUI:

```powershell
python bcga_tui.py examples
```

Needs `rich` and a `blender` executable.

## Rule language (this fork)

On top of upstream BCGA (`extrude`, `split`, `decompose`, `hip_roof`, `color`, …):

| Call | Purpose |
|---|---|
| `choice("a", "b", weights=[0.7, 0.3])` | One discrete value per building |
| `chance((0.6, RuleA()), (0.4, RuleB()))` | Pick one rule |
| `switch(value, {"x": RuleX()}, default=RuleY())` | Branch |
| `gable_roof(pitch[, overhang], face>>.., soffit>>.., fascia>>.., fasciaSize=..)` | Gable on a **4-edge** rectangle. `overhang` (m) pushes the roof edge out past the wall before the pitch starts, instead of cutting off flush at the wall face -- realistic for pre-1930s eaves; `soffit`/`fascia` are optional rules for the underside/barge-board faces |
| `hip_roof(pitch[, overhang], ..., face>>.., soffit>>.., fascia>>.., fasciaSize=..)` | Hip roof; same overhang mechanics as `gable_roof`. Per-edge pitches/overhangs supported (`hip_roof(p1,o1, p2,o2, p3,o3, p4,o4, ...)`) |
| `param(value, group="Facade", unit="m")` | Sidebar grouping |

`generate.py` / `city_builder.py` open a `GenerationSession` and call `session.set_city_block(...)` before each apply. Rule files should read it with `city_block(default)` inside `Begin()` (standalone runs get the default when unset).

## Tests

```powershell
python -m pytest
```

Layout and parceler tests need numpy/scipy. Integration tests that launch Blender are marked `integration` and skipped by default (`pytest.ini`).

## Layout vs geometry

- `pro/city/layout.py` + `pro/city/parcels.py` — pure Python, writes JSON (`blocks`, `roads`, `plots`).
- `city_builder.py` — Blender only: footprints, rules, chimneys, rynek stalls, road ribbons, export.

Do not import `numpy`/`scipy` from inside Blender.

## Upstream BCGA

Original project: [vvoovv/bcga](https://github.com/vvoovv/bcga). Tutorial: [wiki](https://github.com/vvoovv/bcga/wiki/Tutorial). Example rules: [bcga-examples](https://github.com/vvoovv/bcga-examples) ([simple01](https://github.com/vvoovv/bcga-examples/blob/master/examples/simple01.py), [house_01](https://github.com/vvoovv/bcga-examples/blob/master/examples/house_01.py)).

twitter: [@prokitektura](https://twitter.com/prokitektura) · [blenderartists thread](https://blenderartists.org/t/addon-bcga-computer-generated-architecture-for-blender-3d-buildings-with-python/551081)

## Donations (upstream)

If you like the original BCGA, consider a donation:

[![Please donate](https://www.paypalobjects.com/en_US/GB/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ZZ7CHNYKWYYZE)
