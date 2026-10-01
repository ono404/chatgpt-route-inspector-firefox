// Firefox build artifact verification (Chromium vs Firefox targets).
//
// Checks:
//   1. Both targets ship the exact same set of relative file paths (no
//      intersection-only comparison: missing files on either side fail).
//   1b. Source-anchored completeness: every UI page present under src/ui/ is
//      shipped by BOTH targets.
//   2. Every file is byte-identical across targets, except manifest.json.
//      All .js files are additionally required to be byte-identical.
//   3. Every local file referenced by either manifest.json exists.
//   4. Every local file referenced by any shipped .html exists.
//   5. The shipped manifests match the source of truth as whole objects:
//      extension manifest === manifest/manifest.json, and firefox manifest ===
//      toFirefoxManifest(manifest/manifest.json). Field-by-field guardrails
//      once let version / permissions / world / background / data-collection
//      mutations through, so the comparison is total (key order and formatting
//      are not compared).
//
// Boundary: the pairwise comparison in (1) alone cannot detect a page that is
// missing from BOTH targets. (1b) narrows that blind spot to the pages that
// exist in src/ui/, but it still cannot see an entry that was never created in
// src/ (e.g. an upstream `uiEntries` entry whose HTML/TS file does not exist).
//
// Usage: node scripts/verify-firefox-dist.mjs [extensionDir] [firefoxDir]
// Exits non-zero with a report on any failure.
import { deepStrictEqual } from 'node:assert';
import { createHash } from 'node:crypto';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { toFirefoxManifest } from './firefox-manifest.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const extensionDir = path.resolve(process.argv[2] ?? path.join(root, 'dist', 'extension'));
const firefoxDir = path.resolve(process.argv[3] ?? path.join(root, 'dist', 'firefox'));

const failures = [];
const notes = [];
const fail = (message) => failures.push(message);

async function walk(dir, base = dir, out = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, base, out);
    else if (entry.isFile()) out.push(path.relative(base, full).split(path.sep).join('/'));
  }
  return out;
}

async function sha256(file) {
  return createHash('sha256').update(await readFile(file)).digest('hex');
}

async function exists(file) {
  try { return (await stat(file)).isFile(); } catch { return false; }
}

function collectManifestRefs(manifest) {
  const refs = [];
  if (manifest.background?.service_worker) refs.push(manifest.background.service_worker);
  for (const script of manifest.background?.scripts ?? []) refs.push(script);
  if (manifest.action?.default_popup) refs.push(manifest.action.default_popup);
  if (manifest.options_ui?.page) refs.push(manifest.options_ui.page);
  for (const icon of Object.values(manifest.icons ?? {})) refs.push(icon);
  for (const icon of Object.values(manifest.action?.default_icon ?? {})) refs.push(icon);
  for (const entry of manifest.content_scripts ?? []) for (const js of entry.js ?? []) refs.push(js);
  return refs;
}

function collectHtmlRefs(html) {
  const refs = [];
  for (const match of html.matchAll(/<(?:script|link|img)\b[^>]*?\b(?:src|href)\s*=\s*"([^"]+)"/gi)) {
    refs.push(match[1]);
  }
  return refs;
}

function isLocalRef(ref) {
  return Boolean(ref) && !/^(?:[a-z]+:|\/\/|#)/i.test(ref);
}

const extFiles = (await walk(extensionDir)).sort();
const ffFiles = (await walk(firefoxDir)).sort();

// 1. Path sets must match exactly, in both directions.
const extSet = new Set(extFiles);
const ffSet = new Set(ffFiles);
for (const file of extFiles) if (!ffSet.has(file)) fail(`missing in firefox: ${file}`);
for (const file of ffFiles) if (!extSet.has(file)) fail(`missing in extension: ${file}`);
notes.push(`paths: extension=${extFiles.length} firefox=${ffFiles.length} identical=${[...extSet].every((f) => ffSet.has(f))}`);

// 1b. Source-anchored completeness. Without this, a page that the build drops
// from both targets at once would still satisfy the pairwise comparison above.
const srcUiPages = (await walk(path.join(root, 'src', 'ui')))
  .filter((file) => file.endsWith('index.html'))
  .map((file) => `ui/${file}`);
for (const page of srcUiPages) {
  if (!extSet.has(page)) fail(`extension: src UI page not shipped: ${page}`);
  if (!ffSet.has(page)) fail(`firefox: src UI page not shipped: ${page}`);
}
notes.push(`src UI pages: ${srcUiPages.length} checked against both targets`);
notes.push(`boundary: the pairwise path comparison cannot see an entry missing from BOTH targets; the src-anchored check covers src/ui/**/index.html only`);

// 2. Byte identity per file (manifest.json excluded by design).
for (const file of extFiles) {
  if (!ffSet.has(file) || file === 'manifest.json') continue;
  const [a, b] = await Promise.all([sha256(path.join(extensionDir, file)), sha256(path.join(firefoxDir, file))]);
  if (a !== b) fail(`content differs: ${file}`);
}
const extJs = extFiles.filter((file) => file.endsWith('.js'));
for (const file of extJs) {
  if (!ffSet.has(file)) { fail(`JS missing on firefox side: ${file}`); continue; }
  const [a, b] = await Promise.all([sha256(path.join(extensionDir, file)), sha256(path.join(firefoxDir, file))]);
  if (a !== b) fail(`JS not byte-identical: ${file}`);
}
notes.push(`js byte-identical: ${extJs.length} files checked`);

// 3/4. Referenced local files must exist inside the same target.
for (const [label, dir] of [['extension', extensionDir], ['firefox', firefoxDir]]) {
  const manifestFile = path.join(dir, 'manifest.json');
  if (!(await exists(manifestFile))) { fail(`${label}: manifest.json missing`); continue; }
  const manifest = JSON.parse(await readFile(manifestFile, 'utf8'));
  for (const ref of collectManifestRefs(manifest)) {
    if (!isLocalRef(ref)) continue;
    if (!(await exists(path.join(dir, ref)))) fail(`${label}: manifest references missing file ${ref}`);
  }
  for (const htmlFile of (await walk(dir)).filter((file) => file.endsWith('.html'))) {
    const html = await readFile(path.join(dir, htmlFile), 'utf8');
    for (const ref of collectHtmlRefs(html)) {
      if (!isLocalRef(ref)) continue;
      const target = path.resolve(path.dirname(path.join(dir, htmlFile)), ref.split(/[?#]/)[0]);
      if (!(await exists(target))) fail(`${label}: ${htmlFile} references missing file ${ref}`);
    }
  }
}

// Announcement surface must be complete (new in v1.0.7).
for (const [label, dir] of [['extension', extensionDir], ['firefox', firefoxDir]]) {
  for (const file of ['ui/announcement/index.html', 'ui/announcement/index.js']) {
    if (!(await exists(path.join(dir, file)))) fail(`${label}: announcement asset missing ${file}`);
  }
  const announcementHtml = path.join(dir, 'ui', 'announcement', 'index.html');
  if (await exists(announcementHtml)) {
    const refs = collectHtmlRefs(await readFile(announcementHtml, 'utf8'));
    if (!refs.includes('index.js')) fail(`${label}: announcement html does not load index.js`);
  }
}

// Shipped manifests must equal the source-of-truth objects in full. deepEqual
// ignores key order and whitespace; its diff output pinpoints the first
// mismatch, which is all the report needs.
function deepDiffMessage(error) {
  return String(error.message).split('\n').filter((line) => line.trim()).slice(0, 12).join(' ⏎ ').slice(0, 600);
}

try {
  const base = JSON.parse(await readFile(path.join(root, 'manifest', 'manifest.json'), 'utf8'));
  const extManifest = JSON.parse(await readFile(path.join(extensionDir, 'manifest.json'), 'utf8'));
  try {
    deepStrictEqual(extManifest, base);
  } catch (error) {
    fail(`extension: manifest differs from manifest/manifest.json: ${deepDiffMessage(error)}`);
  }
  const ffManifest = JSON.parse(await readFile(path.join(firefoxDir, 'manifest.json'), 'utf8'));
  try {
    deepStrictEqual(ffManifest, toFirefoxManifest(base));
  } catch (error) {
    fail(`firefox: manifest differs from toFirefoxManifest(manifest/manifest.json): ${deepDiffMessage(error)}`);
  }
} catch (error) {
  fail(`manifest unreadable (${error.message})`);
}

for (const note of notes) process.stdout.write(`note  ${note}\n`);
if (failures.length === 0) {
  process.stdout.write('verify-firefox-dist: OK\n');
  process.exit(0);
}
for (const message of failures) process.stderr.write(`FAIL  ${message}\n`);
process.stdout.write(`verify-firefox-dist: ${failures.length} failure(s)\n`);
process.exit(1);
