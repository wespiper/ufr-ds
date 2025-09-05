from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .mdl import MDLScorer
from .repair import RePair
from .tokenizer import simple_tokenize, chars as char_tokens
from .emergence import EmergenceDetector


@dataclass
class EngineResult:
    compressed: List[str]
    rules: Dict[str, tuple]
    mdl_score: float
    compression_ratio: float
    mdl_grammar_cost: float
    mdl_data_cost: float
    naive_mdl: float
    coverage: float
    valid_lossless: bool
    entropies: Optional[List[float]] = None
    events: Optional[List[dict]] = None
    mdl_trajectory: Optional[List[Dict[str, float]]] = None
    windows_entropies: Optional[List[float]] = None
    windows_mdl: Optional[List[float]] = None
    window_events: Optional[List[dict]] = None


class EmergenceEngine:
    def __init__(self) -> None:
        self.tokenizer = simple_tokenize
        self.pattern_miner = RePair()
        self.mdl = MDLScorer()

    def process(
        self,
        input_text: str,
        *,
        emergence: bool = False,
        threshold: float = 0.25,
        window: int = 1,
        preset: str | None = None,
        mode: str = "static",
        k: float = 3.0,
        percentile: float = 0.9,
        chars: bool = False,
        min_persistence: int = 2,
        hysteresis: float = 0.1,
        min_gap: int = 2,
    ) -> EngineResult:
        tokens = (char_tokens(input_text) if chars else self.tokenizer(input_text))
        if emergence:
            snapshots = self.pattern_miner.compress_trace(tokens)
            # Use last snapshot as final compressed+grammar
            compressed, grammar = snapshots[-1]
        else:
            compressed, grammar = self.pattern_miner.compress(tokens)
        sigma = len(set(tokens)) or 2
        mdl_components = self.mdl.score_components(grammar, compressed, sigma)
        mdl_score = mdl_components["total"]
        ratio = self.mdl.compression_ratio(tokens, compressed, grammar)

        # Reconstruction and coverage
        reconstructed = self.pattern_miner.reconstruct(compressed, grammar)
        valid_lossless = reconstructed == tokens
        total_tokens = len(reconstructed) if reconstructed else len(tokens)
        covered = 0
        for sym in compressed:
            if sym in grammar.rules:
                # count expansion size as covered
                # Expand one level: sum of terminals in full expansion
                # We can reuse reconstruction of [sym]
                covered += len(self.pattern_miner.reconstruct([sym], grammar))
        coverage = (covered / total_tokens) if total_tokens > 0 else 0.0

        naive = self.mdl.naive_baseline(tokens)
        result = EngineResult(
            compressed=compressed,
            rules={k: tuple(v) for k, v in grammar.as_tuples().items()},
            mdl_score=mdl_score,
            compression_ratio=ratio,
            mdl_grammar_cost=mdl_components["grammar_cost"],
            mdl_data_cost=mdl_components["data_cost"],
            naive_mdl=naive,
            coverage=coverage,
            valid_lossless=valid_lossless,
        )
        if emergence:
            detector = EmergenceDetector(
                threshold=threshold,
                window=window,
                preset=preset,
                mode=mode,
                k=k,
                percentile=percentile,
                min_persistence=min_persistence,
                hysteresis=hysteresis,
                min_gap=min_gap,
            )
            grammars = [g for _, g in snapshots]
            det = detector.detect(grammars)
            # Convert events to plain dicts for JSON friendliness
            result.entropies = det["entropies"]
            # MDL trajectory
            sigma = len(set(tokens)) or 2
            result_mdl = []
            for seq, gram in snapshots:
                comps = self.mdl.score_components(gram, seq, sigma)
                result_mdl.append({"grammar": comps["grammar_cost"], "data": comps["data_cost"], "total": comps["total"]})
            # Grammar differencing for events: compare grammars[i-1] to grammars[i+1]
            def rules_added(prev: Dict[str, tuple], nxt: Dict[str, tuple]) -> list[str]:
                return sorted([lhs for lhs in nxt.keys() if lhs not in prev])

            events_dicts = []
            for e in det["events"]:
                idx = e.index
                if 1 <= idx < len(grammars) - 1:
                    prev = grammars[idx - 1].as_tuples()
                    nxt = grammars[idx + 1].as_tuples()
                    e.rules_added = rules_added(prev, nxt)
                events_dicts.append(
                    {
                        "index": e.index,
                        "magnitude": e.magnitude,
                        "kind": e.kind,
                        "entropy_before": e.entropy_before,
                        "entropy_after": e.entropy_after,
                        "rules_added": e.rules_added,
                    }
                )
            result.events = events_dicts
            result.entropies = det["entropies"]
            # Attach MDL trajectory
            # Using attribute injection since dataclass already defined. Add to dict payload in CLI.
            result.mdl_trajectory = result_mdl
        return result

    def process_sliding(
        self,
        input_text: str,
        *,
        window_size: int,
        step: int,
        threshold: float = 0.25,
        preset: str | None = None,
        mode: str = "static",
        k: float = 3.0,
        percentile: float = 0.9,
        chars: bool = False,
        min_persistence: int = 2,
        hysteresis: float = 0.1,
        min_gap: int = 2,
    ) -> EngineResult:
        tokens = (char_tokens(input_text) if chars else self.tokenizer(input_text))
        # Build token windows
        windows: List[List[str]] = []
        for start in range(0, max(0, len(tokens) - window_size + 1), max(1, step)):
            windows.append(tokens[start : start + window_size])
        if not windows:
            windows = [tokens]

        grammars: List = []
        mdl_totals: List[float] = []
        entropies: List[float] = []

        sigma = len(set(tokens)) or 2
        last_compressed: List[str] = []
        last_grammar = None
        # Process each window independently
        for w in windows:
            compressed, grammar = self.pattern_miner.compress(w)
            comps = self.mdl.score_components(grammar, compressed, sigma)
            mdl_totals.append(comps["total"])
            grammars.append(grammar)
            # Entropy will be computed by detector; we also collect coverage and validity only for last window for summary
            last_compressed, last_grammar = compressed, grammar

        # For summary fields, use last window recon/coverage
        reconstructed = self.pattern_miner.reconstruct(last_compressed, last_grammar) if last_grammar else []
        valid_lossless = reconstructed == (windows[-1] if windows else [])
        total_tokens = len(reconstructed) if reconstructed else len(windows[-1])
        covered = 0
        for sym in (last_compressed or []):
            if last_grammar and sym in last_grammar.rules:
                covered += len(self.pattern_miner.reconstruct([sym], last_grammar))
        coverage = (covered / total_tokens) if total_tokens > 0 else 0.0

        # Naive vs final window MDL
        naive = self.mdl.naive_baseline(windows[-1] if windows else [])

        # Detect events across windows using grammars per window
        detector = EmergenceDetector(
            threshold=threshold,
            window=1,
            preset=preset,
            mode=mode,
            k=k,
            percentile=percentile,
            min_persistence=min_persistence,
            hysteresis=hysteresis,
            min_gap=min_gap,
        )
        det = detector.detect(grammars)

        # Compute rules_added across adjacent windows for event attribution
        events_dicts: List[dict] = []
        for e in det["events"]:
            idx = e.index
            rules_added: List[str] = []
            if 1 <= idx < len(grammars) - 1:
                prev = grammars[idx - 1].as_tuples()
                nxt = grammars[idx + 1].as_tuples()
                rules_added = sorted([lhs for lhs in nxt.keys() if lhs not in prev])
            events_dicts.append(
                {
                    "index": idx,
                    "magnitude": e.magnitude,
                    "kind": e.kind,
                    "entropy_before": e.entropy_before,
                    "entropy_after": e.entropy_after,
                    "rules_added": rules_added,
                }
            )

        # Build a result-like object using final window compressed/grammar for core metrics
        result = EngineResult(
            compressed=last_compressed or [],
            rules={k: tuple(v) for k, v in (last_grammar.as_tuples() if last_grammar else {}).items()},
            mdl_score=mdl_totals[-1] if mdl_totals else 0.0,
            compression_ratio=self.mdl.compression_ratio(windows[-1] if windows else [], last_compressed or [], last_grammar) if last_grammar else 1.0,
            mdl_grammar_cost=0.0,
            mdl_data_cost=0.0,
            naive_mdl=naive,
            coverage=coverage,
            valid_lossless=valid_lossless,
            entropies=det["entropies"],
            events=events_dicts,
            mdl_trajectory=None,
            windows_entropies=det["entropies"],
            windows_mdl=mdl_totals,
            window_events=events_dicts,
        )
        return result
