# Image → BCGA rule prompt

Paste everything under **Prompt** into an image-capable model together with the building photo. Save the emitted `.py` and generate:

```powershell
blender --background --factory-startup --python generate.py -- --rule examples/YOUR_FILE.py --output out/building.blend
```

The previous `bcga_super` scripts failed because they invented APIs this app does not have (`primitive_cube`, `comp`, `split_v`, `spawn_at`, `set_material`, `Init`). This prompt binds the model to the real DSL.

---

## Prompt

You are writing a **drop-in BCGA rule file** for this Blender app (a fork of vvoovv/bcga). Analyze the attached building photo and output **one complete Python file** that `generate.py` can run unchanged.

How it will be executed (do not emit this command, just write a file that works with it):

```
blender --background --factory-startup --python generate.py -- --rule YOUR_FILE.py --output out/building.blend
```

`generate.py` always starts from a **20×10 m ground rectangle**. Your `Begin()` **must** replace that footprint with `rectangle(width, depth, MassRule())` and `delete()` the leftover. `--width` / `--depth` CLI flags are ignored.

### Hard constraints

1. First line of code: `from pro import *`
2. Start rule **must** be named `Begin`.
3. Decorate rules with `@rule`. Rules are ordinary functions that **call operators**; they do not return values.
4. Output **only** the Python file (a ` ```python ` block is OK). No invented helpers, no `if __name__`, no bpy, no numpy.
5. Use **only** operators listed below. If a *façade* detail cannot be expressed (eyebrow dormers, classical moulding profiles, named PBR materials, spawn-at-xyz), **omit it or approximate with split/color/extrude**. Do not invent `spawn_at`, `primitive_*`, `comp`, `split_v`, `set_material`, `push`/`pop`, `roof_hip`, `repeat_h`.
6. **Interiors are mandatory** even though a street photo does not show them. Every drop-in building must emit floor slabs, and (unless it is clearly a wood-frame cottage/barn/shed) a cellar, plus stairs or a hatch-ladder. A hollow façade-only shell is incorrect.

Optional metadata at module top:

```python
__version__ = "1.0.0"
__description__ = "one-line description"
__tags__ = ["historic"]
```

### Coordinate system (this is where invented scripts go wrong)

- The initial footprint is a **horizontal 2D face** in XY, Z up. `rectangle(w, d, ...)` is **centered on the current face’s center**.
- After `extrude(H, front>>..., side>>..., back>>..., top>>..., bottom>>...)`, each wall is a **vertical 2D face**.
- On a wall, `split(y, ...)` is **vertical** (height). **y=0 is the lowest vertex** (plinth / grade). `split(x, ...)` is along the wall (frontage).
- `front` is the first edge of the rectangle (street façade if you keep vertex 0→1 as the front).
- Extra masses (wings): `copy()` the still-flat footprint, `translate(dx, dy, dz)` in **meters**, then `rectangle(w, d, WingMass())` and `delete()` the leftover copy. **Do not** pass `replace=True` to `rectangle` inside a `copy()` — it pops the operator stack.
- Offsets are relative to the **current face center**, not a corner origin. Main mass centered at origin occupies x ∈ [−W/2, +W/2], y ∈ [−D/2, +D/2]. A wing overlapping 1 m on the +x gable, set back 1.5 m from the −y front:

```python
WING_DX = W/2 - 1.0 + wing_w/2
WING_DY = -D/2 + 1.5 + wing_d/2
```

### Allowed operators (complete list)

```python
color("#rrggbb")                          # or color(PARAM) where PARAM = param("#rrggbb", group="Facade")
param(value, group="Facade")             # hex color or float; shows in the Blender sidebar
extrude(height, front >> Rule(), side >> Rule(), back >> Rule(),
        top >> Rule(), bottom >> Rule(), inheritMaterialSide=True)
split(x, 0.5 >> A(), flt(2.4) >> B(), 0.5 >> C())   # leftover width goes to flt()
split(y, 0.4 >> Plinth(), flt() >> Wall(), 0.25 >> Cornice())
repeat(flt(2.4) >> WindowBay())          # only inside split(...)
flt(value=1), rel(value)
copy(Rule())                             # 2D faces only, before extrude
translate(dx, dy, dz)                    # 2D faces only
rectangle(width, depth, Rule())          # new axis-aligned rect at current center
delete()
stairwell(rise, tread=0.27, riser=0.18)  # 2D rectangle → stepped flight
partition(wall=InteriorWall(h), room=RoomFinish(), thickness=0.12,
          margin=0.18, min_span=2.0, max_span=4.5, corridor=1.15,
          seed=1, door_width=0.9, door_height=2.1,
          lights=True, height=clear_h)  # ceiling point lights; omit lights= for none
openings(h)                              # punch doors recorded by partition()
hip_roof(pitch, overhang, face >> RoofFace(), soffit >> SoffitFace(),
         fascia >> FasciaFace(), fasciaSize=0.14)
gable_roof(pitch, overhang, face >> RoofFace(), soffit >> SoffitFace(),
           fascia >> FasciaFace(), fasciaSize=0.14)   # 4-edge rectangles only
# half-hip example:
# hip_roof(pitch, oh, 90, oh, pitch, oh, 58, oh, face >> RoofFace(), ...)
inset(0.08)                              # optional; prefer split+color for windows
extrude2(...)                            # advanced; avoid unless needed
```

Selectors for `extrude(...)`: `front`, `back`, `left`, `right`, `side`, `top`, `bottom`, `all`.
Roof selectors: `face`, `soffit`, `fascia`.

**Not available:** `primitive_cube`, `comp`, `split_v`/`split_h`, `repeat_h`, `spawn_at`, `roof_hip`, `set_material`, `material("Name")` as a library of presets, `push`/`pop`, `primitive_eyebrow_dormer`, `extrude_moulding`, `bcga.*`.

### Colors, not material names

There is no material library. Paint with hex via `color()` / `param()`:

- plaster / stucco: `#efe8dc`, `#e8dcc8`
- historic brick: `#9a4a3a`, `#8c4032`
- wood trim: `#5c4030` or painted `#f4eee4`
- standing-seam / painted metal roof: `#4a5c48` (green-grey), `#b5523a` (red)
- glass: `#2c3336`
- plinth / stone: `#7a6b56`

### Canonical single-mass skeleton

```python
from pro import *

BUILDING_WIDTH = 16.0
BUILDING_DEPTH = 10.0
WALL_H = 4.2
PLINTH_H = 0.45
CORNICE_H = 0.25
ROOF_PITCH = 36.0
ROOF_OVERHANG = 0.45
HAS_BASEMENT = True
BASEMENT_H = 2.2
BASEMENT_ACCESS = "stairs"

PLASTER = param("#efe8dc", group="Facade")
PLINTH_COLOR = param("#7a6b56", group="Facade")
GLASS = param("#2c3336", group="Facade")
ROOF_COLOR = param("#4a5c48", group="Roof")
SOFFIT_COLOR = param("#d8cfbc", group="Roof")
FASCIA_COLOR = param("#3d3328", group="Roof")

@rule
def Begin():
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()

@rule
def MainMass():
    # interiors MUST be copied here, on the new rectangle, BEFORE extrude.
    # Do not copy them from Begin() — that still has the leftover 20×10.
    copy(FloorSlabs())
    if HAS_BASEMENT:
        copy(Basement())
    color(PLASTER)
    extrude(
        WALL_H,
        front >> StreetFacade(),
        side >> SideFacade(),
        back >> BackFacade(),
        top >> PitchedRoof(),
        inheritMaterialSide=True,
    )

@rule
def StreetFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> GroundFloor(),
        CORNICE_H >> Cornice(),
    )

@rule
def GroundFloor():
    split(x, 0.5, repeat(flt(2.4) >> WindowBay()), 0.5)

@rule
def WindowBay():
    split(x, flt(0.5), 1.2 >> split(y, 0.7, 1.6 >> Window(), flt()), flt(0.5))

@rule
def Window():
    color(GLASS)

@rule
def Plinth():
    color(PLINTH_COLOR)

@rule
def Cornice():
    color(PLASTER)

@rule
def SideFacade():
    split(y, PLINTH_H >> Plinth(), flt() >> split(x, flt(), 1.2 >> Window(), flt()), CORNICE_H >> Cornice())

@rule
def BackFacade():
    SideFacade()

@rule
def PitchedRoof():
    hip_roof(
        ROOF_PITCH, ROOF_OVERHANG,
        face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
        fasciaSize=0.14,
    )

@rule
def RoofFace():
    color(ROOF_COLOR)

@rule
def SoffitFace():
    color(SOFFIT_COLOR)

@rule
def FasciaFace():
    color(FASCIA_COLOR)
```

### Extra mass (wing) — required pattern

```python
@rule
def Begin():
    copy(PlaceWing())
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()

@rule
def PlaceWing():
    translate(WING_DX, WING_DY, 0)
    rectangle(WING_WIDTH, WING_DEPTH, WingMass())
    delete()
```

`copy()` **before** the main `rectangle()` so the duplicate is still the default ground face. Each mass that is a real building (main and a habitable wing) gets its own `copy(FloorSlabs())` / `copy(Basement())` inside *that* mass rule, before its `extrude`.

### Floors, cellar, stairs — mandatory (not visible in the photo)

These operators exist and must be used. Defaults:

- **Cellar** unless the building is clearly a wood-frame cottage, barn, or shed.
- **Stairs** (full `STAIR_W` well) if storeys ≥ 2; **hatch + steep ladder** if storeys == 1 and there is a cellar.
- `SLAB_ELEVATIONS` must match the façade `split(y, ...)` floor lines: `0.0`, each occupied floor, then one plate at `WALL_H` (attic ceiling).

```python
HAS_BASEMENT = True
BASEMENT_H = 2.2
BASEMENT_ACCESS = "stairs"   # or "ladder" for 1-storey cellars; None for cottage/barn
SLAB_H = 0.18
STAIR_W = 1.05
LADDER_W, LADDER_D = 0.65, 0.95
SLAB_ELEVATIONS = [0.0, GROUND_H + PLINTH_H, WALL_H]  # example: 1 upper floor + ceiling

SLAB_COLOR = param("#9a9284", group="Interior")
SLAB_TOP_COLOR = param("#8a6a48", group="Interior")
BASEMENT_WALL_COLOR = param("#6b6255", group="Interior")
BASEMENT_WINDOW_COLOR = param("#12181c", group="Interior")
INTERIOR_WALL_COLOR = param("#d8d0c4", group="Interior")
ROOM_FLOOR_COLOR = param("#7a5a3a", group="Interior")
WOOD_COLOR = param("#5c4030", group="Interior")

@rule
def FloorSlabs():
    _well_up = len(SLAB_ELEVATIONS) > 2
    _well_down = BASEMENT_ACCESS is not None
    for i, elevation in enumerate(SLAB_ELEVATIONS[:-1]):
        if i == 0 and _well_down:
            opening = "hatch" if BASEMENT_ACCESS == "ladder" else "well"
        elif i > 0 and _well_up:
            opening = "well"
        else:
            opening = None
        copy(SlabAt(elevation, opening=opening))
        clear_h = SLAB_ELEVATIONS[i + 1] - elevation - SLAB_H
        copy(InteriorAt(elevation + SLAB_H, clear_h))
    copy(SlabAt(SLAB_ELEVATIONS[-1], opening=("well" if _well_up else None)))
    if _well_down:
        copy(BasementAccess())

@rule
def SlabAt(elevation, opening=None):
    translate(0, 0, elevation)
    if opening == "well":
        split(x, STAIR_W >> delete(), flt() >> SlabSolid())
    elif opening == "hatch":
        split(x, LADDER_W >> split(y, LADDER_D >> delete(), flt() >> SlabSolid()), flt() >> SlabSolid())
    else:
        SlabSolid()

@rule
def SlabSolid():
    color(SLAB_COLOR)
    extrude(SLAB_H, top >> SlabTop(), inheritMaterialSide=True)

@rule
def SlabTop():
    color(SLAB_TOP_COLOR)

@rule
def InteriorAt(elevation, clear_h):
    translate(0, 0, elevation)
    if BASEMENT_ACCESS == "stairs" or len(SLAB_ELEVATIONS) > 2:
        split(x, STAIR_W >> StairFlight(clear_h + SLAB_H), flt() >> RoomsOnly(clear_h))
    elif BASEMENT_ACCESS == "ladder":
        split(x, LADDER_W >> split(y, LADDER_D >> delete(), flt() >> RoomsOnly(clear_h)),
              flt() >> RoomsOnly(clear_h))
    else:
        RoomsOnly(clear_h)

@rule
def StairFlight(rise, tread=0.27, riser=0.18):
    color(WOOD_COLOR)
    stairwell(rise, tread=tread, riser=riser)

@rule
def BasementAccess():
    translate(0, 0, -BASEMENT_H)
    rise = BASEMENT_H + SLAB_H
    if BASEMENT_ACCESS == "ladder":
        split(x, LADDER_W >> split(y, LADDER_D >> StairFlight(rise, tread=0.10, riser=0.28),
                                   flt() >> delete()), flt() >> delete())
    else:
        split(x, STAIR_W >> StairFlight(rise), flt() >> delete())

@rule
def RoomsOnly(clear_h):
    partition(
        wall=InteriorWall(max(0.5, clear_h)),
        room=RoomFinish(),
        thickness=0.12, margin=0.18, min_span=2.0, max_span=4.5,
        corridor=1.15, seed=1, door_width=0.9, door_height=2.1,
        lights=True, height=clear_h,
    )

@rule
def InteriorWall(h):
    color(INTERIOR_WALL_COLOR)
    openings(h)

@rule
def RoomFinish():
    color(ROOM_FLOOR_COLOR)

@rule
def Basement():
    # negative extrude: the physical floor is selector `bottom`, not `top`
    color(BASEMENT_WALL_COLOR)
    extrude(-BASEMENT_H, front >> BasementFacade(), side >> BasementFacade(),
            back >> BasementFacade(), bottom >> BasementFloor(), inheritMaterialSide=True)

@rule
def BasementFacade():
    split(y, flt(max(0.1, BASEMENT_H - 0.85)),
          0.5 >> split(x, flt(0.6), repeat(flt(2.6) >> BasementWindow()), flt(0.6)), 0.35)

@rule
def BasementWindow():
    color(BASEMENT_WINDOW_COLOR)

@rule
def BasementFloor():
    color(SLAB_COLOR)
```

### Chimneys — no spawn_at

From the **roof face** (still 2D, before `hip_roof`), copy, translate in the roof plane, then a small rectangle and extrude. `dx, dy` are from the **roof-face center**. Ridge height ≈ `tan(pitch_rad) * (depth/2)`:

```python
@rule
def PitchedRoof():
    copy(ChimneyAt(-5.0, 0.0))
    copy(ChimneyAt(5.0, 0.0))
    hip_roof(ROOF_PITCH, ROOF_OVERHANG, face >> RoofFace(), soffit >> SoffitFace(),
             fascia >> FasciaFace(), fasciaSize=0.14)

@rule
def ChimneyAt(dx, dy):
    rise = BUILDING_DEPTH / 2.0 * 0.577   # tan(30°)
    translate(dx, dy, rise)
    rectangle(0.8, 0.8, ChimneyStack())
    delete()

@rule
def ChimneyStack():
    color(PLASTER)
    extrude(1.5)
```

### Split rules of thumb

- Bare numbers (`0.5`) are gaps with no child rule. `0.5 >> Rule()` applies a rule.
- **Always** give leftover length to `flt(...)` so parts do not have to sum exactly to the wall.
- Count bays from the photo (e.g. 2–3–2 windows) and encode that count with `repeat` or explicit `split(x, ...)`.
- Typical historic window: 1.1–1.3 m wide, 1.5–1.8 m glass, sill ~0.7 m above plinth.
- Do **not** `extrude()` a face and then `split()` it — split is 2D. Split first, then extrude sills/pilasters on the resulting strips.
- Negative `extrude(-d)` is a niche; if you must recess a window, stop at coloring the pane. Do not split the niche volume.

### Analysis to perform on the photo (then encode)

1. Count independent masses (main, wing). Estimate width × depth × wall-height in meters from people, windows (~1.2 m), storeys.
2. Roof: hip / gable / half-hip; pitch ~30–45°; overhang ~0.3–0.6 m.
3. Façade: storeys, plinth, cornice, pilasters, bay rhythm, door.
4. Colors from the photo (hex). Brick vs plaster vs wood vs metal roof.
5. Chimneys: count and rough x-position along the ridge.
6. Interiors (required, inferred not seen): storey count → `SLAB_ELEVATIONS`; masonry/urban → cellar; storeys ≥ 2 → stairs, else hatch+ladder.

Prefer a **faithful, runnable simplification** of *façade ornaments* over unrunnable moulding profiles. Do **not** simplify away floor slabs, the cellar, or the stair/ladder well.
