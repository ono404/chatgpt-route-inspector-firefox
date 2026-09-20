import { browserUiLanguage } from '../../core/language';
import { getState } from '../shared/client';
import { applyStaticTranslations, bindLanguageSwitch } from '../shared/i18n';

// This page's language switch is local: reading an announcement must not change settings.
let languageChosen = false;
applyStaticTranslations(browserUiLanguage());
bindLanguageSwitch((language) => { languageChosen = true; applyStaticTranslations(language); });
void getState().then((state) => {
  if (!languageChosen) applyStaticTranslations(state.settings.uiLanguage);
}).catch(() => {
  // All notice content is already rendered; browser language remains a usable fallback.
});
document.querySelector('#notice-close')?.addEventListener('click', () => window.close());
