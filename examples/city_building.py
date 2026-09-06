"""
Example BCGA rule file for use with city_builder.py.

Demonstrates density-aware generation: city_builder.py sets
pro.context.cityBlock to the current block's layout data (polygon,
centroid, distance_from_center, density -- 1.0 near downtown, tapering to
0 at the city edge) before generating each block. This rule file reads
that to make downtown blocks taller and glassier, and suburban blocks
shorter and brick-ier, using choice()/chance()/switch() for the actual
variety on top of that gradient.

When run standalone via generate.py instead of city_builder.py (no
cityBlock set), it falls back to a mid-range density of 0.5.
"""
import random as pyrandom

import pro
from pro import *

__version__ = "1.0.0"
__description__ = "Density-aware city building: taller/glassier downtown, shorter/brick-ier suburban"
__tags__ = ["city", "example"]

block = context.cityBlock or {"density": 0.5}
density = block["density"]

# height grows with density, with random jitter so a run of similar-density
# blocks still looks varied rather than uniform
BASE_HEIGHT = param(
    round(3 + density * pyrandom.uniform(18, 32), 1),
    group="Massing", unit="m", min=3, max=45,
)

# denser/downtown blocks lean glass/modern; suburban blocks lean brick/painted
FACADE_COLOR = param(
    choice(
        "#8fa8b8",  # glass blue-grey
        "#b8895a",  # warm brick
        "#d9d2c3",  # painted stucco
        weights=[0.15 + 0.7 * density, 0.5 - 0.35 * density, 0.35 - 0.35 * density],
    ),
    group="Facade",
)


@rule
def Begin():
    color(FACADE_COLOR)
    # Some highly irregular organic block shapes (very short edges from
    # Voronoi clipping, near-duplicate vertices, etc.) can trip bmesh's
    # bevel operator here. Corner rounding is cosmetic -- better to skip
    # it on a problem block than lose the whole building over it.
    extrude(BASE_HEIGHT)
    # taller downtown buildings more often get a flat roof (cheaper to
    # build tall); shorter suburban buildings more often get a pitched
    # gable roof -- weighted by density in the opposite direction
    chance(
        (density, FlatRoof()),
        (1 - density, PitchedRoof()),
    )


@rule
def FlatRoof():
    pass  # flat top, nothing further to add


@rule
def PitchedRoof():
    # hip_roof()'s straight-skeleton algorithm isn't robust against every
    # possible irregular polygon shape (very acute angles, near-duplicate
    # vertices from Voronoi clipping, etc. can trip it up). Since the
    # walls have already been built successfully by this point, fall back
    # to a flat top on failure rather than losing the whole building.
    try:
        hip_roof(30 + pyrandom.uniform(-5, 5))
    except Exception:
        pass
