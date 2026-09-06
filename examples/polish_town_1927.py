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
elif role == "barn":
    ROOF_COLOR = param(choice("#6b3d32", "#7a4a32"), group="Roof")
    ROOF_PITCH = param(round(pyrandom.uniform(36, 44), 1), group="Roof")
else:
    ROOF_COLOR = param(choice("#b5523a", "#9c3b28", "#c45c3e", "#a34430"), group="Roof")
    ROOF_PITCH = param(round(pyrandom.uniform(34, 44), 1), group="Roof")

WINDOW_COLOR = param(choice("#2a3338", "#3a3328", "#243038"), group="Facade")
SHOP_GLASS = param("#4a5a62", group="Facade")
PLINTH_COLOR = param(choice("#7a6b56", "#6e6254", "#8a7a64"), group="Facade")
WOOD_COLOR = param(choice("#5c4030", "#4a3224", "#6b4a32"), group="Facade")
CORNICE_COLOR = param(choice("#d0c4b0", "#c4b49a", "#b8a888"), group="Facade")


@rule
def Begin():
    color(FACADE_COLOR)
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
    pitch = float(ROOF_PITCH)
    if roof_kind == "gable":
        gable_roof(pitch, face >> RoofFace())
    elif roof_kind == "halfhip":
        hip_roof(pitch, 90, pitch, 58, face >> RoofFace())
    else:
        hip_roof(pitch, face >> RoofFace())


@rule
def RoofFace():
    color(ROOF_COLOR)
