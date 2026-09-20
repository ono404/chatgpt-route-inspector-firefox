// Packages dist/firefox into a local .xpi for temporary loading and real-machine
// probes, and records the hashes the probe verifies before installing.
//
// Usage: node scripts/package-firefox.mjs [--dist <dir>] [--out <dir>]
// Defaults: --dist dist/firefox, --out release
import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
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
const record = {
  version: manifest.version,
  geckoId: manifest.browser_specific_settings.gecko.id,
  strictMinVersion: manifest.browser_specific_settings.gecko.strict_min_version,
  distDir,
  manifestSha256: hashes['manifest.json'],
  fileCount: files.length,
  fileHashes: hashes,
  xpiPath,
  xpiSha256: await sha256(xpiPath)
};
const recordPath = path.join(outDir, `${baseName}.build.json`);
await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
process.stdout.write(`Packaged ${xpiPath}\n`);
process.stdout.write(`manifest.json sha256 ${record.manifestSha256}\n`);
process.stdout.write(`xpi sha256 ${record.xpiSha256}\n`);
process.stdout.write(`build record ${recordPath}\n`);
