"""
Regression tests for a signature mismatch that silently broke almost
every rule file using a bare (not `>>`-attached) literal split() margin
or flt()/rel() modifier -- which includes both example rule files
(examples/polish_town_1927.py's GroundFloor()/UpperFloor()/WindowBay(),
and this repo's own recommended idiom for split() spacers).

bpro/op_split.py's Split.execute() always calls `cut[2].execute(ctx)` on
whatever ended up attached to a cut -- including RawValue (pro/op_split.py,
wraps a bare float/int split child) and, via other operators
(bpro/op_decompose.py, op_inset.py, op_hip_roof.py, ...), Modifier
(pro/base.py, wraps a bare flt()/rel()) and Param. All three used to
define `execute(self)` with no `ctx` parameter, so any bare literal
reaching one of these call sites raised
`TypeError: X.execute() takes 1 positional argument but 2 were given`
deep inside rule execution -- caught by city_builder.py's per-block
try/except and logged as "failed to generate block N", so entire cities
would render with most buildings silently missing/blank instead of
raising loudly. See also test_city_builder.py's full-pipeline integration
test, which now expects zero failures for exactly this reason.
"""
from pro.base import Modifier, Param
from pro.op_split import RawValue


def test_raw_value_execute_accepts_a_context_argument():
    # Doesn't need to do anything with it -- just must not raise
    # TypeError for the extra positional arg, since every caller in
    # bpro/op_split.py passes one.
    RawValue(0.4).execute(object())
    RawValue(0.4).execute()  # also callable with no ctx


def test_modifier_execute_accepts_a_context_argument():
    Modifier(flt=1.0).execute(object())
    Modifier(flt=1.0).execute()


def test_param_execute_accepts_a_context_argument():
    p = Param()
    p.execute(object())
    p.execute()


def test_param_color_choice_has_random_attribute_for_prepare():
    """
    Context.prepare() (called once per rule apply) does
    `if getattr(param, "random", None): param.assignValue()` for every
    param in context.params -- ParamColor used to have no `.random`
    attribute at all (only ParamFloat did), so any rule file using
    param(choice("#a", "#b")) for a color crashed every single apply
    with AttributeError. A plain (non-Choice) ParamColor should report
    random=None (nothing to resolve); a Choice-backed one should expose
    the Choice so prepare() resolves it the same way ParamFloat does.
    """
    from pro import choice, context
    from pro.base import ParamColor

    context.params = []  # normally set up by Context.begin_apply() before a rule runs
    fixed = ParamColor("#a83232")
    assert fixed.random is None

    randomized = ParamColor(choice("#a83232", "#3255a8"))
    assert randomized.random is not None
    assert randomized.value is None
    randomized.assignValue()
    assert randomized.value in ("#a83232", "#3255a8")
