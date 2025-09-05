from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .llm import generate_text


def render_markdown_report(payload: dict) -> str:
    inp = payload.get("input", {})
    eng = payload.get("engine", {})
    pats = payload.get("patterns", {})
    fams = payload.get("families", {})
    lines: List[str] = []
    lines.append(f"# UFR Analysis Report\n")
    lines.append(f"## Input\n")
    lines.append(f"- Path: `{inp.get('path','')}`\n")
    lines.append(f"- Files: {inp.get('files',0)}  Tokens: {inp.get('tokens',0)}\n")
    lines.append(f"- Tags: {inp.get('tags',0)}  Props: {inp.get('props',0)}  Components: {inp.get('components',0)}\n")
    lines.append(f"\n## Engine\n")
    lines.append(f"- Compression ratio: {eng.get('compression_ratio')}\n")
    lines.append(f"- MDL total: {eng.get('mdl_score')} (grammar: {eng.get('mdl_grammar_cost')}, data: {eng.get('mdl_data_cost')})\n")
    lines.append(f"- Coverage: {eng.get('coverage')}  Lossless: {eng.get('valid_lossless')}\n")
    lines.append(f"\n## Top Tags\n")
    for name, count in (pats.get('top_tags') or [])[:10]:
        lines.append(f"- {name}: {count}\n")
    lines.append(f"\n## Top Props\n")
    for name, count in (pats.get('top_props') or [])[:10]:
        lines.append(f"- {name}: {count}\n")
    lines.append(f"\n## Family Suggestions\n")
    for s in (fams.get('suggestions') or [])[:20]:
        lines.append(f"- {s.get('family')}: variants={s.get('suggested_variant_values')} props={s.get('top_props')} members={s.get('members')}\n")
    return "".join(lines)


def render_llm_summary(payload: dict, provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    inp = payload.get("input", {})
    eng = payload.get("engine", {})
    pats = payload.get("patterns", {})
    fams = payload.get("families", {})
    # Build a compact structured brief for the model
    brief = {
        "files": inp.get("files"),
        "tokens": inp.get("tokens"),
        "compression_ratio": eng.get("compression_ratio"),
        "coverage": eng.get("coverage"),
        "valid_lossless": eng.get("valid_lossless"),
        "top_tags": (pats.get("top_tags") or [])[:10],
        "top_props": (pats.get("top_props") or [])[:10],
        "suggestions": (fams.get("suggestions") or [])[:10],
    }
    prompt = f"""
You are a senior design systems engineer. Given this analysis, write a concise, human-friendly summary with:
- Key patterns and what they imply (2-4 bullets)
- Suggested consolidations (families and likely variant axes)
- Risks and migration notes (1-2 bullets)
- Clear next actions for the team

Keep it pragmatic and specific to the data. Avoid hype.

Analysis JSON:
{brief}
"""
    return generate_text(prompt, provider)
