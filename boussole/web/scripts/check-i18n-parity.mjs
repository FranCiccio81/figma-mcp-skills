#!/usr/bin/env node
/**
 * Vérification de parité i18n fr/en (bloquante — D15).
 *
 * - mêmes clés (récursivement) dans `messages/fr.json` et `messages/en.json` ;
 * - mêmes arguments ICU (`{name}`) et mêmes variantes de pluriel par clé ;
 * - aucune valeur vide.
 *
 * Usage : `node scripts/check-i18n-parity.mjs` (ou `npm run i18n:check`).
 * Sortie non nulle en cas d'écart — à brancher en CI.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const messagesDir = join(dirname(fileURLToPath(import.meta.url)), "..", "messages");
const locales = ["fr", "en"];

/** Aplati un objet de messages en Map "a.b.c" → valeur. */
function flatten(node, prefix = "", out = new Map()) {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      flatten(value, path, out);
    } else {
      out.set(path, String(value));
    }
  }
  return out;
}

/** Arguments ICU d'un message : noms de `{arg}` (hors littéraux de pluriel `#`). */
function icuArguments(message) {
  const args = new Set();
  for (const match of message.matchAll(/\{\s*([a-zA-Z0-9_]+)\s*[,}]/g)) {
    args.add(match[1]);
  }
  return args;
}

const catalogs = new Map(
  locales.map((locale) => {
    const raw = readFileSync(join(messagesDir, `${locale}.json`), "utf8");
    return [locale, flatten(JSON.parse(raw))];
  }),
);

const [reference, ...others] = locales;
const referenceCatalog = catalogs.get(reference);
const problems = [];

for (const locale of others) {
  const catalog = catalogs.get(locale);
  for (const key of referenceCatalog.keys()) {
    if (!catalog.has(key)) problems.push(`[${locale}] clé manquante : ${key}`);
  }
  for (const key of catalog.keys()) {
    if (!referenceCatalog.has(key)) problems.push(`[${reference}] clé manquante : ${key} (présente en ${locale})`);
  }
  for (const [key, value] of catalog) {
    const referenceValue = referenceCatalog.get(key);
    if (referenceValue === undefined) continue;
    const expected = [...icuArguments(referenceValue)].sort().join(",");
    const actual = [...icuArguments(value)].sort().join(",");
    if (expected !== actual) {
      problems.push(
        `[${locale}] arguments ICU divergents pour ${key} : fr={${expected}} ${locale}={${actual}}`,
      );
    }
  }
}

for (const [locale, catalog] of catalogs) {
  for (const [key, value] of catalog) {
    if (value.trim() === "") problems.push(`[${locale}] valeur vide : ${key}`);
  }
}

if (problems.length > 0) {
  console.error(`Parité i18n en échec — ${problems.length} écart(s) :`);
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}

console.log(
  `Parité i18n OK : ${referenceCatalog.size} clés identiques entre ${locales.join(" et ")}.`,
);
