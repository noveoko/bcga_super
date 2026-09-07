"""Pure-Python tests for stair_profile and the stairwell() constructor."""
from pro.stairs import stair_profile


def test_risers_divide_rise_evenly():
    p = stair_profile(3.67, tread=0.27, riser=0.18)
    assert p["n_risers"] >= 1
    assert abs(p["n_risers"] * p["riser"] - 3.67) < 1e-9


def test_profile_starts_at_origin_ends_at_rise():
    p = stair_profile(3.0, tread=0.27, riser=0.18)
    assert p["parts"][0] == (0.0, 0.0)
    assert abs(p["parts"][-1][1] - 3.0) < 1e-12


def test_run_is_n_treads_times_tread():
    p = stair_profile(3.6, tread=0.30, riser=0.18)
    n_treads = p["n_risers"]
    assert abs(p["run"] - n_treads * p["tread"]) < 1e-12


def test_shrinks_tread_to_fit_run_available():
    p = stair_profile(3.6, tread=0.40, riser=0.18, run_available=4.0)
    assert p["run"] == 4.0
    assert p["tread"] < 0.40
    assert abs(p["n_risers"] * p["tread"] - 4.0) < 1e-12
    assert abs(p["parts"][-1][0] - 4.0) < 1e-12
    assert abs(p["parts"][-1][1] - 3.6) < 1e-12


def test_pads_landing_when_well_is_longer_than_run():
    p = stair_profile(1.8, tread=0.27, riser=0.18, run_available=12.0)
    natural_run = p["n_risers"] * p["tread"]
    assert natural_run < 12.0
    assert abs(p["run"] - 12.0) < 1e-12
    assert abs(p["parts"][-1][0] - 12.0) < 1e-12
    assert abs(p["parts"][-1][1] - 1.8) < 1e-12
    # landing is horizontal at z=rise
    assert abs(p["parts"][-2][1] - 1.8) < 1e-12


def test_tiny_rise_still_produces_a_step():
    p = stair_profile(0.3, tread=0.27, riser=0.18)
    assert p["n_risers"] >= 1
    assert abs(p["parts"][-1][1] - 0.3) < 1e-12


def test_zero_rise_is_a_flat_landing():
    p = stair_profile(0.0, tread=0.27, riser=0.18, run_available=5.0)
    assert p["n_risers"] == 0
    assert p["parts"][0] == (0.0, 0.0)
    assert abs(p["parts"][-1][0] - 5.0) < 1e-12
    assert p["parts"][-1][1] == 0.0


def test_stairwell_operator_records_kwargs():
    from pro.base import context
    from pro.op_stairwell import Stairwell

    class _DummyParent:
        def addChildOperator(self, o):
            pass

        def removeChildOperators(self, n):
            pass

    context.operator = _DummyParent()
    s = Stairwell(3.0, tread=0.25, riser=0.16)
    assert s.rise == 3.0
    assert s.tread == 0.25
    assert s.riser == 0.16
    assert s.symmetric is False
    assert s.relativeCoord1 is False
    assert s.relativeCoord2 is False
