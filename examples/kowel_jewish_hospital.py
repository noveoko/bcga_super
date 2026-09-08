"""
Kowel Jewish Hospital (Еврейская Больница), circa 1910s.

Translated from buildings_as_code/5mror_as_code.txt into this repo's BCGA
DSL. Postcard: plastered one-storey hip-roofed ward with a 2-3-2 window
rhythm, pilasters, and an attached unplastered brick wing on the right.
"""
from pro import *

__version__ = "1.0.0"
__description__ = "Kowel Jewish Hospital: plastered hip-roof ward + brick wing"
__tags__ = ["kowel", "hospital", "historic"]

BUILDING_WIDTH = 22.0
BUILDING_DEPTH = 11.0
BUILDING_HEIGHT = 4.2
ROOF_PITCH = 30.0
ROOF_OVERHANG = 0.5
FASCIA_DEPTH = 0.14

WING_WIDTH = 8.0
WING_DEPTH = 9.5
WING_HEIGHT = 3.6
# Wing center relative to the main mass (centered at origin): overlap 1 m
# on the +x gable, front set back 1.5 m.
WING_DX = BUILDING_WIDTH / 2.0 - 1.0 + WING_WIDTH / 2.0
WING_DY = -BUILDING_DEPTH / 2.0 + 1.5 + WING_DEPTH / 2.0

PLINTH_H = 0.6
CORNICE_H = 0.6
WALL_H = BUILDING_HEIGHT - PLINTH_H - CORNICE_H

PLASTER = param("#efe8dc", group="Facade")
PLINTH_COLOR = param("#e2d8c4", group="Facade")
BRICK = param("#9a4a3a", group="Facade")
ROOF_METAL = param("#4a5c48", group="Roof")
SOFFIT_COLOR = param("#d8cfbc", group="Roof")
FASCIA_COLOR = param("#3d3328", group="Roof")
WOOD_TRIM = param("#f4eee4", group="Facade")
GLASS = param("#2c3336", group="Facade")
SIGN_COLOR = param("#2a2420", group="Facade")


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


@rule
def MainMass():
    color(PLASTER)
    extrude(
        BUILDING_HEIGHT,
        front >> MainFacade(),
        back >> BackFacade(),
        side >> SideFacade(),
        top >> MainRoof(),
        bottom >> Foundation(),
        inheritMaterialSide=True,
    )


@rule
def WingMass():
    color(BRICK)
    extrude(
        WING_HEIGHT,
        front >> WingFacade(),
        back >> WingSide(),
        side >> WingSide(),
        top >> WingRoof(),
        bottom >> Foundation(),
        inheritMaterialSide=True,
    )


@rule
def MainRoof():
    copy(ChimneyAt(-6.0, 0.0))
    copy(ChimneyAt(6.0, 0.0))
    hip_roof(
        ROOF_PITCH, ROOF_OVERHANG,
        face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
        fasciaSize=FASCIA_DEPTH,
    )


@rule
def WingRoof():
    copy(ChimneyAt(2.0, 0.0, WING_DEPTH / 2.0 * 0.466))
    hip_roof(
        ROOF_PITCH - 5.0, 0.4,
        face >> RoofFace(), soffit >> SoffitFace(), fascia >> FasciaFace(),
        fasciaSize=FASCIA_DEPTH,
    )


@rule
def ChimneyAt(dx, dy, rise=None):
    if rise is None:
        rise = BUILDING_DEPTH / 2.0 * 0.577
    translate(dx, dy, rise)
    rectangle(0.9, 0.9, ChimneyStack())
    delete()


@rule
def ChimneyStack():
    color(PLASTER)
    extrude(1.6, top >> ChimneyCap(), inheritMaterialSide=True)


@rule
def ChimneyCap():
    color(PLASTER)
    extrude(0.15)


@rule
def RoofFace():
    color(ROOF_METAL)


@rule
def SoffitFace():
    color(SOFFIT_COLOR)


@rule
def FasciaFace():
    color(FASCIA_COLOR)


@rule
def Foundation():
    color(PLINTH_COLOR)


@rule
def MainFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt(WALL_H) >> MainWallRhythm(),
        CORNICE_H >> Cornice(),
    )


@rule
def MainWallRhythm():
    # 2-3-2 bays with corner and intermediate pilasters (spec sums to 18 m;
    # floating bays absorb the remaining 4 m of the 22 m frontage).
    split(
        x,
        0.5 >> CornerPilaster(),
        flt(4.5) >> WindowBayDouble(),
        0.6 >> IntermediatePilaster(),
        flt(6.8) >> CenterBayTriple(),
        0.6 >> IntermediatePilaster(),
        flt(4.5) >> WindowBayDouble(),
        0.5 >> CornerPilaster(),
    )


@rule
def BackFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> split(x, flt(), 1.2 >> WindowUnit(), flt(), 1.2 >> WindowUnit(), flt(), 1.2 >> WindowUnit(), flt()),
        CORNICE_H >> Cornice(),
    )


@rule
def SideFacade():
    split(
        y,
        PLINTH_H >> Plinth(),
        flt() >> split(x, flt(), 1.2 >> WindowUnit(), flt(), 1.2 >> WindowUnit(), flt()),
        CORNICE_H >> Cornice(),
    )


@rule
def WingFacade():
    color(BRICK)
    split(
        y,
        0.5 >> Plinth(),
        flt() >> split(x, flt() >> WindowAssembly(), flt() >> WindowAssembly()),
        0.4 >> Cornice(),
    )


@rule
def WingSide():
    color(BRICK)
    split(
        y,
        0.5 >> Plinth(),
        flt() >> split(x, flt(), 1.2 >> WindowUnit(), flt()),
        0.4 >> Cornice(),
    )


@rule
def Plinth():
    color(PLINTH_COLOR)
    extrude(0.08)


@rule
def Cornice():
    color(PLASTER)
    extrude(0.12)


@rule
def CornerPilaster():
    color(PLASTER)
    extrude(0.05)


@rule
def IntermediatePilaster():
    color(PLASTER)
    split(y, 0.3, flt() >> PilasterPanel(), 0.3)


@rule
def PilasterPanel():
    color(PLASTER)
    extrude(0.05)


@rule
def WindowBayDouble():
    split(x, flt() >> WindowAssembly(), flt() >> WindowAssembly())


@rule
def CenterBayTriple():
    split(
        x,
        flt() >> WindowAssembly(),
        flt(1.3) >> CenterWindowWithSign(),
        flt() >> WindowAssembly(),
    )


@rule
def CenterWindowWithSign():
    split(
        y,
        flt(),
        0.12 >> WindowSill(),
        1.55 >> WindowRecess(),
        0.12 >> WindowArchitrave(),
        0.45 >> SignboardHeader(),
        flt(),
    )


@rule
def SignboardHeader():
    color(SIGN_COLOR)
    extrude(0.06)


@rule
def WindowAssembly():
    split(x, flt(0.4), 1.2 >> WindowUnit(), flt(0.4))


@rule
def WindowUnit():
    split(
        y,
        flt(),
        0.12 >> WindowSill(),
        1.8 >> WindowRecess(),
        0.12 >> WindowArchitrave(),
        flt(),
    )


@rule
def WindowSill():
    color(PLASTER)
    extrude(0.10)


@rule
def WindowArchitrave():
    color(WOOD_TRIM)
    extrude(0.04)


@rule
def WindowRecess():
    split(
        y,
        flt(2.0) >> split(x, flt() >> GlassPane(), 0.04 >> Mullion(), flt() >> GlassPane()),
        0.05 >> Mullion(),
        flt(1.0) >> GlassPane(),
    )


@rule
def GlassPane():
    color(GLASS)


@rule
def Mullion():
    color(WOOD_TRIM)
