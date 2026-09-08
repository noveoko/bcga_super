from pro import *

__version__ = "1.0.0"
__description__ = "Hotel Victoria - 3-storey historic commercial building with attic mansard"
__tags__ = ["historic", "commercial", "hotel"]

# Overall footprint and height dimensions
BUILDING_WIDTH = 18.0
BUILDING_DEPTH = 13.0
WALL_H = 10.6

# Facade division heights
PLINTH_H = 0.5
GROUND_H = 3.6
BAND_H = 0.5
FIRST_H = 3.2
CORNICE_H = 0.4
ATTIC_H = 2.4

# Roof parameters
ROOF_PITCH = 35.0
ROOF_OVERHANG = 0.45

# Color palette
WALL_COLOR = param("#d8c8b0", group="Facade")
TRIM_COLOR = param("#efe8dc", group="Facade")
DARK_TRIM = param("#3a2f28", group="Facade")
PLINTH_COLOR = param("#685e57", group="Facade")
GLASS_COLOR = param("#20282e", group="Facade")
ROOF_COLOR = param("#42474a", group="Roof")
SOFFIT_COLOR = param("#c5bcaf", group="Roof")
FASCIA_COLOR = param("#362e28", group="Roof")
SLAB_COLOR = param("#9a9284", group="Interior")
SLAB_TOP_COLOR = param("#8a6a48", group="Interior")
BASEMENT_WALL_COLOR = param("#6b6255", group="Interior")
BASEMENT_WINDOW_COLOR = param("#12181c", group="Interior")
INTERIOR_WALL_COLOR = param("#d8d0c4", group="Interior")
ROOM_FLOOR_COLOR = param("#7a5a3a", group="Interior")
WOOD_COLOR = param("#5c4030", group="Interior")

HAS_BASEMENT = True
BASEMENT_H = 2.2
BASEMENT_ACCESS = "stairs"
SLAB_H = 0.18
STAIR_W = 1.05
# Ground, first-floor, attic, then the plate under the roof — aligned with
# StreetFacade()'s PLINTH/GROUND/BAND/FIRST/CORNICE/ATTIC bands.
SLAB_ELEVATIONS = [
    0.0,
    PLINTH_H + GROUND_H + BAND_H,
    PLINTH_H + GROUND_H + BAND_H + FIRST_H + CORNICE_H,
    WALL_H,
]


@rule
def Begin():
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()


@rule
def MainMass():
    copy(FloorSlabs())
    if HAS_BASEMENT:
        copy(Basement())
    color(WALL_COLOR)
    extrude(
        WALL_H,
        front >> StreetFacade(),
        side >> SideFacade(),
        back >> BackFacade(),
        top >> PitchedRoof(),
        inheritMaterialSide=True,
    )


@rule
def FloorSlabs():
    _well_up = True
    _well_down = BASEMENT_ACCESS is not None
    for i, elevation in enumerate(SLAB_ELEVATIONS[:-1]):
        if i == 0 and _well_down:
            opening = "well"
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
    split(
        x,
        STAIR_W >> StairFlight(clear_h + SLAB_H),
        flt() >> RoomsOnly(clear_h),
    )


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
        room=RoomFinish(),
        thickness=0.12,
        margin=0.18,
        min_span=2.0,
        max_span=4.5,
        corridor=1.15,
        seed=1,
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
        GROUND_H >> GroundStorefronts(),
        BAND_H >> CorniceBand(),
        FIRST_H >> FirstFloor(),
        CORNICE_H >> MainCornice(),
        ATTIC_H >> AtticFloor(),
    )


@rule
def Plinth():
    color(PLINTH_COLOR)


@rule
def GroundStorefronts():
    split(x, 0.5, repeat(flt(4.0) >> ShopBay()), 0.5)


@rule
def ShopBay():
    split(x, flt(0.4), 2.8 >> ShopFront(), flt(0.4))


@rule
def ShopFront():
    split(y, 0.4 >> Sill(), flt() >> GlassPane(), 0.7 >> TransomSign())


@rule
def TransomSign():
    color(DARK_TRIM)


@rule
def CorniceBand():
    color(TRIM_COLOR)


@rule
def FirstFloor():
    split(x, 0.5, repeat(flt(4.0) >> FirstFloorBay()), 0.5)


@rule
def FirstFloorBay():
    split(x, flt(0.6), 2.2 >> WindowPairGroup(), flt(0.6))


@rule
def WindowPairGroup():
    split(
        y,
        0.5 >> Sill(),
        flt() >> WindowPairSplit(),
        0.4 >> ArchHeader(),
    )


@rule
def WindowPairSplit():
    split(x, flt() >> GlassPane(), 0.2 >> WallTrim(), flt() >> GlassPane())


@rule
def ArchHeader():
    color(TRIM_COLOR)


@rule
def MainCornice():
    color(TRIM_COLOR)


@rule
def AtticFloor():
    color(DARK_TRIM)
    split(x, 0.4, repeat(flt(2.1) >> AtticBay()), 0.4)


@rule
def AtticBay():
    split(
        x,
        flt(0.3),
        1.2 >> split(y, 0.3, 1.5 >> GlassPane(), flt()),
        flt(0.3),
    )


@rule
def SideFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> SideWallBody(),
        CORNICE_H >> MainCornice(),
        ATTIC_H >> AtticSideWall(),
    )


@rule
def SideWallBody():
    split(
        y,
        flt(4.5) >> SideWindowGrid(),
        1.0 >> SideHotelSign(),
        flt(1.2) >> WallTrim(),
    )


@rule
def SideHotelSign():
    color(DARK_TRIM)


@rule
def SideWindowGrid():
    split(x, flt(), repeat(flt(3.2) >> SideWindowBay()), flt())


@rule
def SideWindowBay():
    split(
        x,
        flt(0.8),
        1.2 >> split(y, 0.8, 1.5 >> GlassPane(), flt()),
        flt(0.8),
    )


@rule
def AtticSideWall():
    color(DARK_TRIM)
    split(x, flt(), repeat(flt(2.5) >> AtticBay()), flt())


@rule
def BackFacade():
    SideFacade()


@rule
def GlassPane():
    color(GLASS_COLOR)


@rule
def WallTrim():
    color(TRIM_COLOR)


@rule
def Sill():
    color(TRIM_COLOR)


@rule
def PitchedRoof():
    copy(ChimneyAt(2.5, 0.0))
    hip_roof(
        ROOF_PITCH,
        ROOF_OVERHANG,
        face >> RoofFace(),
        soffit >> SoffitFace(),
        fascia >> FasciaFace(),
        fasciaSize=0.14,
    )


@rule
def ChimneyAt(dx, dy):
    rise = BUILDING_DEPTH / 2.0 * 0.700
    translate(dx, dy, rise)
    rectangle(0.9, 0.9, ChimneyStack())
    delete()


@rule
def ChimneyStack():
    color(PLINTH_COLOR)
    extrude(1.4)


@rule
def RoofFace():
    color(ROOF_COLOR)


@rule
def SoffitFace():
    color(SOFFIT_COLOR)


@rule
def FasciaFace():
    color(FASCIA_COLOR)