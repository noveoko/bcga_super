"""Phase 3: RuleContext injection and operator construction without dummy parent."""
from pro import context, RuleContext, resolve_rule_context, get_active_rule_context
from pro.base import Operator, Rule
from pro.rule_context import push_rule_context, reset_rule_context
from pro.op_chance import Chance


class _Mark(Operator):
    def __init__(self, name):
        self.name = name
        self.ran_with = None
        super().__init__()

    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        self.ran_with = ctx


def test_resolve_rule_context_wraps_ambient():
    ctx = resolve_rule_context()
    assert isinstance(ctx, RuleContext)
    context.set_seed(5)
    assert ctx.rng is context.rng


def test_operator_constructs_without_dummy_parent():
    # No install_dummy_operator — Phase 3 allows orphan construction.
    context.operator = None
    op = _Mark("solo")
    assert op.name == "solo"


def test_push_rule_context_makes_active():
    outer = resolve_rule_context()
    token = push_rule_context(outer)
    try:
        assert get_active_rule_context() is outer
        assert resolve_rule_context() is outer
    finally:
        reset_rule_context(token)
    assert get_active_rule_context() is None


def test_rule_execute_passes_ctx_to_children():
    marks = []

    def body():
        marks.append(_Mark("child"))

    # Dummy parent only for constructing the Rule itself
    class Parent:
        def addChildOperator(self, o):
            pass

        def removeChildOperators(self, n):
            pass

    context.operator = Parent()
    rule = Rule(body, (), {})
    ctx = resolve_rule_context()
    rule.execute(ctx)
    assert marks
    child = marks[0]
    assert child.ran_with is not None
    assert isinstance(child.ran_with, RuleContext)


def test_chance_execute_accepts_ctx():
    context.set_seed(3)
    hits = []

    class Hit(Operator):
        def execute(self, ctx=None):
            hits.append(resolve_rule_context(ctx))

    context.operator = None
    Chance((1.0, Hit())).execute()
    assert hits and isinstance(hits[0], RuleContext)
