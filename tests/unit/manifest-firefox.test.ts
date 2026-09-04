import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FIREFOX_MIN_VERSION, toFirefoxManifest } from '../../scripts/firefox-manifest.mjs';

function baseManifest(): Record<string, unknown> {
  return JSON.parse(readFileSync(new URL('../../manifest/manifest.json', import.meta.url), 'utf8')) as Record<string, unknown>;
}

describe('firefox manifest transform', () => {
  it('keeps the transform pure and converts only what Firefox needs', () => {
    const base = baseManifest();
    const snapshot = JSON.stringify(base);
    const firefox = toFirefoxManifest(base) as Record<string, unknown>;

    // Base (Chromium) spec untouched.
    expect(JSON.stringify(base)).toBe(snapshot);
    expect(firefox).not.toBe(base);

    // Background: MDN cross-browser shape, same bundle file.
    expect(firefox.background).toEqual({
      scripts: ['background/service-worker.js'],
      service_worker: 'background/service-worker.js',
      type: 'module'
    });

    // Chromium-only key gone; Gecko block present.
    expect(firefox).not.toHaveProperty('minimum_chrome_version');
    expect(firefox.browser_specific_settings).toEqual({
      gecko: expect.objectContaining({ strict_min_version: FIREFOX_MIN_VERSION })
    });

    // No permission widening, no world changes.
    expect(firefox.permissions).toEqual(base.permissions);
    expect(firefox.host_permissions).toEqual(base.host_permissions);
    expect(firefox.content_scripts).toEqual(base.content_scripts);
    expect(firefox.manifest_version).toBe(3);
  });
});
