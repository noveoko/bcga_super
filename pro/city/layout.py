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

try:
    from .terrain import load_terrain
except ImportError:  # python pro/city/layout.py (script, not package)
    from terrain import load_terrain


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


def _halfplane_quad(point, normal, size=1e5):
    """
    A large convex CCW quad approximating the half-plane
    {p : dot(p - point, normal) >= 0}, for use as a Sutherland-Hodgman
    clip polygon (see _clip_polygon). `perp` is `normal` rotated -90 deg,
    chosen so (perp, normal) is a right-handed basis -- this is what makes
    the returned quad wind CCW, which _clip_polygon's inside() test requires.
    """
    perp = (normal[1], -normal[0])
    a = (point[0] - perp[0] * size, point[1] - perp[1] * size)
    b = (point[0] + perp[0] * size, point[1] + perp[1] * size)
    c = (b[0] + normal[0] * size, b[1] + normal[1] * size)
    d = (a[0] + normal[0] * size, a[1] + normal[1] * size)
    return [a, b, c, d]


def _longest_edge_axis(poly):
    """Returns (length, unit_direction, midpoint) of a convex polygon's longest edge."""
    n = len(poly)
    bestLen, bestDir, bestMid = -1.0, (1.0, 0.0), (0.0, 0.0)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length > bestLen:
            bestLen = length
            bestDir = (dx / length, dy / length) if length > 1e-9 else (1.0, 0.0)
            bestMid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    return bestLen, bestDir, bestMid


def _subdivide_block(poly, minLen, maxLen, rng, terrain=None, depth=0, maxDepth=8):
    """
    Recursive block subdivision: real street networks are cut into blocks
    by repeatedly bisecting a superblock until each piece is within a
    target length range (a standard walkable-block guideline is roughly
    80-200m per side), rather than emerging from an unrelated point
    process. Splits perpendicular to the polygon's longest edge, so a
    long thin superblock gets cut the "short way" like an actual land
    survey would. When a terrain model is supplied, the split axis is
    nudged to run along the local contour (perpendicular to the slope
    gradient) so the resulting street runs roughly level rather than
    straight up a hillside.
    """
    length, edgeDir, mid = _longest_edge_axis(poly)
    if length <= maxLen or depth >= maxDepth:
        return [poly]

    if terrain is not None:
        h = max(1.0, length * 0.05)
        dzdx = (terrain.elevation(mid[0] + h, mid[1]) - terrain.elevation(mid[0] - h, mid[1])) / (2 * h)
        dzdy = (terrain.elevation(mid[0], mid[1] + h) - terrain.elevation(mid[0], mid[1] - h)) / (2 * h)
        gradLen = math.hypot(dzdx, dzdy)
        if gradLen > 1e-6:
            # contour direction = gradient rotated 90 degrees (perpendicular
            # to steepest ascent); blend it with the longest-edge direction
            # so streets still roughly respect the block's own geometry
            contourDir = (-dzdy / gradLen, dzdx / gradLen)
            blended = (edgeDir[0] * 0.4 + contourDir[0] * 0.6, edgeDir[1] * 0.4 + contourDir[1] * 0.6)
            blendLen = math.hypot(*blended)
            if blendLen > 1e-6:
                edgeDir = (blended[0] / blendLen, blended[1] / blendLen)

    # To actually shorten the long edge, the cut line must run TRANSVERSE
    # to it (a cross-street cutting straight across the block), not
    # parallel to it -- so the half-plane's normal is edgeDir itself: the
    # boundary line of that half-plane is perpendicular to normal, i.e.
    # perpendicular to edgeDir, i.e. it slices the long edge in two.
    # Cut position is jittered off-center along that edge direction so
    # blocks don't all come out perfectly uniform (real subdivisions
    # rarely bisect a parcel exactly in half).
    normal = edgeDir
    frac = rng.uniform(0.42, 0.58)
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    offset = (frac - 0.5) * length
    splitPoint = (cx + edgeDir[0] * offset, cy + edgeDir[1] * offset)

    posSide = _clip_polygon(poly, _halfplane_quad(splitPoint, normal))
    negSide = _clip_polygon(poly, _halfplane_quad(splitPoint, (-normal[0], -normal[1])))
    pieces = []
    for side in (posSide, negSide):
        if len(side) >= 3 and _polygon_area(side) > 1e-3:
            pieces.append(side)
    if len(pieces) < 2:
        return [poly]
    result = []
    for piece in pieces:
        result.extend(_subdivide_block(piece, minLen, maxLen, rng, terrain, depth + 1, maxDepth))
    return result


def _build_road_graph(roads):
    """Undirected weighted graph of the road network, edge weight = segment length."""
    import networkx as nx

    G = nx.Graph()
    for r in roads:
        a, b = tuple(r["start"]), tuple(r["end"])
        G.add_edge(a, b, weight=math.hypot(b[0] - a[0], b[1] - a[1]))
    return G


def _classify_roads_functional(roads, terrain=None):
    """
    Functional road classification (arterial / collector / local), the
    civil-engineering way: by what a segment *connects* -- measured with
    edge betweenness centrality on the road network graph, i.e. what
    fraction of shortest paths between all pairs of intersections pass
    through it -- rather than by raw distance from the city center. A
    segment that many trips must pass through is an arterial regardless
    of where it happens to sit geometrically; a cul-de-sac spur near the
    center is still local. If a terrain model is supplied, edge weights
    are inflated by local slope first, so the "shortest paths" (and thus
    the resulting classification) already account for grade the way a
    real route-choice model would -- drivers and road planners both
    avoid steep segments when a flatter alternative exists.
    """
    import networkx as nx

    G = _build_road_graph(roads)
    if terrain is not None:
        for a, b, data in G.edges(data=True):
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            slope = terrain.slope(mid[0], mid[1])
            data["weight"] *= (1.0 + 4.0 * slope)

    if G.number_of_edges() == 0:
        return roads
    centrality = nx.edge_betweenness_centrality(G, weight="weight")

    values = list(centrality.values())
    if not values:
        return roads
    hi = sorted(values, reverse=True)[max(0, len(values) // 8)]  # ~top 12.5%
    lo = sorted(values)[max(0, len(values) // 2)]  # median

    for r in roads:
        a, b = tuple(r["start"]), tuple(r["end"])
        c = centrality.get((a, b), centrality.get((b, a), 0.0))
        if c >= hi:
            r["hierarchy"] = "arterial"
        elif c >= lo:
            r["hierarchy"] = "collector"
        else:
            r["hierarchy"] = "local"
    return roads


def _sample_seed_points_terrain_aware(numPoints, radius, centerBias, rng, terrain, maxSlope, maxAttempts=40):
    """
    Same center-biased radial sampling as _sample_seed_points, but rejects
    (and re-rolls) any candidate whose local slope exceeds maxSlope --
    real settlements don't found a dense downtown block on a hillside.
    Falls back to accepting the least-steep of the attempted candidates
    if maxAttempts is exhausted, so a small buildable pocket of flat land
    doesn't stall generation or silently return too few points for
    Voronoi (which needs at least 4).
    """
    points = []
    for _ in range(numPoints):
        best, bestSlope = None, None
        for _attempt in range(maxAttempts):
            u = rng.random()
            r = radius * (u ** centerBias)
            theta = rng.random() * 2 * math.pi
            x, y = r * math.cos(theta), r * math.sin(theta)
            slope = terrain.slope(x, y)
            if slope <= maxSlope:
                best = (x, y)
                break
            if bestSlope is None or slope < bestSlope:
                best, bestSlope = (x, y), slope
        points.append(best)
    return np.array(points)


def _segment_on_polygon_boundary(a, b, poly, tol=0.05):
    """
    True if segment a-b lies along one of poly's edges (used to tell a
    subdivision cut -- a brand new internal street -- apart from an edge
    the piece inherited unchanged from the original block boundary).
    """
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        if _dist_point_to_segment(a, p, q) < tol and _dist_point_to_segment(b, p, q) < tol:
            return True
    return False


def _dist_point_to_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))


def _dedupe_road_segments(roads):
    """Drops duplicate segments (each internal cut is shared by the two pieces it separates)."""
    seen = set()
    result = []
    for r in roads:
        a, b = tuple(r["start"]), tuple(r["end"])
        key = tuple(sorted([tuple(round(c, 3) for c in a), tuple(round(c, 3) for c in b)]))
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


def generate_city_layout(
    numBlocks=60,
    radius=200.0,
    centerBias=1.6,
    minBlockArea=25.0,
    seed=None,
    dem_path=None,
    dem_origin=(0.0, 0.0),
    max_slope=None,
    road_classification="distance",
    block_method="voronoi",
    target_block_length=140.0,
):
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
        dem_path: optional path to a GeoTIFF DEM (see pro/city/terrain.py).
            When given, seed siting, block subdivision, civic-building
            placement, and (in "functional" mode) road classification all
            react to real elevation/slope. Requires rasterio.
        dem_origin: (x, y) in the DEM's own world/projected coordinates
            that the layout's local (0, 0) should map to.
        max_slope: if set (with or without dem_path -- omit dem_path to
            use the deterministic synthetic terrain instead), seed points
            landing on ground steeper than this (rise/run, e.g. 0.25 =~
            14 degrees) are re-rolled so dense downtown blocks don't get
            sited on a hillside. None (default) disables terrain-aware
            siting entirely, matching the original behavior exactly.
        road_classification: "distance" (default, unchanged original
            behavior: primary/secondary by distance from center) or
            "functional": arterial/collector/local by betweenness
            centrality on the road network graph (see
            _classify_roads_functional). Requires networkx.
        block_method: "voronoi" (default, unchanged original behavior) or
            "subdivision": after the Voronoi tessellation, any block
            longer than target_block_length is recursively bisected (see
            _subdivide_block) until every block falls within the target
            walkable-block-length range, with the new cut edges added to
            "roads" as local streets.
        target_block_length: only used when block_method="subdivision";
            the longest allowed block edge in meters before it gets cut.

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
                # ("arterial"|"collector"|"local" instead, if
                # road_classification="functional")
                ...
            ],
        }
    """
    rng = randomlib.Random(seed)
    npRng = np.random.default_rng(seed)

    terrain = None
    if dem_path is not None or max_slope is not None:
        terrain = load_terrain(dem_path=dem_path, seed=seed or 0, dem_origin=dem_origin)

    if terrain is not None and max_slope is not None:
        points = _sample_seed_points_terrain_aware(numBlocks, radius, centerBias, rng, terrain, max_slope)
    else:
        points = _sample_seed_points(numBlocks, radius, centerBias, rng)
    if len(points) < 4:
        raise ValueError("generate_city_layout needs at least 4 blocks to compute a Voronoi diagram")

    vor = Voronoi(points)
    boundary = _boundary_polygon(radius)
    rawPolygons = _finite_polygons(vor, extensionRadius=radius * 10)

    def _make_block(clipped, blockId):
        area = _polygon_area(clipped)
        cx = sum(p[0] for p in clipped) / len(clipped)
        cy = sum(p[1] for p in clipped) / len(clipped)
        distanceFromCenter = math.hypot(cx, cy)
        density = max(0.0, 1.0 - distanceFromCenter / radius)
        return {
            "id": blockId,
            "polygon": [[round(x, 4), round(y, 4)] for x, y in clipped],
            "centroid": [round(cx, 4), round(cy, 4)],
            "area": round(area, 2),
            "distance_from_center": round(distanceFromCenter, 4),
            "density": round(density, 4),
        }

    blocks = []
    subdivisionRoads = []
    for i, poly in enumerate(rawPolygons):
        if not poly:
            continue
        clipped = _clip_polygon(poly, boundary)
        if len(clipped) < 3:
            continue
        area = _polygon_area(clipped)
        if area < minBlockArea:
            continue

        if block_method == "subdivision":
            pieces = _subdivide_block(clipped, minBlockArea, target_block_length, rng, terrain)
        else:
            pieces = [clipped]

        for piece in pieces:
            if len(piece) < 3 or _polygon_area(piece) < minBlockArea:
                continue
            blocks.append(_make_block(piece, len(blocks)))

        if block_method == "subdivision" and len(pieces) > 1:
            # the internal cut edges introduced by subdivision are new
            # local streets -- record them the same way ridge-derived
            # roads are recorded below, so they show up in "roads" too
            for piece in pieces:
                n = len(piece)
                for k in range(n):
                    a, b = piece[k], piece[(k + 1) % n]
                    if not _segment_on_polygon_boundary(a, b, clipped):
                        subdivisionRoads.append({
                            "start": [round(a[0], 4), round(a[1], 4)],
                            "end": [round(b[0], 4), round(b[1], 4)],
                            "hierarchy": "local",
                        })

    # Roads: the unique shared edges between neighboring cells (their
    # ridges), deduped and clipped the same way as blocks. In the default
    # "distance" mode, ridges whose midpoint is close to the center are
    # marked "primary" (wider/more important), others "secondary" -- this
    # part is unchanged from the original geometry-only heuristic.
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
    roads.extend(_dedupe_road_segments(subdivisionRoads))

    if road_classification == "functional":
        roads = _classify_roads_functional(roads, terrain)

    _assign_town_roles(blocks, terrain)
    return {"center": [0, 0], "radius": radius, "blocks": blocks, "roads": roads}


def _assign_town_roles(blocks, terrain=None):
    """
    Tag civic landmarks the way a Magdeburg-plan Polish miasteczko is
    organized: a market square (rynek) at the center, church and town hall
    (ratusz) on it, a synagogue nearby, kamienice around the core, cottages
    toward the edge.

    Ranking is by (distance from center, -area) as before -- civic
    buildings want a big central plot. When a terrain model is supplied,
    that ranking key gets a third term: local slope, so a candidate site
    that's central and large but sits on a steep hillside is passed over
    in favor of a flatter one further down the candidate list, the way a
    real town's founders would site the market square on the most
    buildable ground available rather than strictly the most central one.
    """
    if not blocks:
        return
    if terrain is not None:
        def sort_key(b):
            cx, cy = b["centroid"]
            slope = terrain.slope(cx, cy)
            return (round(slope, 3), b["distance_from_center"], -b["area"])
        ranked = sorted(blocks, key=sort_key)
    else:
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


def _block_zone_hint(block, xmin, ymin, xmax, ymax, radius_guess):
    """
    Cheap pre-parceling estimate of which zoning district a block belongs
    to, using the same geometry _assign_plot_types uses afterward for the
    precise per-plot role. Only needs to be roughly right: it decides
    which ZONING_RULES lot-dimension table parcel_block draws from, while
    _assign_plot_types still does the authoritative per-plot role stamping
    afterward.
    """
    tol = max(6.0, (xmax - xmin) * 0.15)
    on_square = False
    for p in block["polygon"]:
        on_v = (abs(p[0] - xmin) < tol or abs(p[0] - xmax) < tol) and (ymin - tol <= p[1] <= ymax + tol)
        on_h = (abs(p[1] - ymin) < tol or abs(p[1] - ymax) < tol) and (xmin - tol <= p[0] <= xmax + tol)
        if on_v or on_h:
            on_square = True
            break
    if on_square:
        return "commercial"
    dist = block["distance_from_center"]
    if dist < radius_guess * 0.45:
        return "residential_dense"
    elif dist < radius_guess * 0.75:
        return "residential_mid"
    return "residential_edge"


def generate_polish_town_layout(numBlocks=48, radius=160.0, seed=1927, use_zoning=False, **kwargs):
    """
    Magdeburg-plan miasteczko: rectangular rynek, Voronoi streets around it,
    human-scale rectangular plots along every street edge.

    use_zoning: when True, each block's plots are dimensioned from
        ZONING_RULES (parcels.py) via a per-block zone estimate
        (_block_zone_hint) instead of the plain density interpolation --
        so, e.g., blocks facing the rynek get tight commercial-frontage
        lots regardless of density, and outer blocks get spacious
        villa/barn-scale lots. Default False preserves the original
        density-only parceling exactly.
    """
    try:
        from .parcels import parcel_block
    except ImportError:
        from parcels import parcel_block

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

    radius_guess_for_zoning = max((b["distance_from_center"] for b in kept), default=1.0) or 1.0
    plots = []
    for block in kept:
        zone = (
            _block_zone_hint(block, xmin, ymin, xmax, ymax, radius_guess_for_zoning)
            if use_zoning else None
        )
        for plot in parcel_block(
            [tuple(p) for p in block["polygon"]],
            density=block["density"],
            rng=rng,
            zone=zone,
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
    parser.add_argument("--dem", default=None, help="Path to a GeoTIFF DEM for terrain-aware siting (requires rasterio)")
    parser.add_argument("--dem-origin-x", type=float, default=0.0)
    parser.add_argument("--dem-origin-y", type=float, default=0.0)
    parser.add_argument("--max-slope", type=float, default=None,
                        help="Reject seed points steeper than this rise/run (e.g. 0.25). "
                             "Works with synthetic terrain even without --dem.")
    parser.add_argument("--road-classification", choices=["distance", "functional"], default="distance")
    parser.add_argument("--block-method", choices=["voronoi", "subdivision"], default="voronoi")
    parser.add_argument("--target-block-length", type=float, default=140.0)
    parser.add_argument("--use-zoning", action="store_true",
                        help="polish style only: dimension plots from zoning rules instead of density alone")
    args = parser.parse_args()

    if args.style == "polish":
        layout = generate_polish_town_layout(
            numBlocks=args.blocks, radius=args.radius, seed=args.seed if args.seed is not None else 1927,
            centerBias=args.center_bias if args.center_bias != 1.6 else 1.25,
            dem_path=args.dem, dem_origin=(args.dem_origin_x, args.dem_origin_y),
            max_slope=args.max_slope, road_classification=args.road_classification,
            block_method=args.block_method, target_block_length=args.target_block_length,
            use_zoning=args.use_zoning,
        )
    else:
        layout = generate_city_layout(
            numBlocks=args.blocks, radius=args.radius,
            centerBias=args.center_bias, seed=args.seed,
            dem_path=args.dem, dem_origin=(args.dem_origin_x, args.dem_origin_y),
            max_slope=args.max_slope, road_classification=args.road_classification,
            block_method=args.block_method, target_block_length=args.target_block_length,
        )
    save_city_layout(layout, args.output)
    extra = ""
    if layout.get("plots"):
        extra = " / %d plots" % len(layout["plots"])
    print("Wrote %d blocks%s and %d road segments to %s" % (
        len(layout["blocks"]), extra, len(layout["roads"]), args.output))
