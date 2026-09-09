from .rule_context import resolve_rule_context
from .base import Operator, ComplexOperator, context, countOperator


def stairwell(rise, *args, **kwargs):
    """
    Stepped flight on the current rectangle, compiled into extrude2.

    rise (float): total climb in meters.
    tread / riser: target going and rise; risers are adjusted so n * riser == rise,
        and treads shrink if the rectangle is shorter than n * tread.

    Selectors are the same as extrude2: section, cap, cap1, cap2, last, middle.
    last defaults to delete() at execute time (drops extrude2's closing face
    back down to the original far edge at z=0).
    """
    return resolve_rule_context().factory["Stairwell"](rise, *args, **kwargs)


class Stairwell(ComplexOperator):
    def __init__(self, rise, *args, **kwargs):
        self.rise = float(rise)
        self.tread = float(kwargs.get("tread", 0.27))
        self.riser = float(kwargs.get("riser", 0.18))

        self.relativeCoord1 = False
        self.relativeCoord2 = False
        self.inheritMaterialAll = True
        self.inheritMaterialSection = False
        self.inheritMaterialCap = False
        self.keepOriginal = False
        self.symmetric = False
        self.axis = kwargs.get("axis", None)
        self.flipNormal = False
        self.section = None
        self.last = None
        self.cap1 = None
        self.cap2 = None
        self.cap = None
        self.original = None
        self.middle = None

        for k, v in kwargs.items():
            if k not in ("tread", "riser"):
                setattr(self, k, v)

        numOperators = 0
        for arg in args:
            if isinstance(arg, Operator):
                if hasattr(arg, "value") and isinstance(arg.value, str):
                    setattr(self, arg.value, arg)
                if countOperator(arg):
                    numOperators += 1
        super().__init__(numOperators)
