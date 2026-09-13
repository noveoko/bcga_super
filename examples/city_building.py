"""
Example BCGA rule file for use with city_builder.py.

Demonstrates density- *and* role-aware generation and the Phase 5
preferred pattern: read plot/block metadata with city_block() *inside*
Begin(), not at module import time. city_builder / GenerationSession set
cityBlock before each apply; downtown density approaches 1.0, edge
density approaches 0. generate_city_layout() also tags every block with a
"role" (see pro/city/layout.py's _assign_town_roles) -- "church"/
"ratusz"/"synagogue" for the civic core, "kamienica"/"cottage" for
ordinary blocks based on their own density -- which this file reads to
pick a genuinely different massing/material archetype per building,
not just a taller/shorter version of the same box. "plaza" blocks never
reach this file at all (city_builder.py's build_blocks() renders those
with build_plaza() instead).

When run standalone via generate.py (no cityBlock set), city_block()
falls back to a mid-density kamienica.
"""
from pro import *

__version__ = "2.0.0"
__description__ = (
    "Density- and role-aware city building: real per-floor windows, a plinth/cornice band, "
    "and a distinctly colored roof, with civic/kamienica/cottage archetypes instead of one "
    "box shape for the whole city"
)
__tags__ = ["city", "example"]

PLINTH_H = 0.4
CORNICE_H = 0.22


@rule
def Begin():
    # Preferred: resolve plot metadata at execute time (not import time).
    plot = city_block({"density": 0.5, "role": "kamienica"})
    # `plot.get("density") or 0.5` would be wrong here: density=0.0 (the
    # very edge of town, exactly where the starkest contrast should show
    # up) is falsy, so `or` would silently replace it with the 0.5
    # mid-town default and mute the edge-of-town look this file is
    # supposed to produce.
    rawDensity = plot.get("density")
    density = float(rawDensity) if rawDensity is not None else 0.5
    role = plot.get("role") or "kamienica"

    civic = role in ("church", "ratusz", "synagogue")
    cottage = role == "cottage"

    # Each archetype gets its own palette, storey height, and floor-count
    # range so it reads as a genuinely different *kind* of building, not
    # just a taller/shorter copy of the same box -- density still adds
    # jitter and a glassier/brickier lean within whichever archetype this
    # block got.
    if civic:
        facade = choice("#d9d2c3", "#c9c2b0", "#e2dccb", "#c8b89a", weights=[0.35, 0.3, 0.2, 0.15])
        floorH = 4.2
        floors = int(float(random(2, 4)))
        windowColor = choice("#233038", "#2c3a40", "#1c262c")
        trimColor = choice("#b8a888", "#a89878", "#c4b49a")
        roofColor = choice("#5a4638", "#4f5a48", "#6b5240")
        pitchChance = 0.85
        bayWidth, windowW, windowH = 3.0, 1.3, 2.0
    elif cottage:
        facade = choice(
            "#d4b483", "#c9a06a", "#b8895a", "#e2c4b6", "#c5d1b8",
            weights=[0.28, 0.24, 0.22, 0.14, 0.12],
        )
        floorH = 2.9
        floors = int(float(random(1, 3)))
        windowColor = choice("#2a3338", "#3a3328", "#243038")
        trimColor = choice("#8a7a64", "#7a6b56", "#6e6254")
        roofColor = choice("#9c3b28", "#8a3828", "#b5523a", "#7a3020")
        pitchChance = 0.9
        bayWidth, windowW, windowH = 2.2, 0.9, 1.15
    else:  # "kamienica" and anything else -- the generic mid-town building
        facade = choice(
            "#8fa8b8", "#b8895a", "#d9d2c3", "#c5d1b8", "#e6c36a", "#cfd6da",
            weights=[
                0.12 + 0.55 * density, 0.20 - 0.10 * density, 0.20 - 0.08 * density,
                0.16 - 0.10 * density, 0.16 - 0.12 * density, 0.16 - 0.15 * density,
            ],
        )
        floorH = 3.15
        # random()'s range itself scales with density (more floors possible
        # downtown), but the low end never collapses to a single fixed
        # value the way `3 + density * random(...)` did before -- even a
        # density=0 edge-of-town building still lands anywhere from 1 to 3
        # floors instead of always exactly one height.
        floors = int(float(random(1, 3 + round(density * 7))))
        windowColor = choice("#233038", "#2c3a40", "#1c262c")
        trimColor = choice("#d0c4b0", "#c4b49a", "#b8a888")
        roofColor = choice("#b5523a", "#9c3b28", "#c45c3e", "#a34430")
        pitchChance = 1.0 - 0.8 * density
        bayWidth, windowW, windowH = 2.6, 1.1, 1.45

    # Resolve every Choice right away so every face/floor of *this*
    # building agrees on the same facade/trim/window/roof color instead of
    # each side re-rolling its own (Choice.getValue() is one-shot-cached
    # per instance, but a fresh choice() call anywhere else would draw a
    # brand new value from the shared RNG stream).
    facadeColor = str(facade)
    windowColor = str(windowColor)
    trimColor = str(trimColor)
    roofColor = str(roofColor)
    height = PLINTH_H + floors * floorH + CORNICE_H

    color(facadeColor)
    # Build the roof from a COPY of this building's original, untouched
    # footprint (translated up to roof height) rather than chaining off
    # whatever's left of the wall extrude below: Extrude() only leaves a
    # usable "current shape" for further chaining when it has *no* parts
    # at all (see bpro/op_extrude.py) -- since this rule claims the
    # "side" faces for Facade(), state.shape is never reassigned to the
    # top cap, so anything called directly after extrude() here would
    # silently run against the pre-extrude ground-level footprint instead
    # of the real roof position. copy() sidesteps that entirely.
    copy(PlaceRoof(height, pitchChance, roofColor))
    extrude(
        height,
        side >> Facade(floorH, floors, bayWidth, windowW, windowH, facadeColor, windowColor, trimColor),
        inheritMaterialAll=False,
        inheritMaterialSide=True,
    )


@rule
def PlaceRoof(height, pitchChance, roofColor):
    translate(0, 0, height)
    chance(
        (pitchChance, PitchedRoof(roofColor)),
        (1 - pitchChance, FlatRoof(roofColor)),
    )


@rule
def Facade(floorH, floors, bayWidth, windowW, windowH, facadeColor, windowColor, trimColor):
    split(
        y,
        PLINTH_H >> Plinth(trimColor),
        repeat(flt(floorH) >> FloorBand(bayWidth, windowW, windowH, facadeColor, windowColor)),
        CORNICE_H >> Cornice(trimColor),
    )


@rule
def Plinth(trimColor):
    color(trimColor)


@rule
def Cornice(trimColor):
    color(trimColor)


@rule
def FloorBand(bayWidth, windowW, windowH, facadeColor, windowColor):
    color(facadeColor)
    # Plain floats here, not flt(0.4): a split() that also contains a
    # repeat(...) child needs its *other* children to be real fixed-size
    # values, not bare flt()/rel() Modifier wrappers -- a bare Modifier is
    # only a flag meant to be picked up via `size >> SomeRule()` (see
    # Plinth/Cornice above); left unattached next to a repeat(...) child
    # it gets executed directly and blows up (Modifier.execute() doesn't
    # take the ctx argument the repeat-aware split path passes). Compare
    # examples/polish_town_1927.py's GroundFloor()/UpperFloor(), which use
    # exactly this bare-plain-float-margin-around-repeat() pattern.
    split(x, 0.4, repeat(flt(bayWidth) >> WindowBay(windowW, windowH, windowColor)), 0.4)


@rule
def WindowBay(windowW, windowH, windowColor):
    split(
        x, flt(),
        windowW >> split(y, flt(0.35), windowH >> Window(windowColor), flt(0.3)),
        flt(),
    )


@rule
def Window(windowColor):
    # A handful of warm, "lit" windows scattered in among the normal dark
    # glass -- cheap (just a color swap, no extra geometry) but it breaks
    # up what would otherwise be a perfectly uniform grid of identical
    # dark rectangles across every floor of every building.
    color(choice(windowColor, "#e8c878", weights=[0.87, 0.13]))


@rule
def FlatRoof(roofColor):
    # A thin parapet lip -- rather than only coloring a flat 2D face
    # exactly coincident with the wall extrude's own (uncolored, unclaimed)
    # top cap below it, which would z-fight against it -- doubles as a
    # believable flat-roof parapet edge for free.
    color(roofColor)
    extrude(0.12)


@rule
def PitchedRoof(roofColor):
    # hip_roof()'s straight-skeleton algorithm isn't robust against every
    # irregular polygon (Voronoi cells can be quite skewed). Walls are
    # already built; fall back to a flat, but still roof-colored, top on
    # failure instead of silently inheriting the facade color.
    try:
        hip_roof(30 + random(-6, 12), 0.35, face >> RoofFace(roofColor))
    except Exception:
        color(roofColor)


@rule
def RoofFace(roofColor):
    color(roofColor)
