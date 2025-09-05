from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

from .grammar import Grammar


class Sequitur:
    """A simple SEQUITUR-inspired digram compressor.

    This is a pragmatic baseline: find most frequent digrams in the current
    sequence, introduce non-terminals, and replace all non-overlapping
    occurrences until no repeated digrams remain.
    """

    def __init__(self) -> None:
        self.rule_prefix = "R"

    def compress(self, tokens: List[str]) -> Tuple[List[str], Grammar]:
        sequence = list(tokens)
        grammar = Grammar()
        rule_counter = 1

        while True:
            counts = self._digram_counts(sequence)
            if not counts:
                break

            # Find the most frequent digram (freq >= 2)
            digram, freq = max(counts.items(), key=lambda kv: kv[1])
            if freq < 2:
                break

            # Introduce or reuse a rule for this digram
            lhs = f"{self.rule_prefix}{rule_counter}"
            grammar.add_rule(lhs, [digram[0], digram[1]])
            rule_counter += 1

            # Replace all non-overlapping occurrences
            sequence = self._replace_digram(sequence, digram, lhs)

        # Simple rule utility: inline rules that occur only once
        changed = True
        while changed:
            changed = False
            for lhs, rhs in list(grammar.as_tuples().items()):
                occurrences = sequence.count(lhs)
                if occurrences <= 1:
                    # Inline once and drop the rule
                    if occurrences == 1:
                        sequence = self._inline_once(sequence, lhs, list(rhs))
                    if lhs in grammar.rules:
                        del grammar.rules[lhs]
                    changed = True

        return sequence, grammar

    @staticmethod
    def _digram_counts(sequence: List[str]) -> Dict[Tuple[str, str], int]:
        counts: Dict[Tuple[str, str], int] = {}
        for i in range(len(sequence) - 1):
            digram = (sequence[i], sequence[i + 1])
            counts[digram] = counts.get(digram, 0) + 1
        return counts

    @staticmethod
    def _replace_digram(sequence: List[str], digram: Tuple[str, str], symbol: str) -> List[str]:
        out: List[str] = []
        i = 0
        n = len(sequence)
        while i < n:
            if i < n - 1 and sequence[i] == digram[0] and sequence[i + 1] == digram[1]:
                out.append(symbol)
                i += 2
            else:
                out.append(sequence[i])
                i += 1
        return out

    @staticmethod
    def _inline_once(sequence: List[str], lhs: str, rhs: List[str]) -> List[str]:
        out: List[str] = []
        inlined = False
        for tok in sequence:
            if not inlined and tok == lhs:
                out.extend(rhs)
                inlined = True
            else:
                out.append(tok)
        return out

