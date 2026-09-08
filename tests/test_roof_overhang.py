"""
Tests for roof eave overhang support (soffit inset + fascia board) on
gable_roof()/hip_roof(). All bpy-free -- these only exercise the pure-Python
argument-parsing side (pro/op_gable_roof.py, pro/op_hip_roof.py), not the
Blender-side mesh building in bpro/, which needs bpy and is covered by the
"integration" marker elsewhere.

Historically (roughly 1890-1935) roofs were built with rafters that ran
past the wall face, carrying a soffit and a fascia/barge board -- the roof
did not simply stop flush at the wall. soffitSize is a negative inset that
pushes the roof edge outward before the pitch starts; fasciaSize adds a
vertical board hanging off that outward edge.
"""
from pro.base import context, Operator
from pro.op_gable_roof import GableRoof
from pro.op_hip_roof import HipRoof


class _DummyParent:
    def addChildOperator(self, o):
        pass

    def removeChildOperators(self, n):
        pass


def _with_context():
    context.operator = _DummyParent()


def _tag(value):
    """A minimal stand-in for `face >> Rule()` / `soffit >> Rule()` / etc.:
    a real Operator instance with .value set to the tag name, matching what
    Operator.__rrshift__ produces."""
    op = Operator()
    op.value = value
    op.count = False  # already "spent"; don't let it get double-counted
    return op


# -- gable_roof() ---------------------------------------------------------

def test_gable_roof_without_overhang_has_no_soffit():
    _with_context()
    g = GableRoof(35.0)
    assert g.pitch == 35.0
    assert g.soffitSize is None
    assert g.fasciaSize is None


def test_gable_roof_overhang_sets_soffit_and_fascia():
    _with_context()
    g = GableRoof(
        35.0, 0.45,
        _tag("face"), _tag("soffit"), _tag("fascia"),
        fasciaSize=0.14,
    )
    assert g.pitch == 35.0
    assert g.soffitSize == 0.45
    assert g.fasciaSize == 0.14
    assert g.face is not None and g.face.value == "face"
    assert g.soffit is not None and g.soffit.value == "soffit"
    assert g.fascia is not None and g.fascia.value == "fascia"


# -- hip_roof(): single overhang for all edges -----------------------------

def test_hip_roof_uniform_overhang():
    _with_context()
    h = HipRoof(
        38.0, 0.45,
        _tag("face"), _tag("soffit"), _tag("fascia"),
        fasciaSize=0.14,
    )
    h.init(numEdges=4)
    assert h.pitches == (38.0,)
    assert h.soffits == (0.45,)
    assert h.fasciaSize == 0.14


def test_hip_roof_without_overhang_has_no_soffit():
    _with_context()
    h = HipRoof(38.0, _tag("face"))
    h.init(numEdges=4)
    assert h.pitches == (38.0,)
    assert h.soffits is None
    assert h.fasciaSize is None


# -- hip_roof(): per-edge pitch AND per-edge overhang (half-hip case) ------

def test_hip_roof_per_edge_pitch_and_overhang():
    _with_context()
    h = HipRoof(
        35, 0.45, 90, 0.45, 35, 0.45, 58, 0.45,
        _tag("face"), _tag("soffit"), _tag("fascia"),
        fasciaSize=0.14,
    )
    h.init(numEdges=4)
    assert h.pitches == [35, 90, 35, 58]
    assert h.soffits == [0.45, 0.45, 0.45, 0.45]
    assert h.fasciaSize == 0.14
