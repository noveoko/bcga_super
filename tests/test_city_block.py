"""Phase 5: city_block() helper and import-time soft-deprecation."""
import warnings

import pytest

from pro import context, city_block, city_block_at_import
from pro.session import GenerationSession


def test_city_block_returns_default_when_unset():
    context.cityBlock = None
    assert city_block({"density": 0.5}) == {"density": 0.5}
    assert city_block() == {}


def test_city_block_copies_active_session_plot():
    with GenerationSession() as session:
        session.set_city_block({"id": 3, "role": "cottage", "density": 0.2})
        plot = city_block()
        assert plot == {"id": 3, "role": "cottage", "density": 0.2}
        # Mutation of the returned dict must not affect the session.
        plot["role"] = "mutated"
        assert session.context.cityBlock["role"] == "cottage"


def test_city_block_prefers_session_over_default():
    with GenerationSession() as session:
        session.set_city_block({"density": 0.9})
        assert city_block({"density": 0.1})["density"] == 0.9


def test_city_block_at_import_warns():
    context.cityBlock = {"id": 1}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plot = city_block_at_import({"id": 0})
    assert plot["id"] == 1
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert any("Begin()" in str(w.message) for w in caught)


def test_example_city_building_uses_city_block_helper():
    src = open("examples/city_building.py", encoding="utf-8").read()
    assert "city_block(" in src
    assert "context.cityBlock" not in src
    assert "@rule\ndef Begin():" in src.replace("\r\n", "\n")
