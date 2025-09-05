from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from .react_tokenizer import list_source_files, tokenize_file, TAG_OPEN_RE, PROP_RE


COMMON_PREFIXES = [
    "Primary",
    "Secondary",
    "Tertiary",
    "Quaternary",
    "Icon",
    "Fab",
    "Ghost",
    "Outline",
    "Filled",
    "Solid",
    "Link",
]

COMMON_SUFFIXES = [
    "Button",
    "Input",
    "Element",
    "Card",
    "Badge",
    "Chip",
    "Alert",
    "Modal",
    "Dialog",
]


def base_name(name: str) -> Tuple[str, List[str]]:
    """Compute a base name and variant hints from a component-like name.

    Heuristics:
    - If ends with a common suffix (e.g., IconButton, PrimaryButton), base is that suffix.
    - Else remove common prefixes (Primary, Secondary, Icon, etc.) to form base.
    - Return (base, variant_tokens)
    """
    for suf in COMMON_SUFFIXES:
        if name.endswith(suf) and name != suf:
            prefix = name[: -len(suf)]
            variants = [v for v in COMMON_PREFIXES if prefix.startswith(v)]
            variant = prefix if prefix else ""
            return suf, [variant] if variant else variants
    # try strip prefixes
    for pref in COMMON_PREFIXES:
        if name.startswith(pref) and len(name) > len(pref):
            return name[len(pref) :], [pref]
    return name, []


@dataclass
class Element:
    tag: str
    props: List[str] = field(default_factory=list)


def extract_elements_from_text(text: str) -> List[Element]:
    r"""Lightweight extraction of opening JSX tags and their prop names.

    This is a heuristic and may miss complex embedded expressions, but works well
    for common cases. It scans for opening tags and then collects \w-like prop names
    before the next '>' or '/>'.
    """
    elements: List[Element] = []
    for m in TAG_OPEN_RE.finditer(text):
        tag = m.group(1)
        start = m.end(1)
        # Scan ahead to the next closing angle bracket
        end = text.find('>', start)
        if end == -1:
            end = len(text)
        snippet = text[start:end]
        props = [pm.group(1) for pm in PROP_RE.finditer(snippet)]
        elements.append(Element(tag=tag, props=props))
    return elements


def extract_elements(root: Path) -> List[Element]:
    els: List[Element] = []
    for file in list_source_files(root):
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        els.extend(extract_elements_from_text(text))
    return els


@dataclass
class Family:
    base: str
    members: Set[str] = field(default_factory=set)
    props: Dict[str, int] = field(default_factory=dict)
    variants: Set[str] = field(default_factory=set)

    def add_member(self, name: str, props: List[str], variant_hints: List[str]) -> None:
        self.members.add(name)
        for p in props:
            self.props[p] = self.props.get(p, 0) + 1
        for v in variant_hints:
            if v:
                self.variants.add(v)


def discover_families(root_dir: str | Path) -> Dict[str, Family]:
    root = Path(root_dir)
    els = extract_elements(root)
    families: Dict[str, Family] = {}
    for el in els:
        tag = el.tag
        # Consider only PascalCase tags as components
        if not tag or not tag[0].isupper():
            continue
        b, variant_hints = base_name(tag)
        fam = families.setdefault(b, Family(base=b))
        fam.add_member(tag, el.props, variant_hints)
    return families


def family_suggestions(families: Dict[str, Family]) -> List[dict]:
    """Produce consolidation suggestions for families with multiple members.

    Suggest a canonical component per base with a `variant` prop enumerating member prefixes.
    """
    suggestions: List[dict] = []
    for base, fam in families.items():
        if len(fam.members) <= 1:
            continue
        # Variant names inferred from member names
        variant_names: Set[str] = set()
        for m in fam.members:
            if m == base:
                continue
            # derive likely variant token by removing base suffix/prefix
            if m.endswith(base):
                variant_names.add(m[: -len(base)] or "default")
            elif m.startswith(base):
                variant_names.add(m[len(base) :] or "default")
            else:
                # fallback to full name
                variant_names.add(m)
        if fam.variants:
            variant_names.update(fam.variants)
        # Prop shortlist: top-N props
        top_props = sorted(fam.props.items(), key=lambda kv: kv[1], reverse=True)[:8]
        suggestions.append(
            {
                "family": base,
                "members": sorted(fam.members),
                "suggested_variant_values": sorted(v for v in variant_names if v),
                "top_props": [p for p, _ in top_props],
            }
        )
    return suggestions
