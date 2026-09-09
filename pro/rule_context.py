"""
RuleContext — typed view of execution state for operators (Phase 3).

Operators prefer `execute(self, ctx=None)` and `resolve_rule_context(ctx)`.
When ctx is omitted, the active ContextVar (set by Rule.execute) or the
ambient `pro.context` proxy is used, so unmigrated call paths keep working.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_active_rule_context: ContextVar[Optional["RuleContext"]] = ContextVar(
    "bcga_rule_context", default=None
)


class RuleContext:
    """
    Thin typed façade over a Context instance.

    Exposes the same attributes operators already use (stack, bm, factory,
    rng, …) while making the dependency explicit at execute() time.
    """

    __slots__ = ("_ctx",)

    def __init__(self, ctx):
        object.__setattr__(self, "_ctx", ctx)

    @property
    def ctx(self):
        """Underlying Context / session context."""
        return self._ctx

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    def __setattr__(self, name, value):
        if name == "_ctx":
            object.__setattr__(self, name, value)
        else:
            setattr(self._ctx, name, value)

    def __delattr__(self, name):
        delattr(self._ctx, name)


def get_active_rule_context() -> Optional[RuleContext]:
    return _active_rule_context.get()


def resolve_rule_context(explicit=None) -> RuleContext:
    """
    Resolve the RuleContext for an operator execution.

    Priority: explicit arg → ContextVar → ambient pro.context proxy/default.
    """
    if explicit is not None:
        if isinstance(explicit, RuleContext):
            return explicit
        return RuleContext(explicit)

    current = _active_rule_context.get()
    if current is not None:
        return current

    # Fall back to the module-level context proxy (session-aware).
    from .base import context
    target = context._target() if hasattr(context, "_target") else context
    return RuleContext(target)


def push_rule_context(ctx: RuleContext):
    """Activate ctx for nested operator execution; returns a reset token."""
    return _active_rule_context.set(ctx)


def reset_rule_context(token):
    _active_rule_context.reset(token)


def ambient_operator_parent():
    """
    Parent operator for Operator.__init__ child registration, or None when
    constructing operators outside a rule body (unit tests, etc.).
    """
    ctx = resolve_rule_context()
    return getattr(ctx, "operator", None)


def call_execute(op, ctx=None):
    """
    Invoke op.execute, passing RuleContext when the callee accepts it.

    Supports both Phase 3 signatures `execute(self, ctx=None)` and legacy
    `execute(self)` stubs used in older tests / unmigrated helpers.
    """
    ctx = resolve_rule_context(ctx)
    execute = getattr(op, "execute", None)
    if execute is None:
        return None
    try:
        return execute(ctx)
    except TypeError:
        return execute()
