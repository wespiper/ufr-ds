from dataclasses import dataclass


@dataclass(frozen=True)
class Symbol:
    """Simple symbol wrapper (type, value).

    For now, we mostly use string values; `kind` can distinguish terminals vs non-terminals.
    """

    value: str
    kind: str = "terminal"  # or "nonterminal"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

