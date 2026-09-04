// Firefox manifest transform. Pure function: base (Chromium) manifest object in,
// Firefox manifest object out. The base object is never mutated.
export const FIREFOX_EXTENSION_ID = 'chatgpt-route-inspector-firefox@local';
// content_scripts `world: "MAIN"` is supported since Firefox 128 (MDN BCD);
// background `type: "module"` event pages need 112+, service workers 121+.
// 128 is the highest floor, so it is the minimum.
export const FIREFOX_MIN_VERSION = '128.0';

export function toFirefoxManifest(base) {
  const manifest = JSON.parse(JSON.stringify(base));

  // Chromium-only key: Firefox ignores it, drop it so `about:debugging` stays clean.
  delete manifest.minimum_chrome_version;

  // MDN cross-browser pattern: declare both. Chrome (never sees this file) would
  // use `service_worker`; Firefox uses `scripts` (event page) unless told otherwise.
  // Event pages are a superset of the worker context for this codebase (no DOM use
  // in background either way), so the same bundle runs unmodified.
  const workerFile = manifest.background?.service_worker ?? 'background/service-worker.js';
  manifest.background = {
    scripts: [workerFile],
    service_worker: workerFile,
    type: manifest.background?.type ?? 'module'
  };

  // Required for signing/AMO later; harmless for local `about:debugging` loads.
  // strict_min_version keeps pre-128 installs from silently misbehaving.
  manifest.browser_specific_settings = {
    gecko: {
      id: FIREFOX_EXTENSION_ID,
      strict_min_version: FIREFOX_MIN_VERSION
    }
  };

  return manifest;
}
