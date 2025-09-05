from typing import Iterable, List


def simple_tokenize(text: str) -> List[str]:
    """Simple whitespace tokenizer.

    - Splits on any whitespace
    - Keeps punctuation as part of tokens
    """
    return [t for t in text.strip().split() if t]


def chars(text: str) -> List[str]:
    """Character-level tokenization (including spaces compressed to \x20)."""
    return [c if c != " " else "\x20" for c in text]

