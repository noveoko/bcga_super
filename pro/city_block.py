"""
Plot / block metadata helpers for rule files (Phase 5).

Prefer reading metadata inside Begin() / @rule bodies via city_block(), not
at module import time. Import-time ``context.cityBlock`` still works when
``bpro.getModule()`` re-executes the file after ``session.set_city_block``,
but it freezes values if the same module object is re-applied without reload
(Blender addon path).
"""
from __future__ import annotations

import warnings
from typing import Any, Mapping, MutableMapping, Optional


_IMPORT_TIME_WARNING = (
    "Reading context.cityBlock (or city_block()) at module import time is "
    "discouraged; call city_block() inside Begin() / @rule instead. "
    "Import-time reads only stay correct when the rule file is re-executed "
    "per building (bpro.getModule). See docs/CONTEXT.md (Phase 5)."
)


def city_block(default: Optional[Mapping[str, Any]] = None, *, _warn_stacklevel: int = 2):
    """
    Return the current plot/block dict for this GenerationSession apply.

    Args:
        default: used when no cityBlock is set (standalone generate.py runs).
            If None and cityBlock is unset, returns {}.

    Example (preferred)::

        @rule
        def Begin():
            plot = city_block({"density": 0.5, "role": "house"})
            density = float(plot.get("density") or 0.5)
            ...
    """
    from .base import context

    block = getattr(context, "cityBlock", None)
    if block is None:
        if default is None:
            return {}
        return dict(default)
    # Shallow copy so rule code cannot accidentally mutate session state.
    if isinstance(block, Mapping):
        return dict(block)
    return block


def city_block_at_import(default: Optional[Mapping[str, Any]] = None):
    """
    Explicit import-time read with a DeprecationWarning.

    Existing rules that must bind module-level constants from the plot can
    call this to acknowledge the legacy pattern. New rules should use
    city_block() inside Begin() instead.
    """
    warnings.warn(_IMPORT_TIME_WARNING, DeprecationWarning, stacklevel=2)
    return city_block(default, _warn_stacklevel=3)
