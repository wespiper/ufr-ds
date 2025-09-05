from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Tuple

from .grammar import Grammar


class RePair:
    """RePair-style grammar inducer (recursive pair substitution).

    Algorithm (baseline implementation):
      1) Repeatedly find the most frequent adjacent pair (digram) in the sequence.
      2) If its frequency < 2, stop.
      3) Introduce a new non-terminal rule LHS -> (a, b) and replace all
         non-overlapping occurrences of (a, b) with LHS.
      4) After convergence, enforce rule utility: inline rules used <= 1 time.
      5) Compute rule usage counts.

    This is a pragmatic, readable version to bootstrap further optimization.
    """

    def __init__(self, prefix: str = "R") -> None:
        self.prefix = prefix

    def compress(self, tokens: List[str]) -> Tuple[List[str], Grammar]:
        sequence = list(tokens)
        grammar = Grammar()
        rule_id = 1

        while True:
            counts = self._digram_counts(sequence)
            if not counts:
                break
            digram, freq = max(counts.items(), key=lambda kv: kv[1])
            if freq < 2:
                break

            lhs = f"{self.prefix}{rule_id}"
            grammar.add_rule(lhs, [digram[0], digram[1]])
            rule_id += 1
            sequence = self._replace_all(sequence, digram, lhs)

        # Rule utility: inline rules used <= 1 time
        self._inline_singletons(sequence, grammar)

        # Compute usage counts for rules (in compressed seq + nested in RHS)
        self._update_rule_usage(sequence, grammar)

        return sequence, grammar

    def compress_trace(self, tokens: List[str]) -> List[Tuple[List[str], Grammar]]:
        """Run RePair and return snapshots after each replacement step.

        Note: snapshots are recorded before final singleton inlining; usage
        counts are updated for each snapshot to allow entropy/MDL measurement.
        The final step applies inlining and usage update and is also included.
        """
        sequence = list(tokens)
        grammar = Grammar()
        rule_id = 1
        snapshots: List[Tuple[List[str], Grammar]] = []

        while True:
            counts = self._digram_counts(sequence)
            if not counts:
                break
            digram, freq = max(counts.items(), key=lambda kv: kv[1])
            if freq < 2:
                break

            lhs = f"{self.prefix}{rule_id}"
            grammar.add_rule(lhs, [digram[0], digram[1]])
            rule_id += 1
            sequence = self._replace_all(sequence, digram, lhs)

            # Update usage for snapshot
            self._update_rule_usage(sequence, grammar)
            snapshots.append((list(sequence), grammar.clone()))

        # Finalize with inlining and update usage, include final snapshot
        self._inline_singletons(sequence, grammar)
        self._update_rule_usage(sequence, grammar)
        snapshots.append((list(sequence), grammar.clone()))
        return snapshots

    def reconstruct(self, compressed: List[str], grammar: Grammar) -> List[str]:
        """Expand compressed tokens using grammar rules until terminals only."""
        def expand_symbol(sym: str) -> List[str]:
            if sym in grammar.rules:
                rhs = [s for s in grammar.as_tuples()[sym]]
                out: List[str] = []
                for t in rhs:
                    out.extend(expand_symbol(t))
                return out
            return [sym]

        out: List[str] = []
        for t in compressed:
            out.extend(expand_symbol(t))
        return out

    @staticmethod
    def _digram_counts(sequence: List[str]) -> Dict[Tuple[str, str], int]:
        return Counter(zip(sequence, sequence[1:]))

    @staticmethod
    def _replace_all(sequence: List[str], digram: Tuple[str, str], lhs: str) -> List[str]:
        out: List[str] = []
        i = 0
        n = len(sequence)
        while i < n:
            if i < n - 1 and sequence[i] == digram[0] and sequence[i + 1] == digram[1]:
                out.append(lhs)
                i += 2
            else:
                out.append(sequence[i])
                i += 1
        return out

    def _inline_singletons(self, sequence: List[str], grammar: Grammar) -> None:
        # Repeat until no change: inline rules that appear <= 1 time across sequence and rules
        changed = True
        while changed and grammar.rules:
            changed = False
            usage = self._collect_symbol_usage(sequence, grammar)
            for lhs in list(grammar.rules.keys()):
                if usage.get(lhs, 0) <= 1:
                    rhs = list(grammar.as_tuples()[lhs])
                    # Inline once in sequence if present
                    if lhs in sequence:
                        idx = sequence.index(lhs)
                        sequence[idx:idx + 1] = rhs
                        changed = True
                    # Inline inside other rules
                    for r in grammar.rules.values():
                        if r.lhs.value == lhs:
                            continue
                        new_rhs: List[str] = []
                        for sym in [s.value for s in r.rhs]:
                            if sym == lhs:
                                new_rhs.extend(rhs)
                                changed = True
                            else:
                                new_rhs.append(sym)
                        r.rhs = [grammar._get_symbol(v) for v in new_rhs]
                    # Remove the rule
                    if lhs in grammar.rules:
                        del grammar.rules[lhs]

    def _collect_symbol_usage(self, sequence: List[str], grammar: Grammar) -> Dict[str, int]:
        usage: Dict[str, int] = Counter(sequence)
        for lhs, rule in grammar.rules.items():
            for sym in rule.rhs:
                usage[sym.value] = usage.get(sym.value, 0) + 1
        return usage

    def _update_rule_usage(self, sequence: List[str], grammar: Grammar) -> None:
        usage = self._collect_symbol_usage(sequence, grammar)
        # Count only uses of each LHS (not internal symbol frequency)
        for lhs, rule in grammar.rules.items():
            rule.frequency = usage.get(lhs, 0)
        # Optionally compute probabilities as normalized frequencies across rules
        total = sum(r.frequency for r in grammar.rules.values()) or 1
        for r in grammar.rules.values():
            r.probability = r.frequency / total
