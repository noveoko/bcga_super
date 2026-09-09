from .rule_context import resolve_rule_context
from .base import context

def delete():
    """
    Deletes the shape
    """
    return resolve_rule_context().factory["Delete"]()