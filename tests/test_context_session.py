"""Phase 1 Context composition: sub-contexts, chance seeding, apply cleanup."""
import random

import pytest

from pro import context
from pro.base import RandomContext, TraceContext
from pro.op_chance import Chance as ChanceOp

from helpers import install_dummy_operator


def test_context_exposes_random_and_trace_subcontexts():
    assert isinstance(context.random, RandomContext)
    assert isinstance(context.trace, TraceContext)
    # Aliases stay wired for existing callers
    context.set_seed(42)
    assert context.seed == 42
    assert context.rng is context.random.rng
    context.tracing = True
    assert context.trace.tracing is True
    context.buildingTrace = {"ok": 1}
    assert context.trace.buildingTrace == {"ok": 1}
    context.tracing = False
    context.buildingTrace = None


def test_chance_uses_context_rng_not_process_global():
    install_dummy_operator()

    class _Mark:
        def __init__(self, name):
            self.name = name
            self.executed = False

        def execute(self):
            self.executed = True

    # Freeze process-global RNG to a stream that would pick differently if used.
    random.seed(0)
    context.set_seed(123)

    a, b = _Mark("a"), _Mark("b")
    # Build two chance ops with identical weights after the same seed reset.
    context.set_seed(99)
    first = ChanceOp((1.0, a), (1.0, b))
    first.execute()
    first_name = "a" if a.executed else "b"

    a2, b2 = _Mark("a"), _Mark("b")
    context.set_seed(99)
    second = ChanceOp((1.0, a2), (1.0, b2))
    second.execute()
    second_name = "a" if a2.executed else "b"

    assert first_name == second_name


def test_chance_ignores_python_global_seed_changes():
    install_dummy_operator()

    class _Mark:
        def __init__(self):
            self.executed = False

        def execute(self):
            self.executed = True

    context.set_seed(7)
    picks = []
    for global_seed in (1, 2, 3, 4, 5):
        random.seed(global_seed)
        marks = [_Mark(), _Mark()]
        # advance BCGA rng identically each iteration by reseeding
        context.set_seed(7)
        ChanceOp((1.0, marks[0]), (1.0, marks[1])).execute()
        picks.append(0 if marks[0].executed else 1)
    assert len(set(picks)) == 1


def test_begin_end_apply_clears_geometry_attrs_on_failure():
    context.begin_apply()
    context.addAttribute("bm", object())
    context.addAttribute("facesForRemoval", [])
    context.operator = object()
    context.pushState(shape="dummy")

    assert context.bm is not None
    assert context.stack

    try:
        raise RuntimeError("simulated apply failure")
    except RuntimeError as exc:
        context.end_apply(exc)

    # Phase 4: geometry slots live on GeometryContext and are reset to empty
    assert context.bm is None
    assert context.facesForRemoval == []
    assert context.vertexRegistry is None
    assert context.materialManager is None
    assert context.operator is None
    assert context.stack == []
    assert context.deferreds == []
    assert context.params == []
    assert context.ceilingLights == []
    assert context.gameDoors == []


def test_end_apply_preserves_session_accumulators_and_seed():
    context.set_seed(123)
    context.allCeilingLights = [{"n": 1}]
    context.allGameDoors = [{"n": 2}]
    context.cityBlock = {"id": 9}
    context.begin_apply()
    context.ceilingLights = [{"temp": True}]
    context.end_apply()

    assert context.seed == 123
    assert context.allCeilingLights == [{"n": 1}]
    assert context.allGameDoors == [{"n": 2}]
    assert context.cityBlock == {"id": 9}
    assert context.ceilingLights == []
