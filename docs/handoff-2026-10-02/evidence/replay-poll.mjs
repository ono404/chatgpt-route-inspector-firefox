import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const base = path.dirname(fileURLToPath(import.meta.url));
const params = JSON.parse(fs.readFileSync(path.join(base, 'actual-poll.json'), 'utf8'));
const first = JSON.parse(fs.readFileSync(path.join(base, 'actual-found.json'), 'utf8'));
const second = {...first, captureId: '4f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d'};
const state = {revision: 21, turns: [first, second], captureContexts: {
  [first.tabId]: {id: first.captureContextId, pageUrl: first.pageUrl, revision: 11}
}};
globalThis.chrome = {runtime: {sendMessage: async () => ({state})}};
const result = await new Function(params.script)(...params.args);
fs.writeFileSync(path.join(base, 'actual-js-duplicate-result.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
