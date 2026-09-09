"""Shared test helpers for BCGA ambient-context setup."""


class DummyOperatorParent:
    """Minimal parent so Operator.__init__ can register child operators."""

    def addChildOperator(self, o):
        pass

    def removeChildOperators(self, n):
        pass


def install_dummy_operator(ctx=None):
    """
    Install a dummy context.operator so constructing Operator/Rule/Chance
    instances registers as children (optional since Phase 3).

    Phase 3+: Operator.__init__ no longer requires a parent; this helper
    remains for tests that assert child-operator bookkeeping.
    """
    from pro import context as default_context

    if ctx is None:
        ctx = default_context
    parent = DummyOperatorParent()
    ctx.operator = parent
    return parent
