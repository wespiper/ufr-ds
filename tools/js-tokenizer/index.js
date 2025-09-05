#!/usr/bin/env node
/*
 AST-based tokenizer for React/TS projects.
 Emits a JSON payload with flat token array and basic counts.
*/
const fs = require('fs');
const path = require('path');
const fg = require('fast-glob');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const exts = ['.js', '.jsx', '.ts', '.tsx'];

function listFiles(root) {
  return fg.sync(['**/*.{js,jsx,ts,tsx}'], {
    cwd: root,
    absolute: true,
    dot: false,
    ignore: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/build/**'],
  });
}

function tokenizeFile(file) {
  let code;
  try { code = fs.readFileSync(file, 'utf8'); } catch { return []; }
  const tokens = [];
  let ast;
  try {
    ast = parser.parse(code, {
      sourceType: 'module',
      plugins: ['jsx', 'typescript', 'classProperties', 'decorators-legacy'],
    });
  } catch (e) {
    return tokens; // skip parse errors
  }

  traverse(ast, {
    ImportDeclaration(p) {
      const s = p.node.source && p.node.source.value;
      for (const sp of p.node.specifiers) {
        if (sp.type === 'ImportDefaultSpecifier' && sp.local && sp.local.name) {
          tokens.push(`IMPORT:${sp.local.name}`);
        }
        if (sp.type === 'ImportSpecifier' && sp.imported && sp.imported.name) {
          tokens.push(`IMPORT:${sp.imported.name}`);
        }
      }
    },
    JSXOpeningElement(p) {
      const name = p.node.name;
      let tag = null;
      if (name.type === 'JSXIdentifier') tag = name.name;
      if (name.type === 'JSXMemberExpression') {
        // e.g., UI.Button -> take rightmost
        let cur = name;
        while (cur.type === 'JSXMemberExpression') cur = cur.property;
        tag = (cur && cur.name) || null;
      }
      if (tag) tokens.push(`TAG:${tag}`);
      for (const attr of p.node.attributes || []) {
        if (attr.type === 'JSXAttribute' && attr.name && attr.name.name) {
          tokens.push(`PROP:${attr.name.name}`);
        }
      }
    },
  });
  return tokens;
}

function main() {
  const root = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
  const files = listFiles(root);
  const all = [];
  for (const f of files) {
    all.push(...tokenizeFile(f));
  }
  const payload = {
    files: files.length,
    tokens: all,
    counts: {
      tags: all.filter(t => t.startsWith('TAG:')).length,
      props: all.filter(t => t.startsWith('PROP:')).length,
      components: all.filter(t => t.startsWith('IMPORT:')).length,
    },
  };
  process.stdout.write(JSON.stringify(payload));
}

if (require.main === module) main();

