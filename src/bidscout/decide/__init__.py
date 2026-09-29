"""Apply the rules. The rules are data; this package is the machinery."""

from bidscout.decide.engine import decide
from bidscout.decide.rules import RuleSet, load_rules

__all__ = ["RuleSet", "decide", "load_rules"]
