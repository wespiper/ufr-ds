from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import EmergenceEngine


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="emergence", description="Emergence Engine CLI")
    p.add_argument("path", nargs="?", help="Path to input file (default: stdin)")
    p.add_argument("--chars", action="store_true", help="Character-level tokenization")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    p.add_argument("--emergence", action="store_true", help="Compute entropy trajectory and events")
    p.add_argument("--threshold", type=float, default=0.25, help="Emergence normalized curvature threshold")
    p.add_argument("--window", type=int, default=1, help="Emergence detection window (reserved)")
    p.add_argument("--emergence-preset", choices=["sensitive", "balanced", "strict"], help="Preset for emergence detection")
    p.add_argument("--emergence-mode", choices=["static", "adaptive"], default="static", help="Static uses given/preset threshold; adaptive computes from data")
    p.add_argument("--k", type=float, default=3.0, help="Adaptive robust threshold multiplier (MAD)")
    p.add_argument("--percentile", type=float, default=0.9, help="Adaptive percentile (reserved)")
    p.add_argument("--export-graphviz", help="Write final grammar GraphViz DOT to file")
    p.add_argument("--export-plotly", help="Write trajectory Plotly JSON to file")
    p.add_argument("--no-trajectory", action="store_true", help="With --emergence, omit mdl_trajectory from stdout JSON")
    p.add_argument("--summary", action="store_true", help="Print concise summary fields only")
    p.add_argument("--sliding-window", type=int, help="Analyze with sliding windows of this token length")
    p.add_argument("--sliding-step", type=int, default=0, help="Step between windows (default: window/2)")
    p.add_argument("--min-persistence", type=int, default=2, help="Emergence: min consecutive steps above threshold")
    p.add_argument("--hysteresis", type=float, default=0.1, help="Emergence: hysteresis margin to end events")
    p.add_argument("--min-gap", type=int, default=2, help="Emergence: minimum gap between events")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)

    text: str
    if args.path:
        text = Path(args.path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    engine = EmergenceEngine()
    # Sliding window mode
    if args.sliding_window:
        step = args.sliding_step if args.sliding_step > 0 else max(1, args.sliding_window // 2)
        result = engine.process_sliding(
            text,
            window_size=args.sliding_window,
            step=step,
            threshold=args.threshold,
            preset=args.emergence_preset,
            mode=args.emergence_mode,
            k=args.k,
            percentile=args.percentile,
            chars=args.chars,
            min_persistence=args.min_persistence,
            hysteresis=args.hysteresis,
            min_gap=args.min_gap,
        )
    else:
        result = engine.process(
            text,
            emergence=args.emergence,
            threshold=args.threshold,
            window=args.window,
            preset=args.emergence_preset,
            mode=args.emergence_mode,
            k=args.k,
            percentile=args.percentile,
            chars=args.chars,
            min_persistence=args.min_persistence,
            hysteresis=args.hysteresis,
            min_gap=args.min_gap,
        )

    if args.summary:
        payload = {
            "compression_ratio": result.compression_ratio,
            "mdl_score": result.mdl_score,
            "mdl_grammar_cost": result.mdl_grammar_cost,
            "mdl_data_cost": result.mdl_data_cost,
            "naive_mdl": result.naive_mdl,
            "coverage": result.coverage,
            "valid_lossless": result.valid_lossless,
            # Include compact emergence summary when requested
        }
    else:
        payload = {
            "compressed": result.compressed,
            "rules": result.rules,
            "mdl_score": result.mdl_score,
            "mdl_grammar_cost": result.mdl_grammar_cost,
            "mdl_data_cost": result.mdl_data_cost,
            "naive_mdl": result.naive_mdl,
            "compression_ratio": result.compression_ratio,
            "coverage": result.coverage,
            "valid_lossless": result.valid_lossless,
        }

    if args.emergence and not args.sliding_window:
        if args.summary:
            payload["entropies"] = {
                "count": len(result.entropies or []),
                "first": (result.entropies or [None])[0],
                "last": (result.entropies or [None])[-1],
            }
            payload["events_summary"] = {
                "count": len(result.events or []),
                "kinds": sorted({e.get("kind") for e in (result.events or [])}),
                "indices": [e.get("index") for e in (result.events or [])][:10],
            }
        else:
            payload["entropies"] = result.entropies
            payload["events"] = result.events
            if not args.no_trajectory:
                # Also include MDL trajectory unless suppressed
                payload["mdl_trajectory"] = getattr(result, "mdl_trajectory", None)
    # Sliding window outputs
    if args.sliding_window:
        if args.summary:
            payload["windows"] = {
                "count": len(result.windows_mdl or []),
                "first_mdl": (result.windows_mdl or [None])[0],
                "last_mdl": (result.windows_mdl or [None])[-1],
            }
            payload["window_events_summary"] = {
                "count": len(result.window_events or []),
                "kinds": sorted({e.get("kind") for e in (result.window_events or [])}),
                "indices": [e.get("index") for e in (result.window_events or [])][:10],
            }
        else:
            payload["windows_entropies"] = result.windows_entropies
            payload["windows_mdl"] = result.windows_mdl
            payload["window_events"] = result.window_events

        # Optional exports
        if args.export_graphviz:
            from .viz import grammar_to_dot
            try:
                from .grammar import Grammar
                g = Grammar()
                for lhs, rhs in result.rules.items():
                    g.add_rule(lhs, list(rhs))
                Path(args.export_graphviz).write_text(grammar_to_dot(g), encoding="utf-8")
            except Exception as e:
                print(f"Warning: failed to export GraphViz: {e}", file=sys.stderr)
        if args.export_plotly and payload.get("entropies") and payload.get("mdl_trajectory"):
            from .viz import trajectory_to_plotly_json
            try:
                import json as _json
                Path(args.export_plotly).write_text(
                    _json.dumps(trajectory_to_plotly_json(payload["entropies"], payload["mdl_trajectory"]), indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                print(f"Warning: failed to export Plotly JSON: {e}", file=sys.stderr)

    if args.pretty:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps(payload))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
