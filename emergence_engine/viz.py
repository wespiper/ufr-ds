from __future__ import annotations

from typing import Dict, List

from .grammar import Grammar


def grammar_to_dot(grammar: Grammar) -> str:
    """Render a simple GraphViz DOT for the grammar rules.

    Each rule LHS -> RHS is represented as a node for LHS and edges to each RHS symbol.
    Terminals are boxed; non-terminals are ellipses.
    """
    lines: List[str] = ["digraph Grammar {", "  rankdir=LR;"]
    # Declare nodes
    nts = set(grammar.non_terminals.keys())
    ts = set(grammar.terminals.keys())
    for t in ts:
        lines.append(f'  "{t}" [shape=box, style=filled, fillcolor=lightgray];')
    for nt in nts:
        lines.append(f'  "{nt}" [shape=ellipse];')
    # Edges per rule
    for lhs, rule in grammar.rules.items():
        for sym in rule.rhs:
            lines.append(f'  "{lhs}" -> "{sym.value}";')
    lines.append("}")
    return "\n".join(lines)


def trajectory_to_plotly_json(entropies: List[float], mdl_traj: List[Dict[str, float]]) -> Dict:
    """Return a minimal Plotly-friendly JSON payload with entropy and MDL curves."""
    x = list(range(len(entropies)))
    total = [step["total"] for step in mdl_traj]
    data = [
        {"type": "scatter", "name": "Entropy", "x": x, "y": entropies, "yaxis": "y1"},
        {"type": "scatter", "name": "MDL Total", "x": x, "y": total, "yaxis": "y2"},
    ]
    layout = {
        "title": "Entropy and MDL Trajectory",
        "xaxis": {"title": "Step"},
        "yaxis": {"title": "Entropy"},
        "yaxis2": {"title": "MDL", "overlaying": "y", "side": "right"},
    }
    return {"data": data, "layout": layout}

