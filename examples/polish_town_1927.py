"""
Second Polish Republic miasteczko house, circa 1927 (Volhynia / Congress Poland).

Expects a street-aligned rectangular plot in context.cityBlock:
  width, depth, role, roof, wall, frontage, storeys, id

Street edge of the footprint is vertices 0→1, so `front` is the street façade.
"""
import random as pyrandom

from pro import *

__version__ = "2.0.0"
__description__ = "1927 Polish town house: metric façades, gable/hip, shopfronts"
__tags__ = ["city", "poland", "1927", "historic"]

_plot = context.cityBlock or {
    "density": 0.6, "id": 0, "role": "kamienica", "roof": "hip",
    "wall": "plaster", "frontage": "house", "storeys": 2,
    "width": 10.0, "depth": 12.0,
}
pyrandom.seed(1927 + int(_plot.get("id", 0)))

role = _plot.get("role") or "kamienica"
roof_kind = _plot.get("roof") or "hip"
wall = _plot.get("wall") or "plaster"
frontage = _plot.get("frontage") or "house"
storeys = int(_plot.get("storeys") or 2)

PLINTH_H = 0.4
GROUND_H = 3.45 if role != "church" else 4.2
UPPER_H = 3.15
CORNICE_H = 0.25
WALL_H = PLINTH_H + GROUND_H + max(0, storeys - 1) * UPPER_H + CORNICE_H
if role == "church":
    WALL_H += 1.6

# --- Basement / cellar ------------------------------------------------------
# Historically gated by construction type, not just "every building gets
# one": brick/plaster civic and dense urban buildings had cellars for
# storage; single-storey wood-frame rural structures (cottage, barn) sat
# closer to grade on a rubble footing and typically didn't. Depth varies by
# what the space was actually used for (crypt-scale under a church, plain
# storage under a workshop).
HAS_BASEMENT = role not in ("barn", "cottage")
if role == "church":
    BASEMENT_H = 2.6
elif role in ("ratusz", "synagogue"):
    BASEMENT_H = 2.4
elif role == "workshop":
    BASEMENT_H = 2.0
else:
    BASEMENT_H = 2.2

# Cellar access: a proper stairwell, or only a hatch-and-ladder.
# Church/synagogue keep a sealed crypt (no well today). Workshops and
# single-storey buildings typically had a trapdoor; multi-storey masonry
# houses more often had cellar stairs, with a minority still just a ladder.
# Override per plot with basement_access: "stairs" | "ladder".
if not HAS_BASEMENT or role in ("church", "synagogue"):
    BASEMENT_ACCESS = None
elif _plot.get("basement_access") in ("stairs", "ladder"):
    BASEMENT_ACCESS = _plot["basement_access"]
elif role == "workshop" or storeys < 2:
    BASEMENT_ACCESS = "ladder"
else:
    BASEMENT_ACCESS = "ladder" if pyrandom.random() < 0.22 else "stairs"

if wall == "brick":
    FACADE_COLOR = param(choice("#9a4a3a", "#8c4032", "#a35642", "#7a382c"), group="Facade")
elif wall == "wood":
    FACADE_COLOR = param(choice("#8b6a45", "#7a5a38", "#a07a50", "#6e4e32"), group="Facade")
else:
    FACADE_COLOR = param(
        choice(
            "#e8dcc8", "#d4b483", "#e2c4b6", "#c5d1b8",
            "#efe8dc", "#e6c36a", "#d9c2a0", "#c5d4dd",
        ),
        group="Facade",
    )

if role == "church":
    ROOF_COLOR = param(choice("#4f5a48", "#5a4638"), group="Roof")
    ROOF_PITCH = param(round(pyrandom.uniform(48, 54), 1), group="Roof")
    # stone/plaster cornice churches carried a shallower eave than timber outbuildings
    ROOF_OVERHANG = param(round(pyrandom.uniform(0.30, 0.45), 2), group="Roof")
elif role == "barn":
    ROOF_COLOR = param(choice("#6b3d32", "#7a4a32"), group="Roof")
    ROOF_PITCH = param(round(pyrandom.uniform(36, 44), 1), group="Roof")
    # barns/outbuildings favored the deepest eaves, to keep rain off stacked hay/wood
    ROOF_OVERHANG = param(round(pyrandom.uniform(0.50, 0.75), 2), group="Roof")
else:
    ROOF_COLOR = param(choice("#b5523a", "#9c3b28", "#c45c3e", "#a34430"), group="Roof")
    ROOF_PITCH = param(round(pyrandom.uniform(34, 44), 1), group="Roof")
    # typical 1890-1935 kamienica/cottage rafter-tail overhang
    ROOF_OVERHANG = param(round(pyrandom.uniform(0.40, 0.60), 2), group="Roof")

# depth of the painted barge/fascia board hung off the rafter tails
FASCIA_DEPTH = param(round(pyrandom.uniform(0.12, 0.18), 2), group="Roof")
SOFFIT_COLOR = param(choice("#e4ddce", "#d8cfbc", "#c9c0aa"), group="Roof")  # painted underside boards
FASCIA_COLOR = param(choice("#5c4030", "#4a3224", "#6e4a30"), group="Roof")  # painted barge board, usually dark wood

WINDOW_COLOR = param(choice("#2a3338", "#3a3328", "#243038"), group="Facade")
SHOP_GLASS = param("#4a5a62", group="Facade")
PLINTH_COLOR = param(choice("#7a6b56", "#6e6254", "#8a7a64"), group="Facade")
WOOD_COLOR = param(choice("#5c4030", "#4a3224", "#6b4a32"), group="Facade")
CORNICE_COLOR = param(choice("#d0c4b0", "#c4b49a", "#b8a888"), group="Facade")
SLAB_COLOR = param("#9a9284", group="Interior")  # concrete/screed edge & soffit
SLAB_TOP_COLOR = param(choice("#8a6a48", "#7a5c3e", "#9c8060"), group="Interior")  # timber floor finish
BASEMENT_WALL_COLOR = param(choice("#6b6255", "#5e564a", "#776d5e"), group="Interior")
BASEMENT_WINDOW_COLOR = param("#12181c", group="Interior")
INTERIOR_WALL_COLOR = param(choice("#d8d0c4", "#cfc6b8", "#e2dacd"), group="Interior")
ROOM_FLOOR_COLOR = param(choice("#7a5a3a", "#6e4e32", "#8a6844"), group="Interior")

# --- Interior floor slabs --------------------------------------------------
# One horizontal plate per storey level, plus one under the roof (the top
# floor's ceiling/attic floor) -- storeys+1 plates total, the same count a
# real building of this height would actually pour/frame. Elevations are
# derived from the exact same PLINTH_H/GROUND_H/UPPER_H bands StreetFacade()
# already splits the exterior wall into, so a slab always lines up with the
# facade's floor lines instead of being an independent guess.
SLAB_H = 0.18
STAIR_W = 1.05  # side-wall well, split off the street-frontage edge
LADDER_W = 0.65  # trapdoor hatch against the same side wall
LADDER_D = 0.95
LADDER_TREAD = 0.10
LADDER_RISER = 0.28
WALL_MARGIN = 0.18  # exterior wall thickness; matches partition margin
DOOR_H = 2.25
SLAB_ELEVATIONS = [0.0]
for _i in range(1, storeys):
    SLAB_ELEVATIONS.append(PLINTH_H + GROUND_H + (_i - 1) * UPPER_H)
SLAB_ELEVATIONS.append(PLINTH_H + GROUND_H + max(0, storeys - 1) * UPPER_H)


def _street_door_params():
    if frontage == "shop":
        return 1.15, 0.4
    if frontage == "civic":
        return 1.3, 0.6
    if frontage == "blank":
        return 1.1, 0.5
    return 1.15, 0.5


@rule
def Begin():
    color(FACADE_COLOR)
    copy(FloorSlabs())
    if HAS_BASEMENT:
        copy(Basement())
    # Church/synagogue stay sealed landmarks. Everything else is a hollow
    # wall ring so a capsule can walk in from the street door.
    if role in ("church", "synagogue"):
        extrude(
            WALL_H,
            front >> StreetFacade(),
            side >> SideFacade(),
            back >> BackFacade(),
            top >> PitchedRoof(),
            inheritMaterialSide=True,
        )
    else:
        copy(PlaceRoof())
        inset(
            WALL_MARGIN >> FrontWall(),
            WALL_MARGIN >> SideWall(),
            WALL_MARGIN >> BackWall(),
            WALL_MARGIN >> SideWall(),
            cap >> delete(),
        )


@rule
def PlaceRoof():
    translate(0, 0, WALL_H)
    PitchedRoof()


@rule
def FrontWall():
    # Margin strip along street edge 0→1. openings() punches a real door
    # hole and records a Door_* leaf for game export.
    color(FACADE_COLOR)
    door_w, door_off = _street_door_params()
    shape = context.getState().shape
    from pro.openings import Opening
    shape.door_kind = "street"
    shape.openings = [
        Opening(offset=door_off, width=door_w, height=DOOR_H, sill_height=0.0)
    ]
    openings(WALL_H)


@rule
def SideWall():
    color(FACADE_COLOR)
    extrude(WALL_H, front >> SideFacade(), inheritMaterialSide=True)


@rule
def BackWall():
    color(FACADE_COLOR)
    extrude(WALL_H, front >> BackFacade(), inheritMaterialSide=True)


@rule
def FloorSlabs():
    # runs on a COPY of the flat ground-level footprint, taken before
    # Begin()'s extrude() turns the original into the wall volume, so each
    # slab below reuses that same untouched 2D footprint independently.
    # Occupied storeys also get an interior partition copy sitting on top
    # of that storey's slab; the last elevation is the attic plate only.
    _has_stairs = role not in ("church", "synagogue")
    _well_up = _has_stairs and storeys >= 2
    _well_down = BASEMENT_ACCESS is not None
    for i, elevation in enumerate(SLAB_ELEVATIONS[:-1]):
        if i == 0 and _well_down:
            opening = "hatch" if BASEMENT_ACCESS == "ladder" else "well"
        elif i > 0 and _well_up:
            opening = "well"
        else:
            opening = None
        copy(SlabAt(elevation, opening=opening))
        if _has_stairs:
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
        split(
            x,
            LADDER_W >> split(y, LADDER_D >> delete(), flt() >> SlabSolid()),
            flt() >> SlabSolid(),
        )
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
    _has_stairs = role not in ("church", "synagogue")
    _stairs_up = _has_stairs and storeys >= 2
    if _stairs_up:
        split(
            x,
            STAIR_W >> StairFlight(clear_h + SLAB_H),
            flt() >> RoomsOnly(clear_h),
        )
    elif BASEMENT_ACCESS == "stairs":
        split(x, STAIR_W >> delete(), flt() >> RoomsOnly(clear_h))
    elif BASEMENT_ACCESS == "ladder":
        split(
            x,
            LADDER_W >> split(y, LADDER_D >> delete(), flt() >> RoomsOnly(clear_h)),
            flt() >> RoomsOnly(clear_h),
        )
    else:
        RoomsOnly(clear_h)


@rule
def StairFlight(rise, tread=0.27, riser=0.18):
    color(WOOD_COLOR)
    stairwell(rise, tread=tread, riser=riser)


@rule
def BasementAccess():
    # same STAIR_W strip as the upper flights (street-frontage x-split).
    # Stairs fill that strip; a ladder only occupies a trapdoor hatch in
    # the front corner, the rest of the copy is discarded.
    translate(0, 0, -BASEMENT_H)
    rise = BASEMENT_H + SLAB_H
    if BASEMENT_ACCESS == "ladder":
        split(
            x,
            LADDER_W >> split(
                y,
                LADDER_D >> StairFlight(rise, tread=LADDER_TREAD, riser=LADDER_RISER),
                flt() >> delete(),
            ),
            flt() >> delete(),
        )
    else:
        split(x, STAIR_W >> StairFlight(rise), flt() >> delete())


@rule
def RoomsOnly(clear_h):
    partition(
        wall=InteriorWall(max(0.5, clear_h)),
        room=RoomFinish(),
        thickness=0.12,
        margin=0.18,
        min_span=2.0,
        max_span=3.2 if role in ("cottage", "barn", "villa") else 4.5,
        corridor=(1.15 if (role in ("kamienica", "ratusz") or frontage == "shop") else None),
        seed=int(_plot.get("id", 0)),
        door_width=0.9,
        door_height=2.1,
        lights=True,
        height=clear_h,
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
    # extrude() with a NEGATIVE depth carves downward from the same
    # untouched ground-level footprint copy, from z=0 down to
    # z=-BASEMENT_H. Blender/bmesh handles this exactly like the upward
    # WALL_H extrude, just mirrored -- verified directly (see the
    # decompose() face-selector check below) rather than assumed:
    # negative-depth extrusion flags the resulting volume as a "niche"
    # (bpro/shape.py), which flips which selector name the horizontal cap
    # gets routed to. For a normal upward extrude the cap is "top"; here,
    # empirically, it's "bottom" -- so BasementFloor is wired to `bottom`,
    # not `top`, even though it's physically the floor.
    color(BASEMENT_WALL_COLOR)
    extrude(
        -BASEMENT_H,
        front >> BasementFacade(),
        side >> BasementFacade(),
        back >> BasementFacade(),
        bottom >> BasementFloor(),
        inheritMaterialSide=True,
    )


@rule
def BasementFacade():
    # y=0 sits at the deep end (z=-BASEMENT_H) and y=BASEMENT_H at grade
    # (z=0) -- same "lowest-vertex-is-first-loop" rule the upward facades
    # rely on for PLINTH_H being their bottom band, just mirrored here
    # since the extrusion itself runs the other way. Small hopper-style
    # windows sit high in the wall, just under grade, the way real
    # cellar windows do; the lower two-thirds of the wall (against packed
    # earth) stays blank.
    split(
        y,
        flt(max(0.1, BASEMENT_H - 0.85)),
        0.5 >> split(x, flt(0.6), repeat(flt(2.6) >> BasementWindowBay()), flt(0.6)),
        0.35,
    )


@rule
def BasementWindowBay():
    split(x, flt(0.4), 0.9 >> BasementWindow(), flt(0.4))


@rule
def BasementWindow():
    color(BASEMENT_WINDOW_COLOR)


@rule
def BasementFloor():
    color(SLAB_COLOR)


@rule
def StreetFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        GROUND_H >> GroundFloor(),
        repeat(flt(UPPER_H) >> UpperFloor()),
        CORNICE_H >> Cornice(),
    )


@rule
def SideFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        GROUND_H >> split(x, flt(), 2.4 >> WindowBay(), flt()),
        repeat(flt(UPPER_H) >> split(x, flt(), 2.4 >> WindowBay(), flt())),
        CORNICE_H >> Cornice(),
    )


@rule
def BackFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> split(x, flt(), 2.4 >> WindowBay(), flt()),
    )


@rule
def Plinth():
    color(PLINTH_COLOR)


@rule
def Cornice():
    color(CORNICE_COLOR)


@rule
def GroundFloor():
    if frontage == "shop":
        split(
            x,
            0.4,
            1.15 >> Door(),
            0.3,
            repeat(flt(2.5) >> ShopBay()),
            0.4,
        )
    elif frontage == "blank":
        split(x, 0.5, 1.1 >> Door(), flt())
    elif frontage == "civic":
        split(
            x,
            0.6,
            1.3 >> Door(),
            0.5,
            repeat(flt(2.6) >> WindowBay()),
            0.6,
        )
    else:
        split(
            x,
            0.5,
            1.15 >> Door(),
            0.4,
            repeat(flt(2.4) >> WindowBay()),
            0.5,
        )


@rule
def UpperFloor():
    split(
        x,
        0.55,
        repeat(flt(2.4) >> WindowBay()),
        0.55,
    )


@rule
def WindowBay():
    split(
        x,
        flt(0.55),
        1.2 >> split(y, 0.7, 1.55 >> Window(), flt(0.55)),
        flt(0.55),
    )


@rule
def ShopBay():
    split(
        x,
        flt(0.2),
        2.05 >> split(y, 0.35, 2.25 >> ShopWindow(), flt(0.2)),
        flt(0.2),
    )


@rule
def Window():
    color(WINDOW_COLOR)


@rule
def ShopWindow():
    color(SHOP_GLASS)


@rule
def Door():
    split(y, 2.25 >> color(WOOD_COLOR), flt())


@rule
def PitchedRoof():
    # Roofs before ~1935 almost never sat flush on the wall plane: rafters
    # ran past the wall and carried a soffit-and-fascia eave. soffit>>() is a
    # negative inset (pushes the roof edge outward past the wall by
    # ROOF_OVERHANG before the pitch starts), fascia>>() adds the vertical
    # board hanging off the rafter tails.
    pitch = float(ROOF_PITCH)
    overhang = float(ROOF_OVERHANG)
    fasciaDepth = float(FASCIA_DEPTH)
    if roof_kind == "gable":
        gable_roof(
            pitch, overhang,
            face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
            fasciaSize=fasciaDepth,
        )
    elif roof_kind == "halfhip":
        hip_roof(
            pitch, overhang, 90, overhang, pitch, overhang, 58, overhang,
            face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
            fasciaSize=fasciaDepth,
        )
    else:
        hip_roof(
            pitch, overhang,
            face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
            fasciaSize=fasciaDepth,
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
