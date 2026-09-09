import bmesh
import pro
from pro import context
from pro.rule_context import resolve_rule_context


class RoundCorners(pro.op_round_corners.RoundCorners):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        # ponytail: bevel invalidates the footprint BMFace/loops that extrude()
        # still holds; skip rather than leave a dead face for the next op
        return
