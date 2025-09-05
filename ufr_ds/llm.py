from __future__ import annotations

import os
from typing import List, Optional


def _openai_refine(prompt: str) -> Optional[str]:
    try:
        import openai  # type: ignore
    except Exception:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = openai.OpenAI(api_key=api_key)  # newer SDK
        resp = client.chat.completions.create(
            model=os.getenv("UFR_OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=float(os.getenv("UFR_OPENAI_T", "0.2")),
        )
        return resp.choices[0].message.content  # type: ignore
    except Exception:
        return None


def _anthropic_refine(prompt: str) -> Optional[str]:
    try:
        import anthropic  # type: ignore
    except Exception:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.getenv("UFR_ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
            max_tokens=2000,
            temperature=float(os.getenv("UFR_ANTHROPIC_T", "0.2")),
            messages=[{"role": "user", "content": prompt}],
        )
        # anthropic SDK returns content blocks
        parts = getattr(msg, "content", [])
        if parts and hasattr(parts[0], "text"):
            return parts[0].text  # type: ignore
        return None
    except Exception:
        return None


def refine_component(name: str, variants: List[str], props: List[str], base_tsx: str, provider: Optional[str] = None) -> Optional[str]:
    """Optionally refine a generated component via an LLM.

    Provider is 'openai' or 'anthropic'; reads API keys from env.
    Returns refined TSX string or None if unavailable/failure.
    """
    prompt = f"""
You are assisting with a React component refactor guided by discovered UI grammar patterns.
Please improve the following TypeScript React component skeleton while preserving prop and variant contracts.

Component name: {name}
Variants: {variants}
Props: {props}

Goals:
- Keep the API stable; do not remove props.
- If helpful, add better types for common props (e.g., variant as union, booleans, strings).
- Ensure accessibility basics (labels, aria- attributes where reasonable) and good defaults.
- Keep the implementation simple; stubs are fine but avoid dead code.

Provided skeleton:
```
{base_tsx}
```

Return only the improved TSX file content.
"""
    if provider == "openai":
        return _openai_refine(prompt)
    if provider == "anthropic":
        return _anthropic_refine(prompt)
    return None


def generate_text(prompt: str, provider: Optional[str] = None) -> Optional[str]:
    """Generic text generation for summaries via the selected provider."""
    if provider == "openai":
        return _openai_refine(prompt)
    if provider == "anthropic":
        return _anthropic_refine(prompt)
    return None
