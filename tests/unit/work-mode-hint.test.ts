import { expect, it } from 'vitest';
import { workModeHintMarkup } from '../../src/ui/shared/work-mode-hint';

it.each(['zh', 'en'] as const)('anchors the Work explanation to the white status in %s', (language) => {
  const html = workModeHintMarkup(language);
  expect(html).toContain('class="status work-trigger"');
  expect(html).toContain('role="tooltip"');
  expect(html).toContain(language === 'zh' ? '无法判断' : 'Cannot determine');
  expect(html).toContain('Codex');
  expect(html).not.toContain('href=');
  if (language === 'en') expect(html).not.toMatch(/[\u4e00-\u9fff]/);
});
