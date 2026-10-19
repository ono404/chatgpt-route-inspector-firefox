import contextlib
import copy
import io
import json
import pathlib
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(r'C:\workspace\run-01')
OUT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / 'tests/firefox-tooling'))
import test_ff_marionette_run as mod
from fake_marionette import FakeMarionette

CHECK = '22.deep-research-capture-taskkind'
cases = [
    ('control', {}, None),
    ('empty-id', {'answers': {'drTurn': {'captureId': '', 'taskKind': 'deep_research', 'verdict': 'deep_research'}}}, None),
    ('missing-id', {'answers': {'drTurn': {'taskKind': 'deep_research', 'verdict': 'deep_research'}}}, None),
    ('native-fetch', {'answers': {'drCapture': {'started': True, 'fetchName': 'fetch'}}}, None),
    ('old-id', {'answers': {'drTurn': {'captureId': '0f1e2d3c-4b5a-4978-8967-5a4b3c2d1e0f', 'taskKind': 'deep_research', 'verdict': 'deep_research'}}}, None),
    ('wrong-after-context', {}, 'wrong-after-context'),
    ('wrong-after-url', {}, 'wrong-after-url'),
    ('nondefault-port', {}, 'nondefault-port'),
    ('duplicate-results', {}, 'duplicate-results'),
]
summaries = []
for name, kwargs, mode in cases:
    class Peer(FakeMarionette):
        def _on_WebDriver_GetCurrentURL(self, params):
            value = super()._on_WebDriver_GetCurrentURL(params)
            if mode == 'nondefault-port' and value.get('value') == 'https://chatgpt.com/':
                return {'value': 'https://chatgpt.com:444/'}
            return value

        def _answer(self, script, args):
            value = super()._answer(script, args)
            if 'dr22-poll' in script:
                if mode == 'wrong-after-context':
                    value['ctxId'] = 'wrong-context-after-send'
                if mode == 'wrong-after-url':
                    value['ctxPageUrl'] = 'https://chatgpt.com/c/different-page'
                if mode == 'duplicate-results':
                    first = copy.deepcopy(value['found'])
                    second = copy.deepcopy(first)
                    second['captureId'] = '4f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d'
                    value['markerMatches'] = [first, second]
            return value

    original = mod.FakeMarionette
    mod.FakeMarionette = Peer
    harness = mod.RunHarness()
    harness.setUp()
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = harness.run_probe(fake_kwargs=kwargs)
        payload = harness.saved()
        (OUT / (name + '.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (OUT / (name + '.log')).write_text(buf.getvalue(), encoding='utf-8')
        check = next(x for x in payload['results'] if x['check'] == CHECK)
        row = {'name': name, 'exit': code, 'check22': check['ok'], 'identityOk': payload['meta']['summary']['identityOk'], 'failed': payload['meta']['summary']['failedChecks']}
        summaries.append(row)
        if name == 'control':
            poll = next(params for method, params in harness.fake.calls if method == 'WebDriver:ExecuteScript' and 'dr22-poll' in params.get('script', ''))
            (OUT / 'actual-poll.json').write_text(json.dumps(poll, ensure_ascii=False), encoding='utf-8')
            (OUT / 'actual-found.json').write_text(json.dumps(json.loads(check['detail'])['found'], ensure_ascii=False), encoding='utf-8')
    finally:
        harness.doCleanups()
        mod.FakeMarionette = original

(OUT / 'adversarial-summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')
print(json.dumps(summaries, indent=2))
