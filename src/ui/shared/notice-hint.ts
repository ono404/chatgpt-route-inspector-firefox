import type { CaptureMode, UiLanguage } from '../../core/types';
import type { RuntimeRequest, RuntimeResponse } from '../../shared/messages';
import { UPGRADE_NOTICE_PAGE, UPGRADE_NOTICE_VERSION } from '../../shared/upgrade-notice';
import { t } from './i18n';

export const noticeHintStyles = `
  .notice-source-label{position:relative}
  /* Keep the entire path from the source row to any part of the link hoverable. */
  .notice-source-label:has(.notice-hint:not([data-dismissed])):hover::after{content:"";position:absolute;left:0;top:0;bottom:0;z-index:4;width:min(286px,calc(100vw - 60px))}
  .probe:lang(en) .meta{grid-template-columns:max-content minmax(0,1fr);align-items:center}
  .probe:lang(en) .meta>span{white-space:nowrap}
  .notice-hint{display:inline-block;margin-left:3px;vertical-align:baseline}
  .notice-star{position:relative;z-index:6;border:0;padding:0 3px;background:transparent;color:#a9f04d;cursor:help;font:400 16px/14px Arial,sans-serif}
  .notice-star:focus-visible,.notice-popover a:focus-visible{outline:2px solid #a9f04d;outline-offset:2px}
  .notice-popover{position:absolute;left:0;bottom:100%;z-index:5;width:min(286px,calc(100vw - 60px));padding-bottom:5px;visibility:hidden;opacity:0;white-space:normal}
  .notice-popover a{display:block;padding:12px;border:1px solid #697461;background:#171b16;color:#f3f5ec;box-shadow:0 8px 24px rgba(0,0,0,.4);font:12px/1.65 "Bahnschrift",sans-serif;text-decoration:none;overflow-wrap:anywhere}
  .notice-popover a:hover{border-color:#a9f04d}
  .notice-popover strong{color:#a9f04d;text-decoration:underline;text-underline-offset:3px;font-weight:400;white-space:nowrap}
  .notice-source-label:hover .notice-popover,.notice-hint:focus-within .notice-popover{visibility:visible;opacity:1}
  .notice-hint[data-dismissed] .notice-popover{visibility:hidden;opacity:0}
  .notice-error{display:block;color:#f07868}.notice-error[hidden]{display:none}
`;

export function noticeHintMarkup(language: UiLanguage, version: string | undefined, url: string): string {
  if (version !== UPGRADE_NOTICE_VERSION) return '';
  // All text comes from the packaged dictionary; URL is supplied by runtime.getURL.
  return `<span id="route-notice" class="notice-hint"><button id="notice-star" class="notice-star" type="button" aria-label="${t(language, 'notice.hintLabel')}" aria-controls="notice-popover">*</button><span id="notice-popover" class="notice-popover"><a id="notice-link" href="${url}" target="_blank" rel="noopener noreferrer">${t(language, 'notice.hint')} <strong>${t(language, 'notice.readMore')}</strong><span id="notice-error" class="notice-error" role="alert" hidden>${t(language, 'notice.openFailed')}</span></a></span></span>`;
}

export function currentNoticeHint(language: UiLanguage, mode: CaptureMode): string {
  if (mode !== 'live') return '';
  const version = chrome.runtime.getManifest?.().version;
  return version === UPGRADE_NOTICE_VERSION
    ? noticeHintMarkup(language, version, chrome.runtime.getURL(UPGRADE_NOTICE_PAGE)) : '';
}

export function bindNoticeHint(root: ShadowRoot): void {
  const hint = root.getElementById('route-notice');
  if (!hint) return;
  hint.addEventListener('pointerenter', () => hint.removeAttribute('data-dismissed'));
  hint.addEventListener('focusin', () => hint.removeAttribute('data-dismissed'));
  hint.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      root.getElementById('notice-star')?.focus();
      hint.setAttribute('data-dismissed', '');
    }
  });
  root.getElementById('notice-star')?.addEventListener('click', () => hint.removeAttribute('data-dismissed'));
  root.getElementById('notice-link')?.addEventListener('click', async (event) => {
    event.preventDefault();
    // Content pages cannot navigate directly to a private extension page.
    try {
      const response = await chrome.runtime.sendMessage<RuntimeRequest, RuntimeResponse>({ type: 'route:open-announcement' });
      if (!response.ok) throw new Error(response.error);
    } catch {
      root.getElementById('notice-error')?.removeAttribute('hidden');
    }
  });
}
