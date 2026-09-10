"""
Tests for the new DSL richness/variety primitives: chance() (stochastic
rule selection), choice() (discrete random value), switch() (conditional
branching). All bpy-free.
"""
import pro
from pro.base import context, param, choice
from pro.op_chance import Chance
from pro.op_switch import Switch


class _Recorder:
    """A minimal stand-in for a Rule/Operator: records that it executed."""
    count = True  # matches Operator's own class attribute, needed by countOperator/removeChildOperators-style checks
    def __init__(self, name):
        self.name = name
        self.executed = False
    def execute(self):
        self.executed = True


from helpers import install_dummy_operator


def _with_context():
    install_dummy_operator()


# -- choice() -----------------------------------------------------------

def test_choice_picks_one_of_the_given_options():
    c = choice("a", "b", "c")
    assert c.getValue() in ("a", "b", "c")


def test_choice_is_resolved_once_and_stable():
    c = choice(1, 2, 3, 4, 5)
    first = c.getValue()
    for _ in range(10):
        assert c.getValue() == first


def test_choice_distribution_covers_all_options():
    context.set_seed(42)
    seen = set()
    for _ in range(200):
        seen.add(choice("a", "b", "c").getValue())
    assert seen == {"a", "b", "c"}


def test_choice_respects_weights_statistically():
    context.set_seed(1)
    results = [choice("rare", "common", weights=[0.02, 0.98]).getValue() for _ in range(500)]
    common_fraction = results.count("common") / len(results)
    assert common_fraction > 0.9  # should be close to 0.98, generous margin for randomness


def test_choice_requires_at_least_one_option():
    import pytest
    with pytest.raises(ValueError):
        choice()


def test_choice_mismatched_weights_length_raises():
    import pytest
    with pytest.raises(ValueError):
        choice("a", "b", weights=[1, 2, 3])


# -- param() + choice() integration --------------------------------------

def test_param_with_color_choice_dispatches_to_paramcolor():
    from pro.base import ParamColor
    context.init()
    p = param(choice("#ff0000", "#00ff00"), group="Colors")
    assert isinstance(p, ParamColor)
    r, g, b = p.getValue()
    assert (r, g, b) in [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]


def test_param_with_numeric_choice_dispatches_to_paramfloat():
    from pro.base import ParamFloat
    context.init()
    p = param(choice(1, 2, 3))
    assert isinstance(p, ParamFloat)
    # ParamFloat resolves Random/Choice via context.prepare()'s sweep,
    # same contract as random() has always had -- getValue() before that
    # returns None by design (matches pre-existing random() behavior)
    assert p.getValue() is None
    context.prepare()
    assert p.getValue() in (1, 2, 3)


def test_param_color_choice_resolved_once():
    context.init()
    p = param(choice("#ff0000", "#00ff00", "#0000ff"))
    first = p.getValue()
    for _ in range(5):
        assert p.getValue() == first


def test_prepare_accepts_param_color_without_random_attr():
    """bpro.getParams() puts ParamColor in context.params; prepare must not assume .random."""
    from pro.base import ParamColor, ParamFloat, random
    context.init()
    context.set_seed(1)
    color_p = param(choice("#ff0000", "#00ff00"), group="Colors")
    float_p = param(random(1.0, 2.0))
    assert isinstance(color_p, ParamColor)
    assert isinstance(float_p, ParamFloat)
    # Simulate apply() replacing params with the module scan list (includes ParamColor).
    context.params = [color_p, float_p]
    context.prepare()  # must not raise AttributeError
    assert color_p.value in ("#ff0000", "#00ff00")
    assert float_p.value is not None


# -- chance() -------------------------------------------------------------

def test_chance_executes_exactly_one_option():
    _with_context()
    a, b, c = _Recorder("a"), _Recorder("b"), _Recorder("c")
    ch = Chance((1, a), (1, b), (1, c))
    ch.execute()
    executed = [x for x in (a, b, c) if x.executed]
    assert len(executed) == 1


def test_chance_zero_weight_option_never_picked():
    _with_context()
    context.set_seed(0)
    never, always = _Recorder("never"), _Recorder("always")
    for _ in range(50):
        never.executed = always.executed = False
        Chance((0, never), (1, always)).execute()
        assert always.executed
        assert not never.executed


def test_chance_distribution_roughly_matches_weights():
    _with_context()
    context.set_seed(3)
    a, b = _Recorder("a"), _Recorder("b")
    countA = 0
    for _ in range(500):
        a.executed = b.executed = False
        Chance((0.8, a), (0.2, b)).execute()
        if a.executed:
            countA += 1
    fraction = countA / 500
    assert 0.7 < fraction < 0.9  # expect ~0.8, generous margin


def test_chance_requires_at_least_one_part():
    import pytest
    with pytest.raises(ValueError):
        Chance()


def test_chance_all_zero_weights_raises():
    _with_context()
    import pytest
    a, b = _Recorder("a"), _Recorder("b")
    with pytest.raises(ValueError):
        Chance((0, a), (0, b)).execute()


# -- switch() ---------------------------------------------------------------

def test_switch_executes_matching_case():
    _with_context()
    a, b = _Recorder("a"), _Recorder("b")
    sw = Switch("x", {"x": a, "y": b})
    sw.execute()
    assert a.executed and not b.executed


def test_switch_falls_back_to_default():
    _with_context()
    a, default = _Recorder("a"), _Recorder("default")
    sw = Switch("nomatch", {"x": a}, default=default)
    sw.execute()
    assert default.executed and not a.executed


def test_switch_no_match_no_default_does_nothing():
    _with_context()
    a = _Recorder("a")
    sw = Switch("nomatch", {"x": a})
    sw.execute()  # should not raise
    assert not a.executed


def test_switch_with_boolean_keys():
    _with_context()
    yes, no = _Recorder("yes"), _Recorder("no")
    Switch(5 > 3, {True: yes, False: no}).execute()
    assert yes.executed and not no.executed
