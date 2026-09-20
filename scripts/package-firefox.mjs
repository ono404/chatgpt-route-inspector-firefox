// Packages dist/firefox into a local .xpi for temporary loading and real-machine
// probes, and records the hashes the probe verifies before installing.
//
// The record written next to the XPI is the *expectation* consumed by
// ff-marionette.py, so it is produced from the same dist tree in the same run
// and then re-verified against the archive that was actually written: the
// probe never re-reads the package under test to invent its own expectation.
//
// Usage: node scripts/package-firefox.mjs [--dist <dir>] [--out <dir>]
// Defaults: --dist dist/firefox, --out release
import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { inflateRawSync } from 'node:zlib';
import archiver from 'archiver';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const XPI_PREFIX = 'chatgpt-route-inspector-firefox-';

function argValue(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const distDir = path.resolve(root, argValue('dist', path.join('dist', 'firefox')));
const outDir = path.resolve(root, argValue('out', 'release'));
const packageJson = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));

async function walk(dir, base = dir, out = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, base, out);
    else if (entry.isFile()) out.push(path.relative(base, full).split(path.sep).join('/'));
  }
  return out.sort();
}

async function sha256(file) {
  return createHash('sha256').update(await readFile(file)).digest('hex');
}

// Minimal ZIP reader (stored + deflate) so this script can verify the archive
// it just wrote without pulling in a new dependency.
async function readZipEntries(file) {
  const buf = await readFile(file);
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 65558; i -= 1) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('not a zip archive: end-of-central-directory record not found');
  const count = buf.readUInt16LE(eocd + 10);
  let offset = buf.readUInt32LE(eocd + 16);
  const entries = {};
  for (let i = 0; i < count; i += 1) {
    if (buf.readUInt32LE(offset) !== 0x02014b50) throw new Error(`corrupt central directory at ${offset}`);
    const method = buf.readUInt16LE(offset + 10);
    const compressedSize = buf.readUInt32LE(offset + 20);
    const nameLength = buf.readUInt16LE(offset + 28);
    const extraLength = buf.readUInt16LE(offset + 30);
    const commentLength = buf.readUInt16LE(offset + 32);
    const localOffset = buf.readUInt32LE(offset + 42);
    const name = buf.toString('utf8', offset + 46, offset + 46 + nameLength);
    if (buf.readUInt32LE(localOffset) !== 0x04034b50) throw new Error(`corrupt local header for ${name}`);
    const dataStart = localOffset + 30 + buf.readUInt16LE(localOffset + 26) + buf.readUInt16LE(localOffset + 28);
    const raw = buf.subarray(dataStart, dataStart + compressedSize);
    const content = method === 0 ? raw : method === 8 ? inflateRawSync(raw)
      : (() => { throw new Error(`unsupported zip method ${method} for ${name}`); })();
    if (!name.endsWith('/')) entries[name] = createHash('sha256').update(content).digest('hex');
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

async function zipDirectory(source, target) {
  await new Promise((resolve, reject) => {
    const output = createWriteStream(target);
    const archive = archiver('zip', { zlib: { level: 9 } });
    output.on('close', resolve);
    output.on('error', reject);
    archive.on('error', reject);
    archive.pipe(output);
    archive.directory(source, false);
    void archive.finalize();
  });
}

const manifestPath = path.join(distDir, 'manifest.json');
try {
  await stat(manifestPath);
} catch {
  throw new Error(`No Firefox build at ${distDir}. Run: npm run build:firefox`);
}
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
if (manifest.version !== packageJson.version) {
  throw new Error(`manifest version ${manifest.version} does not match package.json ${packageJson.version}`);
}
if (!manifest.browser_specific_settings?.gecko?.id) {
  throw new Error('Firefox manifest is missing browser_specific_settings.gecko.id');
}

await mkdir(outDir, { recursive: true });
const baseName = `${XPI_PREFIX}${manifest.version}`;
const xpiPath = path.join(outDir, `${baseName}.xpi`);
await zipDirectory(distDir, xpiPath);

const files = await walk(distDir);
const hashes = {};
for (const file of files) hashes[file] = await sha256(path.join(distDir, file));

// The archive that was actually written must contain exactly the dist tree we
// hashed. If it does not, no record is emitted: a record that describes
// something other than the shipped XPI would silently become a false
// expectation for ff-marionette.py.
const entries = await readZipEntries(xpiPath);
const mismatches = [];
for (const file of files) {
  if (!(file in entries)) mismatches.push(`missing from XPI: ${file}`);
  else if (entries[file] !== hashes[file]) mismatches.push(`content differs in XPI: ${file}`);
}
for (const name of Object.keys(entries)) {
  if (!(name in hashes)) mismatches.push(`unexpected entry in XPI: ${name}`);
}
if (mismatches.length > 0) {
  throw new Error(`packaged XPI does not match ${distDir}:\n  ${mismatches.slice(0, 10).join('\n  ')}`);
}

const record = {
  version: manifest.version,
  geckoId: manifest.browser_specific_settings.gecko.id,
  strictMinVersion: manifest.browser_specific_settings.gecko.strict_min_version,
  distDir,
  createdAt: new Date().toISOString(),
  manifestSha256: hashes['manifest.json'],
  fileCount: files.length,
  fileHashes: hashes,
  xpiPath,
  xpiSha256: await sha256(xpiPath),
  xpiEntriesVerified: Object.keys(entries).length,
  // NOTE: the zip stores per-file mtimes, so repackaging identical sources
  // yields a different xpiSha256. Regenerate this record on every repack and
  // never compare an XPI hash across repacks.
  note: 'Expectation for ff-marionette.py --expect-build-record. Regenerate together with the XPI on every repack.'
};
const recordPath = path.join(outDir, `${baseName}.build.json`);
await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
process.stdout.write(`Packaged ${xpiPath}\n`);
process.stdout.write(`manifest.json sha256 ${record.manifestSha256}\n`);
process.stdout.write(`xpi sha256 ${record.xpiSha256}\n`);
process.stdout.write(`archive verified against dist: ${record.fileCount} files identical\n`);
process.stdout.write(`build record ${recordPath}\n`);
