@ufr/ast-tokenizer

Babel-based tokenizer for React/TypeScript projects. Emits a flat token list capturing JSX tags, props, and imported identifiers.

Usage

- npx @ufr/ast-tokenizer "/absolute/path/to/react-project" > tokens.json
- tokens.json shape:

  {
    "files": 123,
    "tokens": ["TAG:Button", "PROP:variant", "IMPORT:React", ...],
    "counts": { "tags": 456, "props": 789, "components": 111 }
  }

- Use with the UFR analyzer (Python):

  ufr analyze "/path/to/react-project" --tokens tokens.json --pretty

Notes

- Ignores node_modules, dist, build, .next.
- Parses .js, .jsx, .ts, .tsx with plugins: jsx, typescript, classProperties, decorators-legacy.

