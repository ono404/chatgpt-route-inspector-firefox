import { afterEach, expect, it, vi } from 'vitest';
import { bindNoticeHint, currentNoticeHint, noticeHintMarkup } from '../../src/ui/shared/notice-hint';
import { UPGRADE_NOTICE_PAGE } from '../../src/shared/upgrade-notice';

afterEach(() => vi.unstubAllGlobals());

it.each(['throw', 'reject', 'not-ok', 'ok'])('reports announcement open failures: %s', async (mode) => {
  let click!: (event: { preventDefault: () => void }) => Promise<void>;
  const showError = vi.fn();
  const hint = { addEventListener: vi.fn() };
  const root = { getElementById: (id: string) => id === 'route-notice' ? hint : id === 'notice-error'
    ? { removeAttribute: showError } : id === 'notice-link'
      ? { addEventListener: (_type: string, listener: typeof click) => { click = listener; } } : null };
  vi.stubGlobal('chrome', { runtime: { sendMessage: () => {
    if (mode === 'throw') throw new Error('Extension context invalidated');
    if (mode === 'reject') return Promise.reject(new Error('Worker unavailable'));
    return Promise.resolve({ ok: mode === 'ok', error: 'Open failed' });
  } } });
  bindNoticeHint(root as unknown as ShadowRoot);
  await expect(Promise.resolve().then(() => click({ preventDefault: vi.fn() }))).resolves.toBeUndefined();
  await Promise.resolve();
  expect(showError).toHaveBeenCalledTimes(mode === 'ok' ? 0 : 1);
});

it.each(['zh', 'en'] as const)('shows the temporary source hint in %s only for 1.0.7', (language) => {
  const url = `chrome-extension://example/${UPGRADE_NOTICE_PAGE}`;
  const html = noticeHintMarkup(language, '1.0.7', url);
  expect(html).toContain('class="notice-star"');
  expect(html).toContain('aria-controls="notice-popover">*</button>');
  expect(html).not.toMatch(/[★☆✱✳]/);
  expect(html).toContain('resolved_model_slug');
  expect(html).toContain(`href="${url}"`);
  expect(html).not.toContain('x.com');
  if (language === 'en') expect(html).not.toMatch(/[\u4e00-\u9fff]/);
  for (const version of ['1.0.6', '1.0.8', undefined]) {
    expect(noticeHintMarkup(language, version, url)).toBe('');
  }
});

it('does not build an announcement link after the release gate expires', () => {
  const getURL = vi.fn();
  vi.stubGlobal('chrome', { runtime: { getManifest: () => ({ version: '1.0.8' }), getURL } });
  expect(currentNoticeHint('zh', 'live')).toBe('');
  expect(getURL).not.toHaveBeenCalled();
});

it('never creates a reload-mode notice link even in 1.0.7', () => {
  const getURL = vi.fn();
  vi.stubGlobal('chrome', { runtime: { getManifest: () => ({ version: '1.0.7' }), getURL } });
  expect(currentNoticeHint('en', 'reload')).toBe('');
  expect(getURL).not.toHaveBeenCalled();
});
