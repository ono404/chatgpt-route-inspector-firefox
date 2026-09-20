import { afterEach, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { handleInstallation, isNoticeUpgrade, UPGRADE_NOTICE_KEY, UPGRADE_NOTICE_PAGE } from '../../src/background/upgrade-notice';

const details = (reason: string, previousVersion?: string) => ({ reason, ...(previousVersion ? { previousVersion } : {}) }) as chrome.runtime.InstalledDetails;
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.resetModules(); });

function setup(version = '1.0.7') {
  const disk: Record<string, unknown> = {};
  const create = vi.fn(async () => ({ id: 1 }));
  const get = vi.fn(async () => structuredClone(disk));
  const set = vi.fn(async (value: object) => { Object.assign(disk, value); });
  vi.stubGlobal('chrome', {
    runtime: { getManifest: () => ({ version }), getURL: (path: string) => `chrome-extension://test/${path}` },
    storage: { local: { get, set } }, tabs: { create }, i18n: { getUILanguage: () => 'en' }
  });
  return { disk, create, get, set };
}

it.each(['1.0.6', '1.0.5', '0.9', '1.0.6.9'])('allows upgrades from %s to the exact notice version', (previous) => {
  expect(isNoticeUpgrade('1.0.7', details('update', previous))).toBe(true);
});

it.each([
  ['1.0.7', 'update', '1.0.7'], ['1.0.7', 'update', '1.0.7.0'], ['1.0.7', 'update', '1.0.8'],
  ['1.0.8', 'update', '1.0.6'], ['1.0.7', 'install', '1.0.6'], ['1.0.7', 'chrome_update', '1.0.6'],
  ['1.0.7', 'shared_module_update', '1.0.6'], ['1.0.7', 'update', ''], ['1.0.7', 'update', 'bad']
])('does not announce current=%s reason=%s previous=%s', (current, reason, previous) => {
  expect(isNoticeUpgrade(current, details(reason, previous))).toBe(false);
});

it('opens one local notice for concurrent events and persists the marker across worker restarts', async () => {
  const { create, disk } = setup();
  await Promise.all([handleInstallation(details('update', '1.0.6')), handleInstallation(details('update', '1.0.6'))]);
  expect(create).toHaveBeenCalledExactlyOnceWith({ url: `chrome-extension://test/${UPGRADE_NOTICE_PAGE}`, active: true });
  expect(disk[UPGRADE_NOTICE_KEY]).toBe(true);
  vi.resetModules();
  const restarted = await import('../../src/background/upgrade-notice');
  await restarted.handleInstallation(details('update', '1.0.6'));
  expect(create).toHaveBeenCalledTimes(1);
  const { clearState } = await import('../../src/background/storage');
  await clearState();
  expect(disk[UPGRADE_NOTICE_KEY]).toBe(true);
  await restarted.handleInstallation(details('update', '1.0.6'));
  expect(create).toHaveBeenCalledTimes(1);
});

it('keeps fresh-install onboarding, without showing or marking the upgrade announcement', async () => {
  const { create, disk } = setup();
  await handleInstallation(details('install'));
  expect(create).toHaveBeenCalledExactlyOnceWith({ url: 'chrome-extension://test/ui/onboarding/index.html' });
  expect(disk[UPGRADE_NOTICE_KEY]).toBeUndefined();
});

it('later versions and same-version development reloads do not read storage or open a notice', async () => {
  const { create, get } = setup('1.0.8');
  await handleInstallation(details('update', '1.0.7'));
  expect(create).not.toHaveBeenCalled();
  expect(get).not.toHaveBeenCalled();
  setup();
  expect(isNoticeUpgrade('1.0.7', details('update', '1.0.7'))).toBe(false);
});

it('does not mark a failed open as shown and permits a retry', async () => {
  const { create, disk } = setup();
  create.mockRejectedValueOnce(new Error('tab unavailable'));
  await expect(handleInstallation(details('update', '1.0.6'))).rejects.toThrow('tab unavailable');
  expect(disk[UPGRADE_NOTICE_KEY]).toBeUndefined();
  await handleInstallation(details('update', '1.0.6'));
  expect(disk[UPGRADE_NOTICE_KEY]).toBe(true);
});

it('storage read failure does not open a tab or change the seen marker', async () => {
  const { get, create, disk } = setup();
  get.mockRejectedValueOnce(new Error('storage unavailable'));
  await expect(handleInstallation(details('update', '1.0.6'))).rejects.toThrow('storage unavailable');
  expect(create).not.toHaveBeenCalled();
  expect(disk[UPGRADE_NOTICE_KEY]).toBeUndefined();
});

it('ships a voluntary local announcement with an exact, user-activated external poll link', () => {
  const html = readFileSync(new URL('../../src/ui/announcement/index.html', import.meta.url), 'utf8');
  expect(html).toContain('https://x.com/liu_9982/status/2100132495455043829?s=20');
  expect(html).toContain('rel="noopener noreferrer"');
  expect(html).toContain('参与完全自愿');
  expect(html).toContain('尚不足以');
  expect(html).not.toMatch(/<(script|iframe|img)[^>]+(?:src|href)="https?:/);
  expect(html).toContain('id="notice-close"');
});
