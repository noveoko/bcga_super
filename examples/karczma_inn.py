"""
Karczma (inn / tavern) — Second Polish Republic roadside inn, ~1927.

Dark timber façade, shopfront common room, rooms upstairs, beer cellar.
Run standalone:
  blender --background --factory-startup --python generate.py -- \\
      --rule examples/karczma_inn.py --output out/karczma_inn.blend
"""
from pro import *

__version__ = "1.0.0"
__description__ = "1927 Polish karczma (inn/tavern) with shopfront and cellar"
__tags__ = ["poland", "1927", "inn", "commercial"]

BUILDING_WIDTH = 12.0
BUILDING_DEPTH = 10.0
PLINTH_H = 0.4
GROUND_H = 3.55
UPPER_H = 3.1
CORNICE_H = 0.25
WALL_H = PLINTH_H + GROUND_H + UPPER_H + CORNICE_H

ROOF_PITCH = 42.0
ROOF_OVERHANG = 0.55
FASCIA_DEPTH = 0.15

FACADE_COLOR = param("#6e4a30", group="Facade")
PLINTH_COLOR = param("#4a3a28", group="Facade")
WOOD_COLOR = param("#3a2818", group="Facade")
WINDOW_COLOR = param("#1e1812", group="Facade")
SHOP_GLASS = param("#2a3330", group="Facade")
CORNICE_COLOR = param("#c4b49a", group="Facade")
ROOF_COLOR = param("#5a3a28", group="Roof")
SOFFIT_COLOR = param("#d8cfbc", group="Roof")
FASCIA_COLOR = param("#3a2818", group="Roof")
SLAB_COLOR = param("#9a9284", group="Interior")
SLAB_TOP_COLOR = param("#6e4e32", group="Interior")
BASEMENT_WALL_COLOR = param("#5e564a", group="Interior")
INTERIOR_WALL_COLOR = param("#cfc6b8", group="Interior")
ROOM_FLOOR_COLOR = param("#5c3e28", group="Interior")

HAS_BASEMENT = True
BASEMENT_H = 2.3
BASEMENT_ACCESS = "stairs"
SLAB_H = 0.18
STAIR_W = 1.05
DOOR_H = 2.25
WALL_MARGIN = 0.18
SLAB_ELEVATIONS = [0.0, PLINTH_H + GROUND_H, WALL_H]


@rule
def Begin():
    # city_builder already stamped a street-aligned plot footprint.
    if city_block():
        MainMass()
        return
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
    shape.openings = [Opening(offset=0.45, width=1.2, height=DOOR_H, sill_height=0.0)]
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
    partition(
        wall=InteriorWall(max(0.5, clear_h)),
        room=color(ROOM_FLOOR_COLOR),
        thickness=0.12, margin=0.18, min_span=2.2, max_span=4.2,
        corridor=1.2, seed=42, door_width=0.95, door_height=2.1,
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
    split(y, flt(max(0.1, BASEMENT_H - 0.85)), 0.5 >> split(x, flt(0.6), repeat(flt(2.6) >> BasementWindowBay()), flt(0.6)), 0.35)


@rule
def BasementWindowBay():
    split(x, flt(0.4), 0.9 >> color("#12181c"), flt(0.4))


@rule
def SideFacade():
    split(y, PLINTH_H >> color(PLINTH_COLOR), GROUND_H >> split(x, flt(), 2.4 >> WindowBay(), flt()),
          UPPER_H >> split(x, flt(), 2.4 >> WindowBay(), flt()), CORNICE_H >> color(CORNICE_COLOR))


@rule
def BackFacade():
    split(y, PLINTH_H >> color(PLINTH_COLOR), flt() >> split(x, flt(), 2.4 >> WindowBay(), flt()))


@rule
def WindowBay():
    split(x, flt(0.55), 1.2 >> split(y, 0.7, 1.55 >> color(WINDOW_COLOR), flt(0.55)), flt(0.55))


@rule
def RoofFace():
    color(ROOF_COLOR)


@rule
def SoffitFace():
    color(SOFFIT_COLOR)


@rule
def FasciaFace():
    color(FASCIA_COLOR)
