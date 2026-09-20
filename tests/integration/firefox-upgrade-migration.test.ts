// Firefox-upgrade verification artifact (2026-09-20, upstream v1.0.5 -> v1.0.7).
//
// Purpose: prove the new storage layer (revision / captureContexts / clearedAt,
// schema 1.4.0 -> 1.7.0) still loads and migrates a *pre-upgrade* snapshot.
// All snapshots below are synthetic. No real user export or profile data is used,
// and `readState()` must never write back to storage.
import { afterEach, expect, it, vi } from 'vitest';
import { EMPTY_QUOTA_FIELDS, ROUTE_SCHEMA_VERSION } from '../../src/core/types';

const STORAGE_KEY = 'chatgptRouteInspectorStateV1';

const legacyBase = {
  schema: 'chatgpt-route-observation',
  schemaVersion: '1.4.0',
  captureId: 'legacy-1',
  phase: 'completed',
  tabId: 7,
  pageUrl: 'https://chatgpt.com/c/example',
  networkRequestId: null,
  observedAt: '2026-08-10T01:00:00.000Z',
  startedAt: '2026-08-10T01:00:00.000Z',
  completedAt: '2026-08-10T01:00:03.000Z',
  requestedModel: 'gpt-5-6-pro',
  resolvedModelSlug: 'gpt-5-5-mini',
  effectiveModel: 'gpt-5-5-mini',
  confidence: 0.88,
  confidenceLabel: 'high'
};

/** Snapshot as written by the 1.0.5 build: no revision, no captureContexts, no clearedAt. */
function legacyStoredState() {
  return {
    turns: [
      { ...legacyBase, sources: ['page_fetch'] },
      {
        ...legacyBase, captureId: 'legacy-auto', sources: ['page_fetch'], schemaVersion: '1.5.0', verdict: 'conflict',
        requestedModel: 'gpt-5-6', responseModelSlug: 'gpt-5-6-thinking',
        resolvedModelSlug: 'gpt-5-6-auto-thinking', serverModelSlug: 'gpt-5-6-auto-thinking'
      },
      { ...legacyBase, captureId: 'legacy-retired', sources: ['retired_adapter'] }
    ],
    powReadings: [],
    settings: {
      overlayEnabled: true, overlayMode: 'compact', overlayMinimized: true, retentionLimit: 42,
      captureMode: 'reload', autoCaptureEnabled: true, uiLanguage: 'zh'
    },
    parserHealth: { lastSuccessAt: '2026-08-09T00:00:00.000Z', lastFailureAt: null, consecutiveFailures: 0 }
  };
}

function setup(disk: Record<string, unknown> | null) {
  const store: Record<string, unknown> = disk ? structuredClone(disk) : {};
  const get = vi.fn(async (key: string) => (key in store ? { [key]: structuredClone(store[key]) } : {}));
  const set = vi.fn(async (value: Record<string, unknown>) => { Object.assign(store, structuredClone(value)); });
  vi.stubGlobal('chrome', { storage: { local: { get, set } }, i18n: { getUILanguage: () => 'en' } });
  return { store, get, set };
}

async function readState() {
  const { readState: load } = await import('../../src/background/storage');
  return load();
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.resetModules(); });

it('migrates a pre-upgrade 1.0.5 snapshot to schema 1.7.0 without writing to storage', async () => {
  const { set } = setup({ [STORAGE_KEY]: legacyStoredState() });
  const state = await readState();

  // Reading an old snapshot is read-only: no silent rewrite of user data.
  expect(set).not.toHaveBeenCalled();

  // New state fields are back-filled with safe defaults.
  expect(state.revision).toBe(0);
  expect(state).not.toHaveProperty('clearedAt');
  expect(state.captureContexts).toEqual({});

  // Every valid legacy turn is re-normalized at the current schema version.
  expect(state.turns).toHaveLength(2);
  for (const turn of state.turns) expect(turn.schemaVersion).toBe(ROUTE_SCHEMA_VERSION);
  expect(state.turns.map((turn) => turn.captureId).sort()).toEqual(['legacy-1', 'legacy-auto']);
  // The retired source adapter record is dropped, as before the upgrade.
  expect(state.turns.some((turn) => turn.captureId === 'legacy-retired')).toBe(false);
});

it('reassesses legacy verdicts and back-fills the v1.7.0 quota/quota-timestamp fields', async () => {
  setup({ [STORAGE_KEY]: legacyStoredState() });
  const state = await readState();

  const live = state.turns.find((turn) => turn.captureId === 'legacy-1');
  expect(live).toMatchObject({ captureMode: 'live', routeModel: 'gpt-5-5-mini', verdict: 'mismatch' });
  // Fields introduced after 1.0.5 exist and default to null rather than undefined.
  for (const [field, value] of Object.entries(EMPTY_QUOTA_FIELDS)) {
    expect(live).toHaveProperty(field, value);
  }
  // Legacy-only fields are not carried forward.
  expect(live).not.toHaveProperty('confidence');
  expect(live).not.toHaveProperty('effectiveModel');

  const auto = state.turns.find((turn) => turn.captureId === 'legacy-auto');
  expect(auto).toMatchObject({ verdict: 'auto_reasoning', routeModel: 'gpt-5-6-auto-thinking' });
});

it('preserves user settings and parser health across the upgrade', async () => {
  setup({ [STORAGE_KEY]: legacyStoredState() });
  const state = await readState();
  expect(state.settings).toMatchObject({
    overlayMode: 'compact', overlayMinimized: true, retentionLimit: 42,
    captureMode: 'reload', autoCaptureEnabled: true, uiLanguage: 'zh'
  });
  expect(state.parserHealth).toEqual({ lastSuccessAt: '2026-08-09T00:00:00.000Z', lastFailureAt: null, consecutiveFailures: 0 });
});

it('keeps valid capture contexts from the new build and drops malformed ones', async () => {
  const validContext = {
    id: 'ctx-1', documentId: 'doc-1', documentStartedAt: 1_760_000_000_000, visitStartedAt: 1_760_000_000_000,
    revision: 3, pageUrl: 'https://chatgpt.com/c/example', reloadEligible: true
  };
  setup({ [STORAGE_KEY]: {
    ...legacyStoredState(),
    revision: 9,
    captureContexts: { 7: validContext, 8: { id: 'broken' }, notANumber: validContext }
  } });
  const state = await readState();
  expect(state.revision).toBe(9);
  expect(Object.keys(state.captureContexts ?? {})).toEqual(['7']);
  expect(state.captureContexts?.[7]).toEqual(validContext);
});

it('falls back to a default state when no snapshot exists yet', async () => {
  const { set } = setup(null);
  const state = await readState();
  expect(set).not.toHaveBeenCalled();
  expect(state).toMatchObject({ revision: 0, turns: [], powReadings: [] });
  // A fresh install has no capture-context map yet; it is created on first capture.
  expect(state.captureContexts ?? {}).toEqual({});
  expect(state.settings.retentionLimit).toBeGreaterThan(0);
});
