UFR-DS CLI (Emergence-powered)

Quick start

-   Analyze a React/TS project directory and output a pattern report:

    python -m ufr_ds.cli analyze ../path-to-react-project --pretty

-   Include emergence analysis (entropy trajectory + events):

    python -m ufr_ds.cli analyze ../path-to-react-project --emergence --pretty

-   Generate canonical components from discovered families (writes TSX stubs):

    python -m ufr_ds.cli generate ../path-to-react-project --out ./generated --pretty

Install as a CLI

-   Python package (local install):

    pip install -e .

    Now you can run simply: `ufr analyze <path> --ast --pretty`

-   Optional: Use pre-tokenized JSON instead of spawning Node:

    npx @ufr/ast-tokenizer "/path/to/react-project" > tokens.json
    ufr analyze "/path/to/react-project" --tokens tokens.json --pretty

Reports and LLM summary

-   Write a Markdown report from a saved analysis JSON:

    ufr analyze "/path" --ast --pretty > analysis.json
    ufr report analysis.json --out ufr-report.md

-   Add an LLM-written human-friendly summary (optional):

    export OPENAI_API_KEY=...  # or ANTHROPIC_API_KEY=...
    ufr report analysis.json --llm openai --out ufr-report.md

What it does

-   Tokenizes JSX/TSX/JS files for:
    -   TAG: JSX tag names (e.g., TAG:Button)
    -   PROP: JSX prop names (e.g., PROP:variant)
    -   IMPORT: imported component identifiers (e.g., IMPORT:Button)
-   Feeds tokens into the Emergence Engine (RePair + MDL) to induce a grammar and compute:
    -   Compression ratio (naive baseline vs grammar-encoded sequence)
    -   MDL totals and coverage
    -   Discovered rules (patterns)
    -   Optional emergence events (phase transitions)

Notes

-   The tokenizer is lightweight (regex-based) and intentionally noise-tolerant; the engine tends to compress repetitive noise.
-   For richer analysis, we can replace the tokenizer with a Babel-based AST pipeline in a future iteration.
-   The generator outputs TSX skeletons per family with a `variant` prop and top observed props; refine mapping rules as needed.
 -   LLM providers: `openai` or `anthropic` via `--llm`; keys via `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
