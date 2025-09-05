from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Set


JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}


def list_source_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in JS_EXTS:
            files.append(p)
    return files


TAG_OPEN_RE = re.compile(r"<\s*([A-Za-z_][A-Za-z0-9_]*)[\s>/]")
TAG_CLOSE_RE = re.compile(r"</\s*([A-Za-z_][A-Za-z0-9_]*)\s*>")
PROP_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*")
IMPORT_NAMED_RE = re.compile(r"import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]+['\"];?")
IMPORT_DEFAULT_RE = re.compile(r"import\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s*['\"][^'\"]+['\"];?")


HTML_TAGS: Set[str] = {
    # Common HTML tags to optionally downweight or skip; we keep them but can filter later
    "div", "span", "p", "a", "img", "ul", "ol", "li", "input", "button", "select", "option",
    "label", "form", "table", "thead", "tbody", "tr", "td", "th", "header", "footer", "main",
    "section", "article", "nav", "aside", "h1", "h2", "h3", "h4", "h5", "h6",
}


def tokenize_file(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    tokens: List[str] = []

    # Imports
    for m in IMPORT_DEFAULT_RE.finditer(text):
        name = m.group(1)
        tokens.append(f"IMPORT:{name}")
    for m in IMPORT_NAMED_RE.finditer(text):
        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
        for name in names:
            # Handle aliasing: X as Y
            name = name.split(" as ")[0].strip()
            if name:
                tokens.append(f"IMPORT:{name}")

    # JSX tags
    for m in TAG_OPEN_RE.finditer(text):
        tag = m.group(1)
        tokens.append(f"TAG:{tag}")
    for m in TAG_CLOSE_RE.finditer(text):
        tag = m.group(1)
        tokens.append(f"TAG_CLOSE:{tag}")

    # JSX props
    for m in PROP_RE.finditer(text):
        prop = m.group(1)
        # Filter out likely non-prop assignments in code by simple heuristic: occurs near a '<'
        # Keep all for now; engine can compress noise away
        tokens.append(f"PROP:{prop}")

    return tokens


def tokenize_project(root_dir: str | Path) -> Tuple[List[str], Dict[str, int]]:
    """Tokenize a React/TS project by extracting JSX tags, props, and imports.

    Returns a flat token sequence and basic counts for quick summaries.
    """
    root = Path(root_dir)
    all_tokens: List[str] = []
    counts: Dict[str, int] = {
        "files": 0,
        "tags": 0,
        "components": 0,
        "props": 0,
    }

    for file in list_source_files(root):
        counts["files"] += 1
        toks = tokenize_file(file)
        all_tokens.extend(toks)

    # Summaries
    counts["tags"] = sum(1 for t in all_tokens if t.startswith("TAG:"))
    counts["components"] = sum(1 for t in all_tokens if t.startswith("IMPORT:"))
    counts["props"] = sum(1 for t in all_tokens if t.startswith("PROP:"))
    return all_tokens, counts

