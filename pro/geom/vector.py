"""2D vector primitives. No bpy; imports nothing from rooms/openings/ops."""
import math


def _sub(a, b):
	return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
	return (a[0] + b[0], a[1] + b[1])


def _mul(a, s):
	return (a[0] * s, a[1] * s)


def _dot(a, b):
	return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
	return a[0] * b[1] - a[1] * b[0]


def _len(a):
	return math.hypot(a[0], a[1])


def _norm(a):
	L = _len(a)
	if L < 1e-12:
		return (0.0, 0.0)
	return (a[0] / L, a[1] / L)
