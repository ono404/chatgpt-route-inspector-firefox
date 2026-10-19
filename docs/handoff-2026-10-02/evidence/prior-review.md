# cdbf1b3 independent acceptance — 2026-10-02

The principal missing/stale capture identity fix passes independent checks. Strict page-origin locking has one remaining P2 gap, so the claim that every incorrect page identity is rejected is not fully supported.

Repository: `C:\workspace\run-01`, HEAD `cdbf1b35c16ef9e996d509bdbcee94e93c78c368`. No repository source was edited during acceptance. All independent results are in this directory.

## Confirmed results

- typecheck, lint, verify:firefox: exit 0.
- Business tests: 38 files, 442 passed, coverage 98.1/91.79/100/98.1; exit 0.
- Firefox tooling: 82 tests, OK; exit 0. The failure messages within its log are intentional negative-test outputs.
- Frozen XPI on independently launched Firefox 157.0: 32/32, exit 0, trusted temporary profile, browser stopped and profile removed by this probe. See `independent-positive.json` and `real-probe-actual.log`.
- Probe hash `17297ab4e1d394f0b150fbcc5493cd1369c1271b1002f17e56087bed254e681e` matches the commit and independently generated result.
- The frozen XPI/build record/source ZIP hashes remain `04af228b03f85e954d894a859fb87afcf1bfbc9cd449da881c2f25f99c0165ae`, `a2028179ed18602da5d6be288dd2142a0140dab0d64bfdb6fcd267afaba263a1`, `51523360d4063fc939177672b9bf990278a1e0495f4e715f5e22b0cc49888846`.
- Committed changes are confined to the reported 20 files; business directories remain identical to upstream dd5ea336. The working tree is clean after acceptance.
- Independent scripted peers: empty/missing ID, native fetch, old ID, changed result-time context, and changed result-time context URL all produce identityOk=true, check 22 false, exit 4. The legal control produces exit 0.

## P2: nondefault port is silently accepted as the locked origin

Location: `ff-marionette.py:969-982`, especially the scheme/hostname predicate at line 979, and the final page_ok check at 1065-1066.

`chatgpt_pages()` discards the port and returns only (handle, path). Consequently `https://chatgpt.com:444/` is treated as equivalent to `https://chatgpt.com/`, although their origins differ. It is also accepted again at the final page identity check.

Independent counterexample changes only the scripted peer's WebDriver:GetCurrentURL response for the ChatGPT homepage to `https://chatgpt.com:444/`, leaving the background context/record at `https://chatgpt.com/`. The native page identity and background identity disagree, but the unmodified committed probe reports check 22 PASS and the whole run exits 0. See `nondefault-port.json`, `nondefault-port.log`, and `adversarial-summary.json`. This is a scripted-peer proof of the oracle gap, not evidence of a real service running at port 444 or a Firefox product exploit.

Minimal correction: validate the effective HTTPS port as 443 (omitted and explicit :443 are equivalent); preserve the host, scheme, path and unique-handle checks. Add red/green coverage for wrong port before send and wrong port at result time, alongside legal default/explicit-443 controls. Keep the frozen package and business source unchanged.

## Additional non-blocking observation: multiple marker matches

The poll uses `.find`, while `markerMatches` is evidence only. Two valid new captures with the same marker/tab/context are accepted. `duplicate-results.json` proves current Python acceptance; `replay-poll.mjs` executes the actual extracted JavaScript on two records and `actual-js-duplicate-result.json` confirms the first is selected.

This does not by itself invalidate the narrower claim that a new matching capture exists. The published regression requirement clearly covers multiple pages; unique result cardinality is an additional requirement and is not a blocking finding here. If “ambiguity always fails” is intended to include multiple result records, specify that separately or narrow the report's wording.

## Reproduction

From the repository, run the independently written script with the interpreter used by its tooling runner:

```powershell
& 'C:\Users\<user>\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B 'C:\Users\<user>\AppData\Local\Temp\ff-check22-accept-a755a99d0a10457891ac8785e3720425\adversarial.py'
node 'C:\Users\<user>\AppData\Local\Temp\ff-check22-accept-a755a99d0a10457891ac8785e3720425\replay-poll.mjs'
```

These use temporary synthetic packages and scripted peers. They do not rebuild, install into the daily profile, sign or publish the frozen delivery.

The separate authenticated successful-SSE, stream_parse_failed root cause, real update event, FF128, quota, Chromium E2E, signing/AMO and daily-installation limitations remain unresolved; this acceptance does not promote them to verified.
