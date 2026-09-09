"""
Example BCGA rule file for use with city_builder.py.

Demonstrates density-aware generation and the Phase 5 preferred pattern:
read plot/block metadata with city_block() *inside* Begin(), not at module
import time. city_builder / GenerationSession set cityBlock before each
apply; downtown density approaches 1.0, edge density approaches 0.

When run standalone via generate.py (no cityBlock set), city_block() falls
back to density 0.5.
"""
from pro import *

__version__ = "1.1.0"
__description__ = "Density-aware city building: taller/glassier downtown, shorter/brick-ier suburban"
__tags__ = ["city", "example"]


@rule
def Begin():
    # Preferred: resolve plot metadata at execute time (not import time).
    plot = city_block({"density": 0.5})
    density = float(plot.get("density") or 0.5)

    facade = choice(
        "#8fa8b8",  # glass blue-grey
        "#b8895a",  # warm brick
        "#d9d2c3",  # painted stucco
        weights=[0.15 + 0.7 * density, 0.5 - 0.35 * density, 0.35 - 0.35 * density],
    )
    # height grows with density, with random jitter so similar-density blocks vary
    height = round(3 + density * float(random(18, 32)), 1)

    color(facade)
    extrude(height)
    # taller downtown → more flat roofs; suburban → more pitched
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
    # irregular polygon. Walls are already built; fall back to flat on failure.
    # Second positional value is eave overhang (meters).
    try:
        hip_roof(30 + random(-5, 5), 0.35)
    except Exception:
        pass
