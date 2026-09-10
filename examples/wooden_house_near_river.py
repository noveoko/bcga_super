__version__ = "1.0.0"
__description__ = "Wooden historic cottage with raised plinth and side dormer"
__tags__ = ["historic", "wooden", "cottage"]

from pro import *

BUILDING_WIDTH = 8.0
BUILDING_DEPTH = 7.0
WALL_H = 3.5
PLINTH_H = 1.6
CORNICE_H = 0.2
ROOF_PITCH = 38.0
ROOF_OVERHANG = 0.6

# Wing (Deck/Porch on the left)
DECK_WIDTH = 2.5
DECK_DEPTH = 7.5
DECK_DX = -(BUILDING_WIDTH / 2.0) - (DECK_WIDTH / 2.0) + 0.2
DECK_DY = 0.2

# Interior setup
HAS_BASEMENT = True
BASEMENT_H = 2.0
BASEMENT_ACCESS = "ladder"
SLAB_H = 0.18
LADDER_W, LADDER_D = 0.65, 0.95
STAIR_W = 1.05
SLAB_ELEVATIONS = [0.0, PLINTH_H, WALL_H] 

# Colors
WOOD_FACADE = param("#4a3d35", group="Facade")
WOOD_DARK = param("#2a201b", group="Facade")
ROOF_COLOR = param("#d9dadb", group="Roof") # Snow covered
SOFFIT_COLOR = param("#362b25", group="Roof")
FASCIA_COLOR = param("#2a201b", group="Roof")
GLASS = param("#111517", group="Facade")
SLAB_COLOR = param("#9a9284", group="Interior")
SLAB_TOP_COLOR = param("#8a6a48", group="Interior")
BASEMENT_WALL_COLOR = param("#6b6255", group="Interior")
BASEMENT_WINDOW_COLOR = param("#12181c", group="Interior")
INTERIOR_WALL_COLOR = param("#d8d0c4", group="Interior")
ROOM_FLOOR_COLOR = param("#5c4030", group="Interior")
WOOD_COLOR = param("#5c4030", group="Interior")


@rule
def Begin():
    copy(PlaceDeck())
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()

@rule
def PlaceDeck():
    translate(DECK_DX, DECK_DY, 0)
    rectangle(DECK_WIDTH, DECK_DEPTH, DeckMass())
    delete()

@rule
def DeckMass():
    # Only a ground slab and raised plinth structure
    color(WOOD_DARK)
    extrude(
        PLINTH_H, 
        front >> Plinth(), 
        side >> Plinth(), 
        back >> Plinth(), 
        top >> DeckFloor(), 
        inheritMaterialSide=True
    )

@rule
def DeckFloor():
    color(WOOD_FACADE)

@rule
def MainMass():
    copy(FloorSlabs())
    if HAS_BASEMENT:
        copy(Basement())
    
    color(WOOD_FACADE)
    extrude(
        WALL_H,
        front >> GenericFacade(),
        side >> SideFacade(),
        back >> GenericFacade(),
        top >> PitchedRoof(),
        inheritMaterialSide=True,
    )

@rule
def GenericFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> WallSurface(),
        CORNICE_H >> Cornice(),
    )

@rule
def SideFacade():
    # Visible facade with window and vent
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> split(x, flt(), 1.2 >> Window(), 0.5 >> VentSpace(), flt(0.5)),
        CORNICE_H >> Cornice(),
    )

@rule
def VentSpace():
    split(y, flt(), 0.3 >> color(GLASS), flt(1.0))

@rule
def WallSurface():
    color(WOOD_FACADE)

@rule
def Window():
    split(y, 0.4, 1.4 >> split(x, 0.1, flt() >> Pane(), 0.1, flt() >> Pane(), 0.1), flt())

@rule
def Pane():
    color(GLASS)

@rule
def Plinth():
    color(WOOD_DARK)

@rule
def Cornice():
    color(WOOD_DARK)

@rule
def PitchedRoof():
    copy(ChimneyAt(-1.5, 1.0, 0.6))
    copy(ChimneyAt(0.5, -0.5, 0.4))
    copy(DormerAt(-3.0, 0.0))
    hip_roof(
        ROOF_PITCH, ROOF_OVERHANG,
        face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
        fasciaSize=0.18,
    )

@rule
def ChimneyAt(dx, dy, size):
    rise = BUILDING_DEPTH / 2.0 * 0.781 # tan(38 deg)
    translate(dx, dy, rise)
    rectangle(size, size, ChimneyStack())
    delete()

@rule
def ChimneyStack():
    color(WOOD_DARK)
    extrude(1.8)

@rule
def DormerAt(dx, dy):
    rise = BUILDING_DEPTH / 2.0 * 0.781
    translate(dx, dy, rise - 1.2) 
    rectangle(1.2, 1.8, DormerMass())
    delete()

@rule
def DormerMass():
    color(WOOD_FACADE)
    extrude(1.5, top >> RoofFace(), inheritMaterialSide=True)

@rule
def RoofFace():
    color(ROOF_COLOR)

@rule
def SoffitFace():
    color(SOFFIT_COLOR)

@rule
def FasciaFace():
    color(FASCIA_COLOR)

# --- Mandatory Interiors ---

@rule
def FloorSlabs():
    _well_down = BASEMENT_ACCESS is not None
    for i, elevation in enumerate(SLAB_ELEVATIONS[:-1]):
        if i == 0 and _well_down:
            opening = "hatch"
        else:
            opening = None
        copy(SlabAt(elevation, opening=opening))
        clear_h = SLAB_ELEVATIONS[i + 1] - elevation - SLAB_H
        copy(InteriorAt(elevation + SLAB_H, clear_h))
    copy(SlabAt(SLAB_ELEVATIONS[-1], opening=None))
    if _well_down:
        copy(BasementAccess())

@rule
def SlabAt(elevation, opening=None):
    translate(0, 0, elevation)
    if opening == "hatch":
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
    if BASEMENT_ACCESS == "ladder" and elevation < SLAB_ELEVATIONS[1]:
        split(
            x, 
            LADDER_W >> split(y, LADDER_D >> delete(), flt() >> RoomsOnly(clear_h)),
            flt() >> RoomsOnly(clear_h)
        )
    else:
        RoomsOnly(clear_h)

@rule
def BasementAccess():
    translate(0, 0, -BASEMENT_H)
    rise = BASEMENT_H + SLAB_H
    split(
        x, 
        LADDER_W >> split(y, LADDER_D >> StairFlight(rise, tread=0.10, riser=0.28), flt() >> delete()), 
        flt() >> delete()
    )

@rule
def StairFlight(rise, tread=0.27, riser=0.18):
    color(WOOD_COLOR)
    stairwell(rise, tread=tread, riser=riser)

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
    color(BASEMENT_WALL_COLOR)
    extrude(
        -BASEMENT_H, 
        front >> BasementFacade(), side >> BasementFacade(),
        back >> BasementFacade(), bottom >> BasementFloor(), 
        inheritMaterialSide=True
    )

@rule
def BasementFacade():
    split(
        y, 
        flt(max(0.1, BASEMENT_H - 0.85)),
        0.5 >> split(x, flt(0.6), repeat(flt(2.6) >> BasementWindow()), flt(0.6)), 
        0.35
    )

@rule
def BasementWindow():
    color(BASEMENT_WINDOW_COLOR)

@rule
def BasementFloor():
    color(SLAB_COLOR)