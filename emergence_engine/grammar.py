from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .symbols import Symbol


@dataclass
class ProductionRule:
    lhs: Symbol  # non-terminal
    rhs: List[Symbol]
    frequency: int = 0
    probability: float = 0.0


@dataclass
class Grammar:
    rules: Dict[str, ProductionRule] = field(default_factory=dict)
    terminals: Dict[str, Symbol] = field(default_factory=dict)
    non_terminals: Dict[str, Symbol] = field(default_factory=dict)
    start_symbol: Symbol = field(default_factory=lambda: Symbol("S", kind="nonterminal"))

    def add_rule(self, lhs_name: str, rhs_values: List[str]) -> ProductionRule:
        if lhs_name not in self.non_terminals:
            self.non_terminals[lhs_name] = Symbol(lhs_name, kind="nonterminal")
        lhs = self.non_terminals[lhs_name]
        rhs = [self._get_symbol(v) for v in rhs_values]
        rule = ProductionRule(lhs=lhs, rhs=rhs)
        self.rules[lhs_name] = rule
        return rule

    def _get_symbol(self, value: str) -> Symbol:
        if value in self.non_terminals:
            return self.non_terminals[value]
        if value in self.terminals:
            return self.terminals[value]
        # default new terminals
        sym = Symbol(value, kind="nonterminal" if value.isupper() else "terminal")
        if sym.kind == "terminal":
            self.terminals[value] = sym
        else:
            self.non_terminals[value] = sym
        return sym

    def encode_sequence(self, sequence: List[str]) -> List[str]:
        """Naive encoding: assumes `sequence` already compressed into rule references.

        This method is primarily used by the MDL scorer as a placeholder.
        """
        return list(sequence)

    def as_tuples(self) -> Dict[str, Tuple[str, ...]]:
        return {lhs: tuple(sym.value for sym in rule.rhs) for lhs, rule in self.rules.items()}

    def clone(self) -> "Grammar":
        g = Grammar()
        # Recreate non-terminals/terminals maps based on current symbols
        for name in self.non_terminals:
            g.non_terminals[name] = Symbol(name, kind="nonterminal")
        for name in self.terminals:
            g.terminals[name] = Symbol(name, kind="terminal")
        # Copy rules
        for lhs, rule in self.rules.items():
            g.add_rule(lhs, [sym.value for sym in rule.rhs])
            g.rules[lhs].frequency = rule.frequency
            g.rules[lhs].probability = rule.probability
        return g
