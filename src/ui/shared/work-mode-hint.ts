import type { UiLanguage } from '../../core/types';
import { t } from './i18n';

export const workModeHintStyles = `
  .work-hint{position:relative;z-index:8;display:inline-block;max-width:116px;justify-self:end}
  .work-trigger.status{display:block;max-width:116px;border:0;padding:0;background:transparent;color:#f3f5ec;cursor:help;text-align:right}
  .work-trigger:focus-visible{outline:2px solid #f3f5ec;outline-offset:2px}
  .work-popover{position:absolute;top:100%;right:0;z-index:9;width:min(290px,calc(100vw - 30px));padding-top:5px;visibility:hidden;opacity:0;white-space:normal}
  .work-popover>span{display:block;padding:12px;border:1px solid #697461;background:#171b16;color:#f3f5ec;box-shadow:0 8px 24px rgba(0,0,0,.4);font:12px/1.65 "Bahnschrift",sans-serif;overflow-wrap:anywhere}
  .work-hint:hover .work-popover,.work-hint:focus-within .work-popover{visibility:visible;opacity:1}
`;

export function workModeHintMarkup(language: UiLanguage): string {
  return `<span class="work-hint"><button class="status work-trigger" type="button" aria-describedby="work-popover">${t(language, 'result.workUnverifiable')}</button><span id="work-popover" class="work-popover" role="tooltip"><span>${t(language, 'work.hint')}</span></span></span>`;
}
