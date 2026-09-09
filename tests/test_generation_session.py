"""Phase 2: GenerationSession + context proxy isolation."""
from pro import context, GenerationSession, get_active_session
from pro.base import _OPERATOR_FACTORY, _default_context


def test_no_active_session_uses_default_context():
    assert get_active_session() is None
    context.set_seed(11)
    assert context.seed == 11
    assert _default_context.seed == 11


def test_with_session_isolates_seed_and_city_block():
    context.set_seed(1)
    context.cityBlock = {"id": "default"}

    with GenerationSession(seed=42) as session:
        assert get_active_session() is session
        assert context.seed == 42
        assert context.rng is session.context.rng
        context.cityBlock = {"id": "plot-9"}
        assert session.context.cityBlock == {"id": "plot-9"}
        # default context untouched while session is active
        assert _default_context.seed == 1
        assert _default_context.cityBlock == {"id": "default"}

    assert get_active_session() is None
    assert context.seed == 1
    assert context.cityBlock == {"id": "default"}


def test_sessions_share_operator_factory():
    with GenerationSession() as session:
        assert session.context.factory is _OPERATOR_FACTORY
        assert context.factory is _OPERATOR_FACTORY


def test_nested_activate_depth_on_apply_style_activation():
    session = GenerationSession(seed=7)
    session.activate()
    assert get_active_session() is session
    # simulate bpro.apply activating again when already active: depth++
    session.activate()
    session.deactivate()
    assert get_active_session() is session
    session.deactivate()
    assert get_active_session() is None


def test_clear_accumulators_and_properties():
    with GenerationSession() as session:
        session.context.allCeilingLights.append({"a": 1})
        session.context.allGameDoors.append({"b": 2})
        assert session.all_ceiling_lights == [{"a": 1}]
        assert session.all_game_doors == [{"b": 2}]
        session.clear_accumulators()
        assert session.all_ceiling_lights == []
        assert session.all_game_doors == []


def test_two_sessions_do_not_leak_city_block():
    with GenerationSession() as s1:
        s1.set_city_block({"id": 1})
        assert context.cityBlock == {"id": 1}
    with GenerationSession() as s2:
        assert s2.context.cityBlock is None
        s2.set_city_block({"id": 2})
        assert context.cityBlock == {"id": 2}
    assert get_active_session() is None
