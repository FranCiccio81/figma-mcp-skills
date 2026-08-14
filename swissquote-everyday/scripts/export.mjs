/**
 * Builds the shareable exports.
 *
 *   export/swissquote-everyday.html   one self-contained file — double-click,
 *                                     no server, no network.
 *   export/claude-design/             the same app unbundled for Claude Design:
 *                                     index.html + tokens.css + app.css + app.js.
 *                                     tokens.css loads last, so editing it
 *                                     restyles the whole prototype.
 *
 * Everything is inlined from node_modules — no CDN, nothing to fetch at runtime.
 */
import { build } from 'esbuild';
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'export');
const design = join(out, 'claude-design');

rmSync(out, { recursive: true, force: true });
mkdirSync(design, { recursive: true });

/* ---------------------------------------------------------------- */
/* 1. App code → one readable IIFE (works over file://, no modules)  */
/* ---------------------------------------------------------------- */
await build({
  entryPoints: [join(root, 'src/main.tsx')],
  bundle: true,
  format: 'iife',
  target: 'es2020',
  jsx: 'automatic',
  minify: false,
  keepNames: true,
  legalComments: 'none',
  define: { 'process.env.NODE_ENV': '"production"' },
  loader: { '.css': 'empty' }, // styles ship as real CSS files, not JS
  outfile: join(design, 'app.js'),
});

/* ---------------------------------------------------------------- */
/* 2. Styles: Tailwind + components in app.css, tokens kept separate */
/* ---------------------------------------------------------------- */
const distAssets = join(root, 'dist/assets');
const builtCss = readdirSync(distAssets).find((f) => f.endsWith('.css'));
if (!builtCss) throw new Error('Run `npm run build` first — no built CSS found.');
writeFileSync(join(design, 'app.css'), readFileSync(join(distAssets, builtCss)));

const tokens = readFileSync(join(root, 'src/styles/tokens.css'), 'utf8');
writeFileSync(
  join(design, 'tokens.css'),
  `/*\n * Design tokens — the single place to restyle this prototype.\n * Loaded after app.css, so anything you change here wins.\n */\n\n${tokens}`,
);

/* ---------------------------------------------------------------- */
/* 3. index.html for the unbundled folder                           */
/* ---------------------------------------------------------------- */
writeFileSync(
  join(design, 'index.html'),
  `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Swissquote Everyday — Concept</title>
    <!-- app.css first, tokens.css second: your token edits override the build. -->
    <link rel="stylesheet" href="app.css" />
    <link rel="stylesheet" href="tokens.css" />
  </head>
  <body>
    <div id="root"></div>
    <script src="app.js"></script>
  </body>
</html>
`,
);

/* ---------------------------------------------------------------- */
/* 4. Single-file export                                            */
/* ---------------------------------------------------------------- */
const js = readFileSync(join(design, 'app.js'), 'utf8');
if (js.includes('</' + 'script')) throw new Error('Bundle contains a closing script tag.');
writeFileSync(
  join(out, 'swissquote-everyday.html'),
  `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Swissquote Everyday — Concept</title>
    <style>
${readFileSync(join(design, 'app.css'), 'utf8')}
${tokens}
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script>
${js}
    </script>
  </body>
</html>
`,
);

/* ---------------------------------------------------------------- */
/* 5. How to use it                                                 */
/* ---------------------------------------------------------------- */
writeFileSync(
  join(design, 'README.md'),
  `# Swissquote Everyday — Claude Design export

> Concept — not a product commitment.

The prototype as four flat files. No build step, no server, no network calls.

| File | What it is |
|---|---|
| \`index.html\` | Entry point. Loads the styles, then the app. |
| \`tokens.css\` | **Start here to restyle.** Every colour, type size, spacing, radius, shadow and motion value. Loaded last, so your edits win. |
| \`app.css\` | Component styles (BEM classes) and the utility layer. |
| \`app.js\` | The app: React, the Smart Liquidity engine, and every screen. |

## Run it

Open \`index.html\` — double-clicking works, because nothing is fetched at
runtime. In Claude Design, drop the folder in and it serves itself.

## Restyle it

Everything visual resolves to a custom property in \`tokens.css\`. Change
\`--color-action-accent\` and every accent in the app follows; change
\`--radius-lg\` and every card does. To apply the real Bridge export, replace the
values in that one file.

## Change the behaviour

\`app.js\` is unminified and keeps its original function names, so the engine is
readable — search for \`attemptAutoCover\`, \`computeForecast\` or
\`runAllocation\`. For real editing, work in the TypeScript source one level up
(\`src/\`) and re-run \`npm run export\`.

## What's inside

Four connected features: **AI Budgeting** predicts the liquidity needed before
the next salary; **Smart Salary Allocation** puts the surplus to work;
**Everyday Buying Power** shows accessible cash with credit kept separate; and
**Auto Cover** brings cash back when a payment needs it. The **Simulate** panel
beside the phone advances time and forces the edge cases.
`,
);

const size = (p) => (readFileSync(p).length / 1024).toFixed(0) + ' KB';
console.log('export/swissquote-everyday.html  ', size(join(out, 'swissquote-everyday.html')));
console.log('export/claude-design/app.js      ', size(join(design, 'app.js')));
console.log('export/claude-design/app.css     ', size(join(design, 'app.css')));
console.log('export/claude-design/tokens.css  ', size(join(design, 'tokens.css')));
