import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createTurn } from '../../src/core/turns';

describe('route-turn schema', () => {
  it('accepts auto reasoning and both explicit and fallback route sources', () => {
    const schema = JSON.parse(readFileSync(new URL('../../schemas/route-turn.v1.schema.json', import.meta.url), 'utf8'));
    for (const field of ['resolvedModelSlug', 'responseModelSlug', 'domModelSlug']) {
      const turn = createTurn({
        captureId: field, source: 'page_fetch', captureMode: 'live', phase: 'completed',
        observedAt: '2026-09-12T00:00:00Z', [field]: 'gpt-5-5-auto-thinking'
      });
      expect(schema.properties.schemaVersion.const).toBe(turn.schemaVersion);
      expect(schema.properties.verdict.enum).toContain(turn.verdict);
      for (const source of turn.routeModelSources) expect(schema.properties.routeModelSources.items.enum).toContain(source);
    }
  });
  it('declares every property emitted by RouteTurn and requires the complete record', () => {
    const schema = JSON.parse(readFileSync(new URL('../../schemas/route-turn.v1.schema.json', import.meta.url), 'utf8')) as {
      properties: Record<string, unknown>; required: string[];
    };
    const turn = createTurn({
      captureId: 'schema-test', source: 'page_fetch', captureMode: 'live', phase: 'completed',
      observedAt: '2026-08-11T01:00:00.000Z'
    });
    expect(Object.keys(turn).filter((key) => !(key in schema.properties))).toEqual([]);
    expect(Object.keys(turn).filter((key) => !schema.required.includes(key))).toEqual([]);
  });
  it('accepts the suspected-downgrade verdict emitted for live and reload captures', () => {
    const schema = JSON.parse(readFileSync(new URL('../../schemas/route-turn.v1.schema.json', import.meta.url), 'utf8'));
    for (const captureMode of ['live', 'reload'] as const) {
      const turn = createTurn({
        captureId: captureMode, source: captureMode === 'live' ? 'page_fetch' : 'conversation_record',
        captureMode, phase: 'completed', observedAt: '2026-09-25T00:00:00Z',
        serverModelSlug: 'gpt-5-6-pro'
      });
      expect(turn.verdict).toBe('suspected_downgrade');
      expect(schema.properties.schemaVersion.const).toBe(turn.schemaVersion);
      expect(schema.properties.verdict.enum).toContain(turn.verdict);
    }
  });
  it('accepts the Work-mode unverifiable verdict', () => {
    const schema = JSON.parse(readFileSync(new URL('../../schemas/route-turn.v1.schema.json', import.meta.url), 'utf8'));
    const turn = createTurn({ captureId: 'work', source: 'conversation_record', captureMode: 'reload',
      phase: 'completed', observedAt: '2026-09-25T00:00:00Z', responseModelSlug: 'gpt-6-astra-wm' });
    expect(turn.verdict).toBe('work_unverifiable');
    expect(schema.properties.verdict.enum).toContain(turn.verdict);
  });
});
