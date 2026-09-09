"""
Szkoła (village school) — brick civic massing with tall classrooms, ~1927.

Run standalone:
  blender --background --factory-startup --python generate.py -- \\
      --rule examples/szkola_school.py --output out/szkola_school.blend
"""
from pro import *

__version__ = "1.0.0"
__description__ = "1927 Polish village school (szkoła)"
__tags__ = ["poland", "1927", "school", "civic"]

BUILDING_WIDTH = 16.0
BUILDING_DEPTH = 12.0
PLINTH_H = 0.45
GROUND_H = 3.7
UPPER_H = 3.3
CORNICE_H = 0.3
WALL_H = PLINTH_H + GROUND_H + UPPER_H + CORNICE_H

ROOF_PITCH = 40.0
ROOF_OVERHANG = 0.5
FASCIA_DEPTH = 0.16

FACADE_COLOR = param("#8c4032", group="Facade")
PLINTH_COLOR = param("#5a5248", group="Facade")
WOOD_COLOR = param("#4a3224", group="Facade")
WINDOW_COLOR = param("#1e2830", group="Facade")
CORNICE_COLOR = param("#c4b49a", group="Facade")
ROOF_COLOR = param("#a34430", group="Roof")
SOFFIT_COLOR = param("#d8cfbc", group="Roof")
FASCIA_COLOR = param("#4a3224", group="Roof")
SLAB_COLOR = param("#9a9284", group="Interior")
SLAB_TOP_COLOR = param("#8a6a48", group="Interior")
BASEMENT_WALL_COLOR = param("#5e564a", group="Interior")
INTERIOR_WALL_COLOR = param("#d8d0c4", group="Interior")
ROOM_FLOOR_COLOR = param("#7a5a3a", group="Interior")

HAS_BASEMENT = True
BASEMENT_H = 2.4
BASEMENT_ACCESS = "stairs"
SLAB_H = 0.18
STAIR_W = 1.2
DOOR_H = 2.4
WALL_MARGIN = 0.2
SLAB_ELEVATIONS = [0.0, PLINTH_H + GROUND_H, WALL_H]


@rule
def Begin():
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()


@rule
def MainMass():
    color(FACADE_COLOR)
    copy(FloorSlabs())
    copy(Basement())
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
    hip_roof(
        ROOF_PITCH, ROOF_OVERHANG,
        face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
        fasciaSize=FASCIA_DEPTH,
    )


@rule
def FrontWall():
    color(FACADE_COLOR)
    from pro.openings import Opening
    shape = context.getState().shape
    shape.door_kind = "street"
    shape.openings = [Opening(offset=0.55, width=1.35, height=DOOR_H, sill_height=0.0)]
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
    copy(SlabAt(SLAB_ELEVATIONS[0], opening="well"))
    copy(InteriorAt(SLAB_ELEVATIONS[0] + SLAB_H, GROUND_H - SLAB_H))
    copy(SlabAt(SLAB_ELEVATIONS[1], opening="well"))
    copy(InteriorAt(SLAB_ELEVATIONS[1] + SLAB_H, UPPER_H - SLAB_H))
    copy(SlabAt(SLAB_ELEVATIONS[2], opening="well"))
    copy(BasementAccess())


@rule
def SlabAt(elevation, opening=None):
    translate(0, 0, elevation)
    if opening == "well":
        split(x, STAIR_W >> delete(), flt() >> SlabSolid())
    else:
        SlabSolid()


@rule
def SlabSolid():
    color(SLAB_COLOR)
    extrude(SLAB_H, top >> color(SLAB_TOP_COLOR), inheritMaterialSide=True)


@rule
def InteriorAt(elevation, clear_h):
    translate(0, 0, elevation)
    split(x, STAIR_W >> StairFlight(clear_h + SLAB_H), flt() >> RoomsOnly(clear_h))


@rule
def StairFlight(rise, tread=0.27, riser=0.18):
    color(WOOD_COLOR)
    stairwell(rise, tread=tread, riser=riser)


@rule
def BasementAccess():
    translate(0, 0, -BASEMENT_H)
    split(x, STAIR_W >> StairFlight(BASEMENT_H + SLAB_H), flt() >> delete())


@rule
def RoomsOnly(clear_h):
    # Classrooms: wider spans, central corridor
    partition(
        wall=InteriorWall(max(0.5, clear_h)),
        room=color(ROOM_FLOOR_COLOR),
        thickness=0.14, margin=0.2, min_span=2.8, max_span=5.2,
        corridor=1.4, seed=7, door_width=1.0, door_height=2.2,
        lights=True, height=clear_h,
    )


@rule
def InteriorWall(h):
    color(INTERIOR_WALL_COLOR)
    openings(h)


@rule
def Basement():
    color(BASEMENT_WALL_COLOR)
    extrude(-BASEMENT_H, front >> BasementFacade(), side >> BasementFacade(),
            back >> BasementFacade(), bottom >> color(SLAB_COLOR), inheritMaterialSide=True)


@rule
def BasementFacade():
    split(y, flt(max(0.1, BASEMENT_H - 0.85)), 0.5 >> split(x, flt(0.6), repeat(flt(2.8) >> BasementWindowBay()), flt(0.6)), 0.35)


@rule
def BasementWindowBay():
    split(x, flt(0.4), 1.0 >> color("#12181c"), flt(0.4))


@rule
def SideFacade():
    split(
        y,
        PLINTH_H >> color(PLINTH_COLOR),
        GROUND_H >> split(x, flt(0.5), repeat(flt(2.8) >> TallWindowBay()), flt(0.5)),
        UPPER_H >> split(x, flt(0.5), repeat(flt(2.8) >> TallWindowBay()), flt(0.5)),
        CORNICE_H >> color(CORNICE_COLOR),
    )


@rule
def BackFacade():
    split(y, PLINTH_H >> color(PLINTH_COLOR), flt() >> split(x, flt(), 2.6 >> TallWindowBay(), flt()))


@rule
def TallWindowBay():
    # Classroom windows: taller glass bands
    split(x, flt(0.4), 1.5 >> split(y, 0.55, 2.1 >> color(WINDOW_COLOR), flt(0.4)), flt(0.4))


@rule
def RoofFace():
    color(ROOF_COLOR)


@rule
def SoffitFace():
    color(SOFFIT_COLOR)


@rule
def FasciaFace():
    color(FASCIA_COLOR)
