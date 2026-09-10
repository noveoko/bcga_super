"""Priority 6–7: authored vs resolved generation records; strict encode."""
import pytest

from helpers import install_dummy_operator
from pro.base import (
    Choice,
    Random,
    ParamFloat,
    SerializationError,
    context,
    encode_value,
    encode_param,
    wrap_trace,
)
from pro.op_extrude import Extrude
from pro.op_chance import Chance
from pro.op_color import Color
from pro.op_switch import Switch
from pro.op_split import SplitDef, RawValue
from pro.openings import Opening
from pro.dsl.operator import Operator


class _Recorder:
    count = True

    def __init__(self, name):
        self.name = name
        self.executed = False

    def execute(self, ctx=None):
        self.executed = True

    def to_dict(self):
        return {"operator": "Recorder", "parameters": {"name": {"kind": "literal", "resolved": self.name}}}


def test_encode_value_random_keeps_range_and_resolved():
    context.set_seed(1)
    cell = encode_value(Random(2.8, 3.6))
    assert cell["kind"] == "random"
    assert cell["range"] == [2.8, 3.6]
    assert 2.8 <= cell["resolved"] <= 3.6


def test_encode_value_choice_keeps_options():
    context.set_seed(2)
    cell = encode_value(Choice("a", "b", "c", weights=[1, 0, 0]))
    assert cell["kind"] == "choice"
    assert cell["options"] == ["a", "b", "c"]
    assert cell["weights"] == [1, 0, 0]
    assert cell["resolved"] == "a"


def test_encode_param_float_with_random_authored():
    context.init()
    context.set_seed(3)
    p = ParamFloat(Random(1.0, 2.0))
    context.prepare()
    cell = encode_value(p)
    assert cell["kind"] == "param"
    assert cell["authored"]["kind"] == "random"
    assert cell["authored"]["range"] == [1.0, 2.0]
    assert 1.0 <= cell["resolved"] <= 2.0


def test_extrude_bind_param_records_authored_random():
    install_dummy_operator()
    context.set_seed(10)
    op = Extrude(Random(2.8, 3.6))
    record = op.to_dict()
    assert record["operator"] == "Extrude"
    depth = record["parameters"]["depth"]
    assert depth["kind"] == "random"
    assert depth["range"] == [2.8, 3.6]
    assert depth["resolved"] == op.depth
    assert isinstance(op.depth, float)


def test_color_records_choice_authored():
    install_dummy_operator()
    context.set_seed(4)
    op = Color(Choice("#ff0000", "#00ff00"))
    record = op.to_dict()
    color = record["parameters"]["color"]
    assert color["kind"] == "choice"
    assert color["options"] == ["#ff0000", "#00ff00"]
    assert color["resolved"] == list(op.color)


def test_chance_records_selected_index():
    install_dummy_operator()
    context.set_seed(5)
    a, b = _Recorder("a"), _Recorder("b")
    ch = Chance((0.0, a), (1.0, b))
    ch.execute()
    record = ch.to_dict()
    assert record["parameters"]["selected"]["resolved"] == 1
    assert b.executed and not a.executed


def test_switch_records_selected_key_index():
    install_dummy_operator()
    a, b = _Recorder("a"), _Recorder("b")
    sw = Switch("wide", {"narrow": a, "wide": b})
    sw.execute()
    record = sw.to_dict()
    assert record["parameters"]["selected"]["resolved"] == 1
    assert record["parameters"]["switchValue"]["resolved"] == "wide"
    assert b.executed and not a.executed


def test_wrap_trace_envelope():
    root = {"operator": "Rule", "rule": "Begin", "parameters": {}}
    env = wrap_trace(root, seed=123, rule="examples/x.py")
    assert env["format"] == "bcga-trace"
    assert env["version"] == 1
    assert env["seed"] == 123
    assert env["rule"] == "examples/x.py"
    assert env["root"] is root


def test_encode_param_overrides_resolved():
    cell = encode_param(Random(0.0, 1.0), resolved=0.5)
    assert cell["kind"] == "random"
    assert cell["resolved"] == 0.5


def test_encode_value_unknown_type_raises():
    with pytest.raises(SerializationError, match="Cannot serialize"):
        encode_value(object())


def test_plain_resolved_unknown_type_raises():
    from pro.serialization.trace import _plain_resolved
    with pytest.raises(SerializationError):
        _plain_resolved(object())


def test_encode_split_def_and_raw_value():
    cell = encode_value(RawValue(2.5))
    assert cell == {"kind": "raw_value", "value": {"kind": "literal", "resolved": 2.5}}

    split_def = SplitDef([1.0, 2.0], repeat=False)
    cell = encode_value(split_def)
    assert cell["kind"] == "split_def"
    assert cell["repeat"] is False
    assert len(cell["parts"]) == 2


def test_encode_opening_via_to_dict():
    cell = encode_value(Opening(offset=1.2, width=0.9, height=2.1))
    assert cell["kind"] == "object"
    assert cell["type"] == "Opening"
    assert cell["fields"]["offset"] == 1.2
    assert cell["fields"]["width"] == 0.9


def test_trace_skip_omits_class_listed_attrs():
    install_dummy_operator()

    class _Skipped(Operator):
        _TRACE_SKIP = frozenset({"secret"})

        def __init__(self):
            self.secret = object()  # would raise if encoded
            self.visible = 1
            super().__init__()

    record = _Skipped().to_dict()
    assert "secret" not in record["parameters"]
    assert record["parameters"]["visible"]["resolved"] == 1


def test_insets_emitted_as_structural_field():
    install_dummy_operator()
    from pro.op_inset import Inset

    op = Inset(1.0)
    record = op.to_dict()
    assert "insets" in record
    assert "insets" not in record["parameters"]
