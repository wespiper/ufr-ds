from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from emergence_engine.engine import EmergenceEngine

from .react_tokenizer import tokenize_project
from .tokenizer_node_bridge import has_node_tokenizer, tokenize_project_ast
from .families import discover_families, family_suggestions
from .engine_suggest import suggestions_from_rules
from .generator import generate_from_suggestions


def cmd_analyze(args: argparse.Namespace) -> int:
    # Input source precedence: --tokens JSON > AST tokenizer > regex tokenizer
    tokens: list[str]
    counts: dict[str, int]
    if getattr(args, 'tokens', None):
        data = json.loads(Path(args.tokens).read_text(encoding='utf-8'))
        tokens = list(data.get('tokens', []))
        counts = {
            'files': int(data.get('files', 0)),
            'tags': int(data.get('counts', {}).get('tags', 0)),
            'props': int(data.get('counts', {}).get('props', 0)),
            'components': int(data.get('counts', {}).get('components', 0)),
        }
    else:
        # Choose tokenizer
        use_ast = bool(args.ast) and has_node_tokenizer()
        if args.ast and not has_node_tokenizer():
            print("Warning: --ast requested but Node tokenizer not available; falling back to regex tokenizer.")
        tokens, counts = tokenize_project_ast(args.path) if use_ast else tokenize_project(args.path)

    # Bridge tokens to engine by joining with spaces (engine uses whitespace tokenizer)
    text = " ".join(tokens)

    engine = EmergenceEngine()
    result = engine.process(
        text,
        emergence=args.emergence,
        threshold=args.threshold,
        window=args.window,
        preset=args.emergence_preset,
        mode=args.emergence_mode,
        k=args.k,
        percentile=args.percentile,
        chars=False,
        min_persistence=args.min_persistence,
        hysteresis=args.hysteresis,
        min_gap=args.min_gap,
    )

    # Basic suggestions: list top tokens by frequency (tags/props)
    # Keep simple and useful for now
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1

    def top(prefix: str, n: int = 10) -> list[tuple[str, int]]:
        items = [(k.split(":", 1)[1], v) for k, v in freq.items() if k.startswith(prefix)]
        return sorted(items, key=lambda kv: kv[1], reverse=True)[:n]

    fams = discover_families(args.path)
    suggestions = family_suggestions(fams)

    payload = {
        "input": {
            "path": str(args.path),
            "files": counts["files"],
            "tokens": len(tokens),
            "tags": counts["tags"],
            "props": counts["props"],
            "components": counts["components"],
        },
        "engine": {
            "compression_ratio": result.compression_ratio,
            "mdl_score": result.mdl_score,
            "mdl_grammar_cost": result.mdl_grammar_cost,
            "mdl_data_cost": result.mdl_data_cost,
            "naive_mdl": result.naive_mdl,
            "coverage": result.coverage,
            "valid_lossless": result.valid_lossless,
        },
        "patterns": {
            "rules": result.rules,
            "top_tags": top("TAG:"),
            "top_props": top("PROP:"),
            "top_components": top("IMPORT:"),
        },
        "families": {
            "count": len(fams),
            "suggestions": suggestions,
        },
    }

    if args.emergence:
        payload["emergence"] = {
            "entropies": result.entropies,
            "events": result.events,
            "mdl_trajectory": getattr(result, "mdl_trajectory", None),
        }

    # Exports
    try:
        if args.export_graphviz:
            from emergence_engine.viz import grammar_to_dot
            # Rebuild Grammar from rules
            from emergence_engine.grammar import Grammar
            g = Grammar()
            for lhs, rhs in result.rules.items():
                g.add_rule(lhs, list(rhs))
            args.export_graphviz.write_text(grammar_to_dot(g), encoding="utf-8")
        if args.export_trajectory and args.emergence:
            from emergence_engine.viz import trajectory_to_plotly_json
            if result.entropies and getattr(result, "mdl_trajectory", None):
                import json as _json
                args.export_trajectory.write_text(
                    _json.dumps(trajectory_to_plotly_json(result.entropies, result.mdl_trajectory), indent=2),
                    encoding="utf-8",
                )
    except Exception as e:  # non-fatal
        print(f"Warning: export failed: {e}")

    if args.pretty:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ufr", description="UFR-DS CLI (Emergence-powered)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Analyze a React project and report patterns")
    a.add_argument("path", type=Path, help="Path to React project root")
    a.add_argument("--ast", action="store_true", help="Use Babel AST tokenizer (requires Node + deps)")
    a.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    a.add_argument("--emergence", action="store_true", help="Compute entropy trajectory and events")
    a.add_argument("--threshold", type=float, default=0.25, help="Emergence normalized curvature threshold")
    a.add_argument("--window", type=int, default=1, help="Emergence detection window (reserved)")
    a.add_argument("--emergence-preset", choices=["sensitive", "balanced", "strict"], help="Preset for emergence detection")
    a.add_argument("--emergence-mode", choices=["static", "adaptive"], default="static", help="Static uses given/preset threshold; adaptive computes from data")
    a.add_argument("--k", type=float, default=3.0, help="Adaptive robust threshold multiplier (MAD)")
    a.add_argument("--percentile", type=float, default=0.9, help="Adaptive percentile (reserved)")
    a.add_argument("--min-persistence", type=int, default=2, help="Emergence: min consecutive steps above threshold")
    a.add_argument("--hysteresis", type=float, default=0.1, help="Emergence: hysteresis margin to end events")
    a.add_argument("--min-gap", type=int, default=2, help="Emergence: minimum gap between events")
    a.add_argument("--tokens", type=Path, help="Path to pre-tokenized JSON (from Node tokenizer)")
    a.set_defaults(func=cmd_analyze)

    # Optional exports for visualization
    a.add_argument("--export-graphviz", type=Path, help="Write final grammar GraphViz DOT to file")
    a.add_argument("--export-trajectory", type=Path, help="Write MDL trajectory + entropies JSON to file (requires --emergence)")

    g = sub.add_parser("generate", help="Generate canonical components from discovered families")
    g.add_argument("path", type=Path, help="Path to React project root (input for discovery)")
    g.add_argument("--out", type=Path, default=Path("generated"), help="Output directory for generated components")
    g.add_argument("--engine", action="store_true", help="Use engine-driven suggestions (analyze first)")
    g.add_argument("--ast", action="store_true", help="Use Babel AST tokenizer when analyzing for engine suggestions")
    g.add_argument("--tokens", type=Path, help="Path to pre-tokenized JSON (from Node tokenizer)")
    g.add_argument("--llm", choices=["openai", "anthropic"], help="Refine generated components with an LLM (optional)")
    g.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    g.set_defaults(func=cmd_generate)

    r = sub.add_parser("report", help="Write a Markdown report from analysis JSON")
    r.add_argument("analysis", type=Path, help="Path to JSON payload (from ufr analyze)")
    r.add_argument("--out", type=Path, default=Path("ufr-report.md"), help="Output Markdown file")
    r.add_argument("--llm", choices=["openai", "anthropic"], help="Augment report with LLM-written human-friendly summary")
    r.set_defaults(func=cmd_report)

    return p


def cmd_generate(args: argparse.Namespace) -> int:
    # Build suggestions
    suggestions: list[dict]
    if args.engine:
        # Obtain tokens for engine analysis if needed
        if args.tokens:
            data = json.loads(Path(args.tokens).read_text(encoding='utf-8'))
            tokens = list(data.get('tokens', []))
        else:
            use_ast = bool(args.ast) and has_node_tokenizer()
            if args.ast and not has_node_tokenizer():
                print("Warning: --ast requested but Node tokenizer not available; falling back to regex tokenizer.")
            tokens, _ = tokenize_project_ast(args.path) if use_ast else tokenize_project(args.path)
        # Run engine to get rules
        engine = EmergenceEngine()
        text = " ".join(tokens)
        result = engine.process(text, emergence=False, chars=False)
        suggestions = suggestions_from_rules(result.rules)
        # Fallback to heuristic if engine found nothing
        if not suggestions:
            fams = discover_families(args.path)
            suggestions = family_suggestions(fams)
    else:
        fams = discover_families(args.path)
        suggestions = family_suggestions(fams)

    files = generate_from_suggestions(suggestions, args.out, llm_provider=args.llm)
    payload = {
        "generated": files,
        "suggestions": suggestions,
    }
    if args.pretty:
        import json
        print(json.dumps(payload, indent=2))
    else:
        import json
        print(json.dumps(payload))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


def cmd_report(args: argparse.Namespace) -> int:
    from .report import render_markdown_report, render_llm_summary
    data = json.loads(Path(args.analysis).read_text(encoding='utf-8'))
    md = render_markdown_report(data)
    if args.llm:
        summary = render_llm_summary(data, args.llm)
        if summary:
            md += "\n\n## Human Summary (LLM)\n\n" + summary + "\n"
        else:
            md += "\n\n_note: LLM summary unavailable (no API key or provider error)._\n"
    args.out.write_text(md, encoding='utf-8')
    print(f"Wrote report to {args.out}")
    return 0
