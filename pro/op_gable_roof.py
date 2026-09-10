from .rule_context import resolve_rule_context
from .base import Operator, ComplexOperator, context, countOperator


def gable_roof(*args, **kwargs):
    return resolve_rule_context().factory["GableRoof"](*args, **kwargs)


class GableRoof(ComplexOperator):
    """
    Gable roof: a pair of opposite slopes, the other pair vertical (90 deg).
    Same call shape as hip_roof(pitch[, soffit], face>>..., fascia>>..., ...).
    Only rectangular (4-edge) footprints are supported by the Blender impl.
    """
    def __init__(self, *args, **kwargs):
        self.pitch = 35.0
        self.soffitSize = None
        self.fasciaSize = kwargs.get("fasciaSize")
        self.face = None
        self.soffit = None
        self.fascia = None
        numeric = []
        numOperators = 0
        for arg in args:
            if isinstance(arg, Operator):
                if hasattr(arg, "value") and isinstance(arg.value, str):
                    setattr(self, arg.value, arg)
                if countOperator(arg):
                    numOperators += 1
            else:
                numeric.append(arg)
        if numeric:
            self.bind_param("pitch", numeric[0], resolve=float)
        if len(numeric) > 1:
            self.bind_param("soffitSize", numeric[1], resolve=float)
        for k in ("face", "soffit", "fascia"):
            if k in kwargs:
                setattr(self, k, kwargs[k])
        super().__init__(numOperators)
