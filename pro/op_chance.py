from .base import Operator, ComplexOperator
from .rule_context import resolve_rule_context, call_execute


def chance(*weighted_parts):
    """
    Stochastic rule selection: picks exactly ONE of the given
    (weight, operator_or_rule) pairs at random, weighted by the given
    weights (they don't need to sum to 1 -- they're normalized
    automatically against their total), and executes only that one.

    Example:
        chance(
            (0.6, BrickWall()),
            (0.3, StoneWall()),
            (0.1, PaintedWall()),
        )
    """
    return resolve_rule_context().factory["Chance"](*weighted_parts)


class Chance(ComplexOperator):
    def __init__(self, *weighted_parts):
        if not weighted_parts:
            raise ValueError("chance() needs at least one (weight, operator) pair")
        self.parts = weighted_parts
        numOperators = 0
        for weight, op in weighted_parts:
            if isinstance(op, Operator) and op.count:
                op.count = False
                numOperators += 1
        super().__init__(numOperators)

    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        weights = [w for w, _ in self.parts]
        total = sum(weights)
        if total <= 0:
            raise ValueError("chance() weights must sum to a positive number")
        # Use BCGA's session RNG (ctx.rng), not the process-global random
        # module, so set_seed() controls chance() the same way as random()/choice().
        r = ctx.rng.uniform(0, total)
        upto = 0.0
        chosen = self.parts[-1][1]
        for w, op in self.parts:
            upto += w
            if r <= upto:
                chosen = op
                break
        call_execute(chosen, ctx)
