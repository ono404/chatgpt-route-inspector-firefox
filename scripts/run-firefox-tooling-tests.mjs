// Runs the Python regression tests for the Firefox verification tooling.
//
// Two environment quirks are handled explicitly:
//   1. A bare `python` on Windows is often the Microsoft Store alias, which
//      exits 9009 and prints nothing useful. Treating that as "tests failed"
//      would be wrong, so every candidate is probed before it is used.
//   2. On this machine `child_process.spawnSync` fails with EBUSY for every
//      command, while the asynchronous `spawn` works. The runner therefore
//      uses async spawn throughout.
//
// Usage: node scripts/run-firefox-tooling-tests.mjs
//   PYTHON=<path>   override the interpreter
import { spawn } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const testsDir = path.join(root, 'tests', 'firefox-tooling');

function run(command, args, options = {}) {
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    const child = spawn(command, args, { windowsHide: true });
    child.stdout?.on('data', (chunk) => { stdout += chunk; });
    child.stderr?.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => resolve({ status: null, error, stdout, stderr }));
    child.on('close', (status) => resolve({ status, error: null, stdout, stderr, ...options }));
  });
}

function runVisible(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      stdio: 'inherit',
      cwd: root,
      windowsHide: true,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }
    });
    child.on('error', (error) => resolve({ status: null, error }));
    child.on('close', (status) => resolve({ status, error: null }));
  });
}

function managedPythonCandidates() {
  const base = path.join(os.homedir(), '.workbuddy', 'binaries', 'python', 'versions');
  if (!existsSync(base)) return [];
  return readdirSync(base)
    .map((version) => path.join(base, version, 'python.exe'))
    .filter((exe) => existsSync(exe))
    .sort()
    .reverse();
}

const candidates = [
  ...(process.env.PYTHON ? [[process.env.PYTHON, []]] : []),
  ...(process.env.FF_PROBE_PYTHON ? [[process.env.FF_PROBE_PYTHON, []]] : []),
  ...managedPythonCandidates().map((exe) => [exe, []]),
  ['python3', []],
  ['py', ['-3']],
  ['python', []]
];

let chosen = null;
for (const [command, prefix] of candidates) {
  const probe = await run(command, [...prefix, '-c', 'import sys;print(sys.version_info[0])']);
  if (probe.status === 0 && (probe.stdout ?? '').trim() === '3') { chosen = [command, prefix]; break; }
}
if (!chosen) {
  process.stderr.write('run-firefox-tooling-tests: no working Python 3 interpreter found.\n');
  process.stderr.write('Tried: ' + candidates.map(([c]) => c).join(', ') + '\n');
  process.stderr.write('Set PYTHON=<path to python.exe> and retry.\n');
  process.exit(70);
}
const [python, prefix] = chosen;
process.stdout.write(`interpreter: ${python}\n`);

const result = await runVisible(python, [
  ...prefix, '-B', '-m', 'unittest', 'discover',
  '-t', testsDir, '-s', testsDir, '-p', 'test_*.py', '-v'
]);
if (result.error) {
  process.stderr.write(`run-firefox-tooling-tests: ${result.error.message}\n`);
  process.exit(70);
}
process.exit(result.status ?? 1);
