from .rule_context import resolve_rule_context
from .base import ComplexOperator, context, countOperator

def copy(operator=None, **kwargs):
    return resolve_rule_context().factory["Copy"](operator, **kwargs)

class Copy(ComplexOperator):
    def __init__(self, operator, **kwargs):
        self.operator = operator
        numOperators = 1 if countOperator(operator) else 0
        super().__init__(numOperators)