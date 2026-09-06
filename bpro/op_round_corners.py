import bmesh
import pro
from pro import context


class RoundCorners(pro.op_round_corners.RoundCorners):
    def execute(self):
        # ponytail: bevel invalidates the footprint BMFace/loops that extrude()
        # still holds; skip rather than leave a dead face for the next op
        return
