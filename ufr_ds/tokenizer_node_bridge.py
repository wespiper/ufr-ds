from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def has_node_tokenizer() -> bool:
    node = shutil.which("node")
    script = Path("tools/js-tokenizer/index.js")
    return bool(node and script.exists())


def tokenize_project_ast(root_dir: str | Path) -> Tuple[List[str], Dict[str, int]]:
    root = Path(root_dir)
    script = Path("tools/js-tokenizer/index.js").resolve()
    proc = subprocess.run(
        ["node", str(script), str(root.resolve())],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Node tokenizer failed: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    tokens = list(data.get("tokens", []))
    counts = {
        "files": int(data.get("files", 0)),
        "tags": int(data.get("counts", {}).get("tags", 0)),
        "props": int(data.get("counts", {}).get("props", 0)),
        "components": int(data.get("counts", {}).get("components", 0)),
    }
    return tokens, counts

