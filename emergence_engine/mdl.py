from __future__ import annotations

from math import log2, floor
from typing import Dict, List, Tuple

from .grammar import Grammar


def _safe_log2(x: int) -> float:
    return log2(max(2, x))


def elias_gamma_length(n: int) -> int:
    """Bit-length of Elias gamma code for positive integer n (n>=1).

    For n<=0, we map to 1 to keep things defined.
    L(n) = 2*floor(log2(n)) + 1
    """
    if n <= 0:
        n = 1
    return 2 * floor(log2(n)) + 1


class MDLScorer:
    """Explicit two-part MDL with simple universal codes.

    - Grammar cost (lightweight):
      - Sum log2(V) for symbols in each RHS.
      - We intentionally omit explicit costs for number of rules,
        RHS length headers, and rule frequency to avoid over-penalizing
        simple, highly-repetitive cases.
    - Data cost:
      - Encode sequence length via gamma(n)
      - Then n * log2(V) to emit symbol indices

    V = |Σ ∪ N|, vocabulary size (terminals + non-terminals)
    Σ size is provided via `terminals_size` when scoring.
    """

    def score_components(self, grammar: Grammar, compressed: List[str], terminals_size: int) -> Dict[str, float]:
        sigma = max(2, terminals_size)
        V = max(2, sigma + len(grammar.rules))
        sym_cost = _safe_log2(V)

        # Grammar cost: only pay for symbols appearing in RHS across rules
        grammar_cost = 0.0
        for rule in grammar.rules.values():
            rhs_len = len(rule.rhs)
            grammar_cost += rhs_len * sym_cost

        # Data cost
        n = len(compressed)
        data_cost = float(elias_gamma_length(n)) + n * sym_cost

        total = grammar_cost + data_cost
        return {"grammar_cost": grammar_cost, "data_cost": data_cost, "total": total}

    def score(self, grammar: Grammar, compressed: List[str], terminals_size: int | None = None) -> float:
        sigma = terminals_size if terminals_size is not None else max(2, len(grammar.terminals) or 2)
        return self.score_components(grammar, compressed, sigma)["total"]

    def naive_baseline(self, original_tokens: List[str]) -> float:
        sigma = max(2, len(set(original_tokens)) or 2)
        n = len(original_tokens)
        return float(elias_gamma_length(n)) + n * _safe_log2(sigma)

    def compression_ratio(self, original_tokens: List[str], compressed: List[str], grammar: Grammar) -> float:
        sigma = max(2, len(set(original_tokens)) or 2)
        original_size = self.naive_baseline(original_tokens)
        compressed_size = self.score(grammar, compressed, terminals_size=sigma)
        if compressed_size == 0:
            return 1.0
        return original_size / compressed_size

    def delta(self, before: Tuple[List[str], Grammar], after: Tuple[List[str], Grammar], terminals_size: int) -> float:
        b_seq, b_g = before
        a_seq, a_g = after
        return self.score(a_g, a_seq, terminals_size) - self.score(b_g, b_seq, terminals_size)
