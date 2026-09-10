"""2D polygon helpers. No bpy; depends only on geom.vector."""
import math

from .vector import _add, _cross, _dot, _mul, _norm, _sub

_AREA_EPS = 1e-6
_SPAN_EPS = 1e-9


def _centroid(poly):
	return (
		sum(p[0] for p in poly) / len(poly),
		sum(p[1] for p in poly) / len(poly),
	)


def _polygon_area(poly):
	n = len(poly)
	if n < 3:
		return 0.0
	acc = 0.0
	for i in range(n):
		a, b = poly[i], poly[(i + 1) % n]
		acc += a[0] * b[1] - b[0] * a[1]
	return acc * 0.5


def _point_in_convex(p, poly, eps=1e-7):
	n = len(poly)
	for i in range(n):
		a, b = poly[i], poly[(i + 1) % n]
		if _cross(_sub(b, a), _sub(p, a)) < -eps:
			return False
	return True


def _clip_polygon(subject, clipPoly):
	"""Sutherland-Hodgman. clipPoly must be convex and CCW."""
	def inside(p, a, b):
		return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

	def intersect(p1, p2, a, b):
		x1, y1 = p1
		x2, y2 = p2
		x3, y3 = a
		x4, y4 = b
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
	return _dedupe_ring(output)


def _dedupe_ring(poly, tol=1e-9):
	if not poly:
		return []
	out = [poly[0]]
	for p in poly[1:]:
		if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > tol:
			out.append(p)
	if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
		out.pop()
	return out


def _halfplane_quad(point, normal, size=1e5):
	"""
	Large convex CCW quad for {p : dot(p - point, normal) >= 0}.
	`perp` is normal rotated -90 deg so (perp, normal) is right-handed.
	"""
	perp = (normal[1], -normal[0])
	a = (point[0] - perp[0] * size, point[1] - perp[1] * size)
	b = (point[0] + perp[0] * size, point[1] + perp[1] * size)
	c = (b[0] + normal[0] * size, b[1] + normal[1] * size)
	d = (a[0] + normal[0] * size, a[1] + normal[1] * size)
	return [a, b, c, d]


def _clip_half(poly, point, normal):
	return _clip_polygon(poly, _halfplane_quad(point, normal))


def _valid_poly(poly):
	return poly is not None and len(poly) >= 3 and _polygon_area(poly) > _AREA_EPS


def _edge_inward(a, b, poly):
	direction = _norm(_sub(b, a))
	inward = (-direction[1], direction[0])  # left of CCW edge
	mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
	c = _centroid(poly)
	if _dot(inward, _sub(c, mid)) < 0:
		inward = (-inward[0], -inward[1])
	return direction, inward


def _inset_convex(poly, margin):
	if margin <= 0:
		return list(poly)
	result = list(poly)
	n = len(poly)
	for i in range(n):
		a, b = poly[i], poly[(i + 1) % n]
		_direction, inward = _edge_inward(a, b, poly)
		offset_pt = _add(a, _mul(inward, margin))
		result = _clip_half(result, offset_pt, inward)
		if not _valid_poly(result):
			return []
	return result


def _longest_edge_axis(poly):
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


def _span_along(poly, axis):
	dots = [_dot(p, axis) for p in poly]
	return min(dots), max(dots)


def _width_depth(poly):
	"""width = shorter span, depth = longer span, in the longest-edge frame."""
	_length, edgeDir, _mid = _longest_edge_axis(poly)
	perp = (-edgeDir[1], edgeDir[0])
	long_span = _span_along(poly, edgeDir)
	short_span = _span_along(poly, perp)
	long = long_span[1] - long_span[0]
	short = short_span[1] - short_span[0]
	return short, long
