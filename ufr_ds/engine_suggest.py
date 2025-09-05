from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .families import base_name


Token = str
RuleMap = Dict[str, Tuple[Token, ...]]


def _expand_rule(rule: str, rules: RuleMap, seen: Set[str] | None = None) -> List[Token]:
    if seen is None:
        seen = set()
    if rule in seen:
        return []
    seen.add(rule)
    out: List[Token] = []
    rhs = rules.get(rule)
    if not rhs:
        return []
    for sym in rhs:
        if sym in rules:
            out.extend(_expand_rule(sym, rules, seen))
        else:
            out.append(sym)
    return out


def _terminals_for_rule(rule: str, rules: RuleMap) -> List[Token]:
    return [t for t in _expand_rule(rule, rules) if t.startswith(("TAG:", "PROP:", "IMPORT:"))]


def suggestions_from_rules(rules: RuleMap) -> List[dict]:
    """Build family suggestions using engine rules (co-occurrence based).

    - Expands rules transitively to terminal tokens
    - Groups TAG:<Name> by base name (Element, Button, etc.)
    - Aggregates co-occurring PROP:* as top props per family
    - Suggests variants from member name differences
    """
    # Collect per-tag props via co-occurrence across rules
    tag_to_props: Dict[str, Dict[str, int]] = {}
    tags_seen: Set[str] = set()
    for rname in list(rules.keys()):
        terminals = _terminals_for_rule(rname, rules)
        tags = [t for t in terminals if t.startswith("TAG:")]
        props = [p for p in terminals if p.startswith("PROP:")]
        for tag in tags:
            tags_seen.add(tag)
            tmap = tag_to_props.setdefault(tag, {})
            for p in props:
                name = p.split(":", 1)[1]
                tmap[name] = tmap.get(name, 0) + 1

    # Group tags into families by base name
    family_members: Dict[str, Set[str]] = {}
    family_props: Dict[str, Dict[str, int]] = {}
    for tag in tags_seen:
        name = tag.split(":", 1)[1]
        base, variant_hints = base_name(name)
        family_members.setdefault(base, set()).add(name)
        # Merge props
        fmap = family_props.setdefault(base, {})
        for p, c in tag_to_props.get(tag, {}).items():
            fmap[p] = fmap.get(p, 0) + c

    # Build suggestions
    suggestions: List[dict] = []
    for base, members in family_members.items():
        if len(members) <= 1:
            continue
        variant_names: Set[str] = set()
        for m in members:
            if m.endswith(base):
                variant_names.add(m[: -len(base)] or "default")
            elif m.startswith(base):
                variant_names.add(m[len(base) :] or "default")
            else:
                variant_names.add(m)
        top_props = sorted(family_props.get(base, {}).items(), key=lambda kv: kv[1], reverse=True)[:10]
        suggestions.append(
            {
                "family": base,
                "members": sorted(members),
                "suggested_variant_values": sorted(v for v in variant_names if v),
                "top_props": [p for p, _ in top_props],
                "source": "engine",
            }
        )
    return suggestions

