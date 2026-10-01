// Regression test: the verify-firefox-dist CLI must reject tampered Firefox
// manifests. The CLI is executed for real (no mocks, no reimplemented checks);
// fixtures are copies of the frozen dist/ targets in a system temp directory.
//
// History: the pre-hardening verifier only spot-checked a few Firefox manifest
// fields, so version / permissions / world / background / data-collection
// mutations passed with exit code 0. Each mutation below is applied to an
// otherwise legal fixture, so a non-zero exit can only come from the manifest
// comparison.
import { spawn } from 'node:child_process';
import { cp, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, expect, it } from 'vitest';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const verifier = path.join(root, 'scripts', 'verify-firefox-dist.mjs');
const distExtension = path.join(root, 'dist', 'extension');
const distFirefox = path.join(root, 'dist', 'firefox');

type CliResult = { code: number; output: string };

async function assertDirExists(dir: string): Promise<void> {
  try {
    if ((await stat(dir)).isDirectory()) return;
  } catch { /* fall through to the error below */ }
  throw new Error(`fixture input missing (refusing to skip): ${dir}`);
}

let fixtureRoot = '';
let pristineExtension = '';
let pristineFirefox = '';
let mutationIndex = 0;

beforeAll(async () => {
  await assertDirExists(distExtension);
  await assertDirExists(distFirefox);
  fixtureRoot = await mkdtemp(path.join(tmpdir(), 'ff-dist-verifier-'));
  pristineExtension = path.join(fixtureRoot, 'extension');
  pristineFirefox = path.join(fixtureRoot, 'firefox');
  await cp(distExtension, pristineExtension, { recursive: true });
  await cp(distFirefox, pristineFirefox, { recursive: true });
});

afterAll(async () => {
  if (fixtureRoot) await rm(fixtureRoot, { recursive: true, force: true });
});

function runVerifier(extensionDir: string, firefoxDir: string): Promise<CliResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [verifier, extensionDir, firefoxDir], {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });
    let out = '';
    child.stdout.on('data', (chunk: Buffer) => { out += chunk; });
    child.stderr.on('data', (chunk: Buffer) => { out += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code: code ?? -1, output: out }));
  });
}

/** Fresh copy of the legal firefox fixture with one manifest mutation applied. */
async function mutatedFirefox(mutate: (manifest: Record<string, unknown>) => void): Promise<string> {
  mutationIndex += 1;
  const dir = path.join(fixtureRoot, `mutation-${mutationIndex}`);
  await cp(pristineFirefox, dir, { recursive: true });
  const manifestPath = path.join(dir, 'manifest.json');
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Record<string, unknown>;
  if (typeof manifest !== 'object' || manifest === null) throw new Error('fixture manifest is not an object');
  mutate(manifest);
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  return dir;
}

it('accepts a legal fixture with exit code 0', async () => {
  const result = await runVerifier(pristineExtension, pristineFirefox);
  expect(result.code).toBe(0);
  expect(result.output).toContain('verify-firefox-dist: OK');
});

type Mutation = { name: string; apply: (manifest: Record<string, unknown>) => void };

const MUTATIONS: Mutation[] = [
  { name: 'firefox version is wrong', apply: (m) => { m.version = '0.0.0-tampered'; } },
  { name: 'permissions gain an extra entry', apply: (m) => { m.permissions = [...(m.permissions as string[]), 'bookmarks']; } },
  { name: 'host_permissions gain an extra entry', apply: (m) => { m.host_permissions = [...(m.host_permissions as string[]), 'https://example.com/*']; } },
  {
    name: 'MAIN world content script is downgraded to ISOLATED',
    apply: (m) => {
      const scripts = m.content_scripts as Array<Record<string, unknown>>;
      const main = scripts.find((entry) => entry.world === 'MAIN');
      if (!main) throw new Error('fixture unexpectedly has no MAIN content script');
      main.world = 'ISOLATED';
    }
  },
  { name: 'background.scripts is emptied', apply: (m) => { (m.background as Record<string, unknown>).scripts = []; } },
  { name: 'background.type is wrong', apply: (m) => { (m.background as Record<string, unknown>).type = 'classic'; } },
  {
    name: 'data_collection_permissions.required becomes ["none","locationInfo"]',
    apply: (m) => {
      const settings = m.browser_specific_settings;
      if (typeof settings !== 'object' || settings === null) throw new Error('fixture has no browser_specific_settings');
      const gecko = (settings as Record<string, unknown>).gecko;
      if (typeof gecko !== 'object' || gecko === null) throw new Error('fixture has no gecko block');
      const geckoRecord = gecko as Record<string, unknown>;
      const dcp = geckoRecord.data_collection_permissions;
      if (typeof dcp !== 'object' || dcp === null) throw new Error('fixture has no data_collection_permissions');
      (dcp as Record<string, unknown>).required = ['none', 'locationInfo'];
    }
  }
];

for (const mutation of MUTATIONS) {
  it(`rejects: ${mutation.name}`, async () => {
    const firefoxDir = await mutatedFirefox(mutation.apply);
    const result = await runVerifier(pristineExtension, firefoxDir);
    expect(result.code, `expected non-zero exit, output was:\n${result.output}`).not.toBe(0);
    // The failure must come from the manifest comparison, not from a missing
    // file or an unrelated crash.
    expect(result.output).toContain('manifest');
    expect(result.output).not.toContain('references missing file');
  });
}

it('keeps the legal fixture passing after the mutation rounds (restore check)', async () => {
  const result = await runVerifier(pristineExtension, pristineFirefox);
  expect(result.code).toBe(0);
  expect(result.output).toContain('verify-firefox-dist: OK');
});
