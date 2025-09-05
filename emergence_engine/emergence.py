from __future__ import annotations

from dataclasses import dataclass
from math import log2
from typing import Dict, List, Tuple, Optional

from .grammar import Grammar


def compute_entropy(grammar: Grammar) -> float:
    """Shannon entropy (bits) over rule usage frequencies.

    If there are no rules or zero total frequency, returns 0.0.
    """
    total = sum(r.frequency for r in grammar.rules.values())
    if total <= 0:
        return 0.0
    H = 0.0
    for r in grammar.rules.values():
        if r.frequency <= 0:
            continue
        p = r.frequency / total
        H -= p * log2(p)
    return H


@dataclass
class EmergenceEvent:
    index: int
    magnitude: float
    kind: str  # 'emergence' or 'dissolution'
    entropy_before: float
    entropy_after: float
    rules_added: List[str]


class EmergenceDetector:
    def __init__(
        self,
        threshold: float = 0.25,
        window: int = 1,
        *,
        preset: Optional[str] = None,
        mode: str = "static",  # 'static' | 'adaptive'
        k: float = 3.0,
        percentile: float = 0.9,
        min_persistence: int = 2,
        hysteresis: float = 0.1,
        min_gap: int = 2,
    ) -> None:
        """Initialize detector.

        - threshold: normalized curvature threshold (abs(d2)/max_entropy)
        - window: derivative window (reserved)
        - preset: 'sensitive'|'balanced'|'strict' sets threshold if provided
        - mode: 'static' uses given/preset threshold; 'adaptive' computes from data
        - k: tuning parameter for robust/zscore modes (currently used for robust)
        - percentile: for percentile-based thresholding (not used yet)
        """
        self.threshold = threshold
        self.window = window
        self.preset = preset
        self.mode = mode
        self.k = k
        self.percentile = percentile
        self.min_persistence = max(1, int(min_persistence))
        self.hysteresis = max(0.0, float(hysteresis))
        self.min_gap = max(0, int(min_gap))

        if preset is not None:
            self.threshold = self._preset_threshold(preset)

    @staticmethod
    def _preset_threshold(name: str) -> float:
        name = name.lower()
        if name == "sensitive":
            return 0.15
        if name == "balanced":
            return 0.25
        if name == "strict":
            return 0.40
        return 0.25

    @staticmethod
    def _curvatures(entropies: List[float]) -> List[float]:
        if len(entropies) < 3:
            return []
        return [entropies[i + 1] - 2 * entropies[i] + entropies[i - 1] for i in range(1, len(entropies) - 1)]

    def threshold_from_entropies(self, entropies: List[float]) -> float:
        """Compute threshold for 'adaptive' mode using robust stats on curvature.

        thr = median(|d2|/max_entropy) + k * MAD(|d2|/max_entropy)
        Fallback to default threshold if insufficient points.
        """
        curv = self._curvatures(entropies)
        if len(curv) == 0:
            return self.threshold
        max_entropy = max(entropies) or 1.0
        values = [abs(c) / max_entropy for c in curv]
        med = _median(values)
        mad = _median([abs(v - med) for v in values])
        return med + self.k * mad

    def detect(self, grammars: List[Grammar]) -> Dict[str, List]:
        entropies = [compute_entropy(g) for g in grammars]
        events: List[EmergenceEvent] = []
        if len(entropies) < 3:
            return {"entropies": entropies, "events": events}

        thr = self.threshold if self.mode != "adaptive" else self.threshold_from_entropies(entropies)
        max_entropy = max(entropies) or 1.0

        # Persistence/hysteresis gating
        run = 0
        active = False
        last_event_idx = -10**9

        for i in range(1, len(entropies) - 1):
            d2 = entropies[i + 1] - 2 * entropies[i] + entropies[i - 1]
            norm = abs(d2) / max_entropy
            if norm >= thr:
                run += 1
            else:
                run = 0

            if not active and run >= self.min_persistence and (i - last_event_idx) >= self.min_gap:
                kind = "emergence" if d2 < 0 else "dissolution"
                events.append(
                    EmergenceEvent(
                        index=i,
                        magnitude=d2,
                        kind=kind,
                        entropy_before=entropies[i - 1],
                        entropy_after=entropies[i + 1],
                        rules_added=[],
                    )
                )
                active = True
                last_event_idx = i

            if active and norm <= max(0.0, thr - self.hysteresis):
                active = False

        return {"entropies": entropies, "events": events}


def _median(values: List[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    vs = sorted(values)
    mid = n // 2
    if n % 2 == 1:
        return vs[mid]
    return 0.5 * (vs[mid - 1] + vs[mid])
