"""
Compatibility façade for the former pro.base god module.

Implementations live under:
  pro.dsl          — Modifier, Operator, Rule, …
  pro.params       — Param*, Random, Choice
  pro.runtime      — Context, State, shape, …
  pro.serialization — encode_value / to_json / generation records

Import from `pro.base` remains the stable public path.
"""

from .dsl.modifier import Modifier, flt, rel
from .dsl.operator import (
	Operator,
	RrshiftOperator,
	ComplexOperator,
	countOperator,
	OperatorDef,
)
from .dsl.rule import Rule
from .params.parameter import Param, ParamFloat, ParamColor, param
from .params.random import Random, random
from .params.choice import Choice, choice
from .runtime.state import State
from .runtime.context import (
	Context,
	ContextProxy,
	RandomContext,
	TraceContext,
	_OPERATOR_FACTORY,
	_default_context,
	context,
)
from .runtime.execution import shape
from .serialization.trace import (
	_SERIALIZE_SKIP_ATTRS,
	_serialize_value,
	SerializationError,
	Serializable,
	encode_value,
	encode_param,
	wrap_trace,
	to_json,
)

__all__ = [
	"Modifier",
	"flt",
	"rel",
	"Operator",
	"RrshiftOperator",
	"ComplexOperator",
	"countOperator",
	"OperatorDef",
	"Rule",
	"Param",
	"ParamFloat",
	"ParamColor",
	"param",
	"Random",
	"random",
	"Choice",
	"choice",
	"State",
	"Context",
	"ContextProxy",
	"RandomContext",
	"TraceContext",
	"_OPERATOR_FACTORY",
	"_default_context",
	"context",
	"shape",
	"_SERIALIZE_SKIP_ATTRS",
	"_serialize_value",
	"SerializationError",
	"Serializable",
	"encode_value",
	"encode_param",
	"wrap_trace",
	"to_json",
]
