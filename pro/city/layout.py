"""
Organic city layout generator.

Produces a non-grid, "organically grown" city plan: building density and
block size taper outward from a city center, the way real cities that grew
incrementally around a core tend to look, rather than a uniform grid.

Approach: scatter seed points with a center-biased radial distribution
(dense near the center, sparse toward the edge), then compute their
Voronoi diagram. Each Voronoi cell becomes one city block; the shared
edges between neighboring cells become the road network. This gives
organic, irregular block shapes "for free" without needing to hand-roll
road-growth/branching logic, while guaranteeing valid (non-self-
intersecting, always-convex) block polygons.

DEPENDENCIES: numpy and scipy. Deliberately NOT imported by anything
bpy-dependent (bpro/, city_builder.py) -- this module is meant to run as a
separate, ordinary Python process to produce a JSON layout file, which
city_builder.py then reads inside Blender. This keeps Blender itself free
of any numpy/scipy installation requirement.
"""
import json
import math
import random as randomlib

import numpy as np
from scipy.spatial import Voronoi


def _sample_seed_points(numPoints, radius, centerBias, rng):
    """
    Samples numPoints points inside a disk of the given radius, biased
    toward the center. centerBias > 1 concentrates points more strongly
    near the center (denser "downtown"); centerBias == 1 would be roughly
    uniform-in-radius (already denser near center than uniform-in-area);
    centerBias == 0.5 gives uniform-in-area (no density gradient at all).
    """
    points = []
    for _ in range(numPoints):
        u = rng.random()
        r = radius * (u ** centerBias)
        theta = rng.random() * 2 * math.pi
        points.append((r * math.cos(theta), r * math.sin(theta)))
    return np.array(points)


def _boundary_polygon(radius, numSides=32):
    """A regular numSides-gon approximating a circular city boundary, CCW."""
    return [
        (radius * math.cos(2 * math.pi * i / numSides), radius * math.sin(2 * math.pi * i / numSides))
        for i in range(numSides)
    ]


def _clip_polygon(subject, clipPoly):
    """Sutherland-Hodgman polygon clipping. clipPoly must be convex and CCW."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def intersect(p1, p2, a, b):
        x1, y1 = p1; x2, y2 = p2; x3, y3 = a; x4, y4 = b
        d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(d) < 1e-12:
            return p2
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

    output = list(subject)
    n = len(clipPoly)
    for i in range(n):
        a, b = clipPoly[i], clipPoly[(i + 1) % n]
        inputList, output = output, []
        if not inputList:
            break
        for j in range(len(inputList)):
            cur, prev = inputList[j], inputList[j - 1]
            curIn, prevIn = inside(cur, a, b), inside(prev, a, b)
            if curIn:
                if not prevIn:
                    output.append(intersect(prev, cur, a, b))
                output.append(cur)
            elif prevIn:
                output.append(intersect(prev, cur, a, b))
    return output


def _finite_polygons(vor, extensionRadius):
    """
    Reconstructs scipy's (possibly infinite/unbounded) Voronoi regions as
    finite polygons, by extending unbounded ridges out to extensionRadius
    in the correct direction. Regions are then clipped to the actual city
    boundary separately (_clip_polygon), so extensionRadius just needs to
    be "far enough" that the extended edge is guaranteed to be past the
    real boundary -- it doesn't need to be exact.

    Returns a list (indexed the same as vor.points) of lists of (x, y)
    vertex coordinates, each already ordered counter-clockwise.
    """
    newVertices = vor.vertices.tolist()
    center = vor.points.mean(axis=0)

    allRidges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        allRidges.setdefault(p1, []).append((p2, v1, v2))
        allRidges.setdefault(p2, []).append((p1, v1, v2))

    polygons = []
    for p1, regionIndex in enumerate(vor.point_region):
        vertexIndices = vor.regions[regionIndex]

        if vertexIndices and all(v >= 0 for v in vertexIndices):
            region = list(vertexIndices)
        else:
            region = [v for v in vertexIndices if v >= 0]
            for p2, v1, v2 in allRidges.get(p1, []):
                if v2 < 0:
                    v1, v2 = v2, v1
                if v1 >= 0:
                    continue  # finite ridge, already included above
                t = vor.points[p2] - vor.points[p1]
                norm = np.linalg.norm(t)
                if norm < 1e-12:
                    continue
                t = t / norm
                n = np.array([-t[1], t[0]])
                midpoint = vor.points[[p1, p2]].mean(axis=0)
                direction = n if np.dot(midpoint - center, n) >= 0 else -n
                farPoint = vor.vertices[v2] + direction * extensionRadius
                region.append(len(newVertices))
                newVertices.append(farPoint.tolist())

        if len(region) < 3:
            polygons.append([])
            continue

        vs = np.array([newVertices[v] for v in region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
        orderedRegion = [region[i] for i in np.argsort(angles)]
        polygons.append([tuple(newVertices[v]) for v in orderedRegion])

    return polygons


def _polygon_area(points):
    """Shoelace formula."""
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _clip_segment(a, b, clipPoly):
    """
    Clips segment (a, b) against a convex, CCW polygon by intersecting the
    segment's valid parameter range [tmin, tmax] against each edge's
    half-plane (Liang-Barsky style, generalized from a box to an arbitrary
    convex polygon). Returns the clipped (a', b') segment, or None if the
    segment doesn't intersect the polygon at all.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    tmin, tmax = 0.0, 1.0
    n = len(clipPoly)
    for i in range(n):
        px, py = clipPoly[i]
        qx, qy = clipPoly[(i + 1) % n]
        edgeDx, edgeDy = qx - px, qy - py
        # inside-half-plane test, same convention as _clip_polygon's inside():
        # f(t) = edgeDx*(y(t)-py) - edgeDy*(x(t)-px), point is inside when f(t) >= 0
        f0 = edgeDx * (a[1] - py) - edgeDy * (a[0] - px)
        fSlope = edgeDx * dy - edgeDy * dx
        if abs(fSlope) < 1e-12:
            if f0 < 0:
                return None  # parallel to this edge and entirely outside it
            continue
        tBoundary = -f0 / fSlope
        if fSlope > 0:
            tmin = max(tmin, tBoundary)
        else:
            tmax = min(tmax, tBoundary)
        if tmin > tmax:
            return None
    return (a[0] + tmin * dx, a[1] + tmin * dy), (a[0] + tmax * dx, a[1] + tmax * dy)


def generate_city_layout(numBlocks=60, radius=200.0, centerBias=1.6, minBlockArea=25.0, seed=None):
    """
    Generates an organic city layout.

    Args:
        numBlocks: approximate number of city blocks to generate (some may
            be dropped afterward if degenerate/too small -- see minBlockArea).
        radius: city radius in meters.
        centerBias: >1 concentrates blocks more densely near the center
            (see _sample_seed_points). 1.6 gives a pronounced but not
            extreme downtown-to-suburb density gradient.
        minBlockArea: blocks smaller than this (m^2) after clipping are
            dropped as degenerate slivers (can happen right at the
            boundary edge).
        seed: random seed, for reproducible layouts.

    Returns a JSON-serializable dict:
        {
            "center": [0, 0], "radius": radius,
            "blocks": [
                {"id": int, "polygon": [[x,y], ...], "centroid": [x,y],
                 "area": float, "distance_from_center": float,
                 "density": float},  # 1.0 at center, ~0 at the edge
                ...
            ],
            "roads": [
                {"start": [x,y], "end": [x,y], "hierarchy": "primary"|"secondary"},
                ...
            ],
        }
    """
    rng = randomlib.Random(seed)
    npRng = np.random.default_rng(seed)

    points = _sample_seed_points(numBlocks, radius, centerBias, rng)
    if len(points) < 4:
        raise ValueError("generate_city_layout needs at least 4 blocks to compute a Voronoi diagram")

    vor = Voronoi(points)
    boundary = _boundary_polygon(radius)
    rawPolygons = _finite_polygons(vor, extensionRadius=radius * 10)

    blocks = []
    for i, poly in enumerate(rawPolygons):
        if not poly:
            continue
        clipped = _clip_polygon(poly, boundary)
        if len(clipped) < 3:
            continue
        area = _polygon_area(clipped)
        if area < minBlockArea:
            continue
        cx = sum(p[0] for p in clipped) / len(clipped)
        cy = sum(p[1] for p in clipped) / len(clipped)
        distanceFromCenter = math.hypot(cx, cy)
        density = max(0.0, 1.0 - distanceFromCenter / radius)
        blocks.append({
            "id": len(blocks),
            "polygon": [[round(x, 4), round(y, 4)] for x, y in clipped],
            "centroid": [round(cx, 4), round(cy, 4)],
            "area": round(area, 2),
            "distance_from_center": round(distanceFromCenter, 4),
            "density": round(density, 4),
        })

    # Roads: the unique shared edges between neighboring cells (their
    # ridges), deduped and clipped the same way as blocks. Ridges whose
    # midpoint is close to the center are marked "primary" (wider/more
    # important), others "secondary".
    roads = []
    seenSegments = set()
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        if v1 < 0 or v2 < 0:
            continue  # unbounded ridge; its finite portion is already implied by clipped block edges
        a, b = tuple(vor.vertices[v1]), tuple(vor.vertices[v2])
        clipped = _clip_segment(a, b, boundary)
        if clipped is None:
            continue
        a, b = clipped
        midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        key = tuple(sorted([tuple(round(c, 3) for c in a), tuple(round(c, 3) for c in b)]))
        if key in seenSegments:
            continue
        seenSegments.add(key)
        hierarchy = "primary" if math.hypot(*midpoint) < radius * 0.35 else "secondary"
        roads.append({
            "start": [round(a[0], 4), round(a[1], 4)],
            "end": [round(b[0], 4), round(b[1], 4)],
            "hierarchy": hierarchy,
        })

    _assign_town_roles(blocks)
    return {"center": [0, 0], "radius": radius, "blocks": blocks, "roads": roads}


def _assign_town_roles(blocks):
    """
    Tag civic landmarks the way a Magdeburg-plan Polish miasteczko is
    organized: a market square (rynek) at the center, church and town hall
    (ratusz) on it, a synagogue nearby, kamienice around the core, cottages
    toward the edge.
    """
    if not blocks:
        return
    ranked = sorted(blocks, key=lambda b: (b["distance_from_center"], -b["area"]))
    civic = [b for b in ranked if b["area"] >= 90]
    pool = civic if len(civic) >= 4 else ranked
    for block, role in zip(pool, ("plaza", "church", "ratusz", "synagogue")):
        block["role"] = role
    for block in blocks:
        if "role" in block:
            continue
        block["role"] = "kamienica" if block["density"] >= 0.38 else "cottage"


def _rynek_rect(width=64.0, depth=80.0):
    """Axis-aligned Magdeburg square centered on the origin: xmin, ymin, xmax, ymax."""
    return (-width / 2.0, -depth / 2.0, width / 2.0, depth / 2.0)


def _poly_overlaps_aabb(poly, xmin, ymin, xmax, ymax):
    px = [p[0] for p in poly]
    py = [p[1] for p in poly]
    return not (max(px) < xmin or min(px) > xmax or max(py) < ymin or min(py) > ymax)


def _clip_block_from_rynek(poly, xmin, ymin, xmax, ymax, radius):
    """
    Drop cells whose centroid is in the square. Cells that straddle it are
    cut to the half-plane of the nearest side, so the hole stays rectangular.
    """
    if len(poly) < 3:
        return None
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    if xmin < cx < xmax and ymin < cy < ymax:
        return None
    if not _poly_overlaps_aabb(poly, xmin, ymin, xmax, ymax):
        return poly
    R = radius * 4.0
    if cx <= xmin:
        clip = [(-R, -R), (xmin, -R), (xmin, R), (-R, R)]
    elif cx >= xmax:
        clip = [(xmax, -R), (R, -R), (R, R), (xmax, R)]
    elif cy <= ymin:
        clip = [(-R, -R), (R, -R), (R, ymin), (-R, ymin)]
    else:
        clip = [(-R, ymax), (R, ymax), (R, R), (-R, R)]
    return _clip_polygon(poly, clip)


def _touches_rynek(plot, xmin, ymin, xmax, ymax, tol=2.5):
    a, b = plot["polygon"][0], plot["polygon"][1]
    for p in (a, b):
        on_v = (abs(p[0] - xmin) < tol or abs(p[0] - xmax) < tol) and (ymin - tol <= p[1] <= ymax + tol)
        on_h = (abs(p[1] - ymin) < tol or abs(p[1] - ymax) < tol) and (xmin - tol <= p[0] <= xmax + tol)
        if on_v or on_h:
            return True
    return False


def _stamp_plot_type(plot, role, rng):
    plot["role"] = role
    if role == "church":
        plot.update(roof="gable", wall="plaster", frontage="civic", storeys=2)
    elif role == "ratusz":
        plot.update(roof="hip", wall="plaster", frontage="civic", storeys=3)
    elif role == "synagogue":
        plot.update(roof="hip", wall="brick", frontage="civic", storeys=2)
    elif role == "barn":
        plot.update(roof="gable", wall="wood", frontage="blank", storeys=1)
    elif role == "cottage":
        plot.update(
            roof=rng.choice(["gable", "gable", "halfhip"]),
            wall=rng.choice(["wood", "wood", "plaster"]),
            frontage="house",
            storeys=1,
        )
    elif role == "villa":
        plot.update(roof="hip", wall="plaster", frontage="house", storeys=2)
    elif role == "workshop":
        plot.update(roof="gable", wall="brick", frontage="shop", storeys=1)
    else:
        # kamienica
        plot.update(
            roof=rng.choice(["hip", "hip", "gable", "halfhip"]),
            wall=rng.choice(["plaster", "plaster", "plaster", "brick"]),
            frontage=plot.get("frontage") or "house",
            storeys=rng.choice([2, 2, 3]),
        )


def _assign_plot_types(plots, rynek, rng):
    xmin, ymin, xmax, ymax = rynek
    on_square = [p for p in plots if _touches_rynek(p, xmin, ymin, xmax, ymax)]
    on_square.sort(key=lambda p: -(p["width"] * p["depth"]))
    reserved = set()
    for role, plot in zip(("church", "ratusz", "synagogue"), on_square):
        if plot["width"] >= 8.0:
            _stamp_plot_type(plot, role, rng)
            reserved.add(id(plot))
            if role != "church":
                plot["frontage"] = "civic"

    radius_guess = 1.0
    if plots:
        radius_guess = max(math.hypot(*p["centroid"]) for p in plots) or 1.0

    for plot in plots:
        if id(plot) in reserved:
            continue
        dist = math.hypot(*plot["centroid"])
        on_sq = _touches_rynek(plot, xmin, ymin, xmax, ymax)
        u = rng.random()
        if on_sq:
            plot["frontage"] = "shop"
            _stamp_plot_type(plot, "kamienica", rng)
            plot["frontage"] = "shop"
            plot["storeys"] = rng.choice([2, 2, 3])
        elif dist < radius_guess * 0.45:
            role = "workshop" if u < 0.12 else "kamienica"
            _stamp_plot_type(plot, role, rng)
            if role == "kamienica" and u > 0.7:
                plot["frontage"] = "shop"
        elif dist < radius_guess * 0.75:
            if u < 0.15:
                _stamp_plot_type(plot, "workshop", rng)
            elif u < 0.28:
                _stamp_plot_type(plot, "cottage", rng)
            else:
                _stamp_plot_type(plot, "kamienica", rng)
                plot["storeys"] = 2
        else:
            if u < 0.12:
                _stamp_plot_type(plot, "barn", rng)
            elif u < 0.18:
                _stamp_plot_type(plot, "villa", rng)
            else:
                _stamp_plot_type(plot, "cottage", rng)


def generate_polish_town_layout(numBlocks=48, radius=160.0, seed=1927, **kwargs):
    """
    Magdeburg-plan miasteczko: rectangular rynek, Voronoi streets around it,
    human-scale rectangular plots along every street edge.
    """
    from .parcels import parcel_block

    kwargs.setdefault("centerBias", 1.15)
    kwargs.setdefault("minBlockArea", 60.0)
    rng = randomlib.Random(seed)
    layout = generate_city_layout(
        numBlocks=numBlocks, radius=radius, seed=seed, **kwargs
    )

    xmin, ymin, xmax, ymax = _rynek_rect()
    kept = []
    for block in layout["blocks"]:
        clipped = _clip_block_from_rynek(block["polygon"], xmin, ymin, xmax, ymax, radius)
        if not clipped or len(clipped) < 3:
            continue
        area = _polygon_area(clipped)
        if area < 80.0:
            continue
        cx = sum(p[0] for p in clipped) / len(clipped)
        cy = sum(p[1] for p in clipped) / len(clipped)
        block = dict(block)
        block["polygon"] = [[round(x, 4), round(y, 4)] for x, y in clipped]
        block["centroid"] = [round(cx, 4), round(cy, 4)]
        block["area"] = round(area, 2)
        block["distance_from_center"] = round(math.hypot(cx, cy), 4)
        block["density"] = round(max(0.0, 1.0 - math.hypot(cx, cy) / radius), 4)
        block["role"] = "block"
        kept.append(block)

    plaza_poly = [
        [xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax],
    ]
    plaza = {
        "id": 0,
        "polygon": plaza_poly,
        "centroid": [0.0, 0.0],
        "area": round((xmax - xmin) * (ymax - ymin), 2),
        "distance_from_center": 0.0,
        "density": 1.0,
        "role": "plaza",
    }
    for i, block in enumerate(kept):
        block["id"] = i + 1
    layout["blocks"] = [plaza] + kept

    # cobbled ring around the square
    corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        layout["roads"].append({
            "start": [round(a[0], 4), round(a[1], 4)],
            "end": [round(b[0], 4), round(b[1], 4)],
            "hierarchy": "primary",
        })

    plots = []
    for block in kept:
        for plot in parcel_block(
            [tuple(p) for p in block["polygon"]],
            density=block["density"],
            rng=rng,
        ):
            plot["block_id"] = block["id"]
            plot["density"] = block["density"]
            plots.append(plot)
    for i, plot in enumerate(plots):
        plot["id"] = i
    _assign_plot_types(plots, (xmin, ymin, xmax, ymax), rng)

    layout["plots"] = plots
    layout["rynek"] = [xmin, ymin, xmax, ymax]
    layout["style"] = "polish_town_1927"
    return layout


def save_city_layout(layout, path):
    with open(path, "w") as f:
        json.dump(layout, f, indent=2)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate an organic city layout as JSON")
    parser.add_argument("--output", required=True)
    parser.add_argument("--blocks", type=int, default=60)
    parser.add_argument("--radius", type=float, default=200.0)
    parser.add_argument("--center-bias", type=float, default=1.6)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--style", choices=["organic", "polish"], default="organic",
        help="polish: small-town 1927 defaults (milder density, civic landmarks)",
    )
    args = parser.parse_args()

    if args.style == "polish":
        layout = generate_polish_town_layout(
            numBlocks=args.blocks, radius=args.radius, seed=args.seed if args.seed is not None else 1927,
            centerBias=args.center_bias if args.center_bias != 1.6 else 1.25,
        )
    else:
        layout = generate_city_layout(
            numBlocks=args.blocks, radius=args.radius,
            centerBias=args.center_bias, seed=args.seed,
        )
    save_city_layout(layout, args.output)
    extra = ""
    if layout.get("plots"):
        extra = " / %d plots" % len(layout["plots"])
    print("Wrote %d blocks%s and %d road segments to %s" % (
        len(layout["blocks"]), extra, len(layout["roads"]), args.output))
