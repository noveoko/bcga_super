import pro
from pro import context
from .polygon import Roof
from .polygon_manager import Manager
from .bl_util import get_roof_shape


class GableRoof(pro.op_gable_roof.GableRoof):
    def execute(self):
        shape = context.getState().shape
        roofShape = get_roof_shape(shape)
        face = roofShape.face
        verts = list(face.verts)
        numEdges = len(verts)
        if numEdges != 4:
            raise ValueError(
                "gable_roof() only supports rectangular (4-edge) footprints; "
                "this shape has %d edges. Use hip_roof(...) with an explicit "
                "pitch per edge for anything else." % numEdges
            )

        # measure each edge length to decide which pair of opposite edges
        # gets the slope (the longer pair, by convention)
        lengths = [
            (verts[i].co - verts[(i + 1) % numEdges].co).length
            for i in range(numEdges)
        ]
        pairA = lengths[0] + lengths[2]  # edges 0 and 2 are opposite
        pairB = lengths[1] + lengths[3]  # edges 1 and 3 are opposite
        pitch = self.pitch
        pitches = (pitch, 90, pitch, 90) if pairA >= pairB else (90, pitch, 90, pitch)

        manager = Manager()
        roof = Roof(face.verts, roofShape.getNormal(), manager)
        if self.soffitSize:
            manager.rule = self.soffit
            roof.inset(self.soffitSize, negate=True)
        if self.fasciaSize:
            manager.rule = self.fascia
            roof.translate(self.fasciaSize)
        manager.rule = self.face
        roof.roof(*pitches)
        roofShape.delete()
        for entry in manager.shapes:
            context.pushState(shape=entry[0])
            entry[1].execute()
            context.popState()
