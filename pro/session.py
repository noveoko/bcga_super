"""
GenerationSession — explicit orchestrator API (Phase 2).

Usage:

    with GenerationSession(seed=12345, blender_context=bpy.context) as session:
        session.set_city_block(plot)
        session.apply("examples/polish_town_1927.py")
        lights = session.all_ceiling_lights

While a session is active, the module-level `pro.context` proxy forwards to
that session's Context so existing rule files and operators keep working.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from .base import Context

_active_session: ContextVar[Optional["GenerationSession"]] = ContextVar(
    "bcga_active_session", default=None
)


def get_active_session() -> Optional["GenerationSession"]:
    return _active_session.get()


class GenerationSession:
    """
    One city/batch or headless generate run.

    Owns a dedicated Context (shared operator factory, isolated RNG / cityBlock
    / all* accumulators). Activate via `with session:` or `activate()`/
    `deactivate()`; `apply()` briefly activates if needed.
    """

    def __init__(self, seed=None, blender_context=None):
        self.context = Context()
        self.context.blenderContext = blender_context
        self.context.allCeilingLights = []
        self.context.allGameDoors = []
        if seed is not None:
            self.context.set_seed(seed)
        self._token = None
        self._activate_depth = 0

    # --- activation ---------------------------------------------------------

    def activate(self):
        """Make this session the target of the `pro.context` proxy."""
        if self._activate_depth == 0:
            self._token = _active_session.set(self)
        self._activate_depth += 1
        return self

    def deactivate(self):
        """Pop one activate() / nested apply activation."""
        if self._activate_depth <= 0:
            return
        self._activate_depth -= 1
        if self._activate_depth == 0 and self._token is not None:
            _active_session.reset(self._token)
            self._token = None

    def __enter__(self):
        return self.activate()

    def __exit__(self, exc_type, exc, tb):
        self.deactivate()
        return False

    # --- session controls ---------------------------------------------------

    def set_seed(self, seed):
        self.context.set_seed(seed)
        return self

    def set_city_block(self, block):
        """Plot/block metadata readable from rule files as context.cityBlock."""
        self.context.cityBlock = block
        return self

    def set_blender_context(self, blender_context):
        self.context.blenderContext = blender_context
        return self

    def clear_accumulators(self):
        """Reset batch light/door lists (e.g. starting a new city)."""
        self.context.allCeilingLights = []
        self.context.allGameDoors = []
        return self

    @property
    def all_ceiling_lights(self):
        return self.context.allCeilingLights

    @property
    def all_game_doors(self):
        return self.context.allGameDoors

    @property
    def building_trace(self):
        return self.context.buildingTrace

    def apply(self, ruleFile, startRule="Begin", trace=False):
        """
        Apply a rule file/module using this session's Context.

        Activates the session for the duration of the apply if it is not
        already the active session (so `with GenerationSession()` batches
        do not flap the ContextVar on every building).
        """
        import bpro
        return bpro.apply(
            ruleFile, startRule=startRule, trace=trace, session=self
        )
