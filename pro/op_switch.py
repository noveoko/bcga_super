from .base import Operator, ComplexOperator
from .rule_context import resolve_rule_context, call_execute


def switch(value, cases, default=None):
    """
    Conditional branch: executes the operator/rule in cases[value] if
    present, otherwise `default` (if given -- otherwise nothing happens).
    `value` can be a plain Python value, or anything that resolves via
    str()/comparison (e.g. a param's .getValue(), or the result of
    choice()/random()).

    Example, picking a roof style by a resolved building width:
        switch(
            "narrow" if WIDTH.getValue() < 10 else "wide",
            {
                "narrow": gable_roof(35),
                "wide": hip_roof(25, 25, 25, 25),
            },
        )

    Example, branching on a discrete choice():
        STYLE = choice("modern", "classic", "industrial")
        switch(STYLE.getValue(), {
            "modern": ModernFacade(),
            "classic": ClassicFacade(),
            "industrial": IndustrialFacade(),
        }, default=ModernFacade())
    """
    return resolve_rule_context().factory["Switch"](value, cases, default)


class Switch(ComplexOperator):
    def __init__(self, value, cases, default=None):
        self.switchValue = value
        self.cases = cases
        self.default = default
        numOperators = 0
        candidates = list(cases.values()) + ([default] if default is not None else [])
        for op in candidates:
            if isinstance(op, Operator) and op.count:
                op.count = False
                numOperators += 1
        super().__init__(numOperators)

    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        keys = list(self.cases.keys())
        if self.switchValue in self.cases:
            selected = keys.index(self.switchValue)
            chosen = self.cases[self.switchValue]
        else:
            selected = None
            chosen = self.default
        self.bind_param("switchValue", self.switchValue, resolve=None)
        self.bind_param("selected", selected, resolve=None)
        if chosen is not None:
            call_execute(chosen, ctx)
