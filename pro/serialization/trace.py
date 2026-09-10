"""Generation-record encoding (authored vs resolved).

Unknown types raise SerializationError — never silently str().
"""
from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable


class SerializationError(TypeError):
	"""Raised when a value cannot be encoded into a generation record."""

	def __init__(self, value: Any):
		self.value = value
		super().__init__(
			"Cannot serialize %s for generation records; "
			"add an encode_value branch, implement to_dict(), "
			"or list the attribute in a trace skip set"
			% type(value).__name__
		)


@runtime_checkable
class Serializable(Protocol):
	"""Types that can appear in generation records via to_dict()."""

	def to_dict(self) -> dict: ...


# Bookkeeping attrs never appear in generation records
_SERIALIZE_SKIP_ATTRS = {
	"count",
	"operators",
	"executedChildren",
	"_param_authored",
}

# Nested operator lists emitted as top-level record fields (not parameters)
_STRUCTURAL_ATTRS = frozenset({"parts", "cases", "default", "insets"})


def encode_value(v):
	"""
	Encode a value as a generation-record cell (authored + resolved when known).

	Used by Operator.to_dict() / Rule.to_dict() and encode_param().
	Raises SerializationError for unsupported types (no str() fallback).
	"""
	# Lazy imports avoid a serialization ↔ dsl/params cycle at module load.
	from ..dsl.operator import Operator, RrshiftOperator
	from ..dsl.modifier import Modifier
	from ..params.random import Random
	from ..params.choice import Choice
	from ..params.parameter import Param

	if isinstance(v, Operator):
		return v.to_dict()
	if isinstance(v, RrshiftOperator):
		cell = {
			"kind": "rrshift",
			"operator": encode_value(v.operator),
			"value": encode_value(getattr(v, "value", None)),
		}
		if v.modifier is not None:
			cell["modifier"] = v.modifier
		return cell
	if isinstance(v, Modifier):
		cell = {
			"kind": "modifier",
			"modifier": v.modifier,
			"value": encode_value(v.value),
		}
		try:
			cell["resolved"] = float(v.value)
		except (TypeError, ValueError):
			pass
		return cell
	if isinstance(v, Random):
		return {
			"kind": "random",
			"range": [v.low, v.high],
			"resolved": v.getValue(),
		}
	if isinstance(v, Choice):
		cell = {
			"kind": "choice",
			"options": [encode_value(o) if not _is_plain(o) else o for o in v.options],
			"resolved": v.getValue(),
		}
		if v.weights is not None:
			cell["weights"] = list(v.weights)
		return cell
	if isinstance(v, Param):
		return _encode_param_instance(v)

	# Split helpers (authored or post-calculateSplit)
	from ..op_split import SplitDef, RawValue
	if isinstance(v, SplitDef):
		return {
			"kind": "split_def",
			"repeat": bool(v.repeat),
			"parts": [encode_value(p) for p in v.parts],
		}
	if isinstance(v, RawValue):
		return {
			"kind": "raw_value",
			"value": encode_value(v.value),
		}

	# Duck-typed Serializable / Opening / test doubles with to_dict()
	to_dict = getattr(v, "to_dict", None)
	if callable(to_dict) and not isinstance(v, type):
		data = to_dict()
		if isinstance(data, dict) and ("operator" in data or "kind" in data):
			return data
		if isinstance(data, dict):
			return {
				"kind": "object",
				"type": type(v).__name__,
				"fields": data,
			}
		raise SerializationError(v)

	if isinstance(v, (list, tuple)):
		return {
			"kind": "list",
			"items": [encode_value(x) for x in v],
		}
	if isinstance(v, dict):
		return {
			"kind": "map",
			"entries": {str(k2): encode_value(x) for k2, x in v.items()},
		}
	if _is_plain(v):
		return {"kind": "literal", "resolved": v}
	raise SerializationError(v)


def encode_param(authored, resolved=None):
	"""
	Build a parameter cell from an authored source and an optional already-resolved value.

	When `authored` is Random/Choice/Param, prefer its structured encode and
	override `resolved` with the explicit resolved value when provided.
	"""
	from ..params.random import Random
	from ..params.choice import Choice
	from ..params.parameter import Param

	if isinstance(authored, (Random, Choice, Param)):
		cell = encode_value(authored)
		if resolved is not None:
			cell["resolved"] = _plain_resolved(resolved)
		return cell
	if resolved is not None and authored is not resolved and not _is_plain(authored):
		# Authored was something structured; encode it and attach resolved.
		cell = encode_value(authored)
		cell["resolved"] = _plain_resolved(resolved)
		return cell
	if resolved is not None:
		return {"kind": "literal", "resolved": _plain_resolved(resolved)}
	return encode_value(authored)


def _encode_param_instance(param):
	from ..params.parameter import ParamFloat, ParamColor

	cell = {"kind": "param"}
	group = getattr(param, "group", None)
	unit = getattr(param, "unit", None)
	if group is not None:
		cell["group"] = group
	if unit is not None:
		cell["unit"] = unit

	if isinstance(param, ParamFloat):
		if param.min is not None:
			cell["min"] = param.min
		if param.max is not None:
			cell["max"] = param.max
		if param.random is not None:
			cell["authored"] = encode_value(param.random)
		else:
			cell["authored"] = {"kind": "literal", "resolved": param.value}
		cell["resolved"] = param.getValue()
		return cell

	if isinstance(param, ParamColor):
		if getattr(param, "choice", None) is not None:
			cell["authored"] = encode_value(param.choice)
		else:
			cell["authored"] = {"kind": "literal", "resolved": param.value}
		# Prefer hex string for readability when available
		cell["resolved"] = str(param) if param.value is not None or param.choice else param.getValue()
		return cell

	cell["authored"] = {"kind": "literal", "resolved": param.getValue()}
	cell["resolved"] = param.getValue()
	return cell


def _is_plain(v):
	return isinstance(v, (int, float, str, bool)) or v is None


def _plain_resolved(v):
	if isinstance(v, (tuple, list)) and v and all(isinstance(x, (int, float)) for x in v):
		return list(v)
	if _is_plain(v):
		return v
	try:
		return float(v)
	except (TypeError, ValueError):
		raise SerializationError(v)


def wrap_trace(root, seed=None, rule=None):
	"""Optional export envelope around a root generation record."""
	envelope = {
		"format": "bcga-trace",
		"version": 1,
		"root": root,
	}
	if seed is not None:
		envelope["seed"] = seed
	if rule is not None:
		envelope["rule"] = rule
	return envelope


def to_json(rule, **kwargs):
	"""
	Convenience wrapper: serializes a Rule/Operator (or its already-computed
	to_dict() result) to a JSON string. kwargs are passed through to
	json.dumps (e.g. indent=2).
	"""
	data = rule.to_dict() if hasattr(rule, "to_dict") else rule
	return json.dumps(data, **kwargs)


# Back-compat alias used by older imports / façade
def _serialize_value(v):
	return encode_value(v)
