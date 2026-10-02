"""End-to-end regression tests for the probe control flow (no real browser).

The browser is replaced by an in-process scriptable peer (`fake_marionette`),
so the code under test is the probe itself: which checks it runs, how a failing
check or an aborted run is reported, and which exit code it returns.

Note: real-browser red/green runs are evidenced separately in
`docs/upgrade-2026-09-20/`; these tests exist so the failure conditions can be
re-proved deterministically without Firefox.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe_loader  # noqa: E402
from fake_marionette import FakeMarionette  # noqa: E402
from probe_loader import build_record, write_dist, zip_dist  # noqa: E402

PROBE = probe_loader.load_probe()
OMIT_OUT = object()  # sentinel: run with no --out at all


class FakeProcess:
    """Stands in for the browser process the probe launched."""

    def __init__(self):
        self.pid = 4242
        self._alive = True
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def kill(self):
        self.killed = True
        self._alive = False

    def wait(self, timeout=None):
        return 0


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class RunHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-run-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = write_dist(os.path.join(self.tmp, "dist"))
        self.xpi = zip_dist(self.dist, os.path.join(self.tmp, "good.xpi"))
        self.record_path = os.path.join(self.tmp, "good.build.json")
        with open(self.record_path, "w", encoding="utf-8") as handle:
            json.dump(build_record(PROBE, self.dist, self.xpi), handle)
        self.out = os.path.join(self.tmp, "results.json")
        self.launched = []
        self.fake = None
        self.resume = {}

    def run_probe(self, fake_kwargs=None, extra=None, out=OMIT_OUT, wait_for_port=None,
                  startup_timeout=None):
        """Run the probe against the fake browser. Only wall-clock waits are
        compressed; no control flow or assertion is altered."""
        fake_kwargs = fake_kwargs or {}
        process = FakeProcess()

        def fake_launch(firefox_exe, profile_dir, port):
            self.launched.append({"firefox": firefox_exe, "profile": profile_dir, "port": port})
            return process, ["fake-firefox", "-profile", profile_dir]

        def fake_wait(host, port, timeout, proc):
            if wait_for_port is not None:
                return wait_for_port(host, port, timeout, proc)

        def fake_marionette(host, port):
            self.fake = FakeMarionette(self.launched[-1]["profile"], **fake_kwargs)
            return self.fake

        argv = ["--xpi", self.xpi, "--expect-build-record", self.record_path,
                "--dist", self.dist, "--label", "regression",
                "--firefox", os.path.join(self.tmp, "fake-firefox.exe")]
        if out is OMIT_OUT:
            argv += ["--out", self.out]
        elif out is not None:
            argv += ["--out", out]
        if startup_timeout is not None:
            argv += ["--startup-timeout", str(startup_timeout)]
        argv += extra or []

        originals = (PROBE.launch_firefox, PROBE.wait_for_port, PROBE.Marionette)
        PROBE.launch_firefox = fake_launch
        PROBE.wait_for_port = fake_wait
        PROBE.Marionette = fake_marionette
        try:
            with mock.patch("time.sleep", lambda _seconds: None):
                code = PROBE.main(argv)
        finally:
            PROBE.launch_firefox, PROBE.wait_for_port, PROBE.Marionette = originals
        self.process = process
        return code

    def saved(self, path=None):
        with open(path or self.out, encoding="utf-8") as handle:
            return json.load(handle)

    def assert_cleanup(self):
        self.assertTrue(self.process.terminated, "the launched process must be stopped")
        profile = self.launched[0]["profile"]
        self.assertFalse(os.path.exists(profile), "the temporary profile must be removed")


class TestGreenRun(RunHarness):
    def test_complete_green_run_exits_zero(self):
        code = self.run_probe()
        self.assertEqual(code, PROBE.EXIT_OK)
        payload = self.saved()
        summary = payload["meta"]["summary"]
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["missingChecks"], [])
        self.assertTrue(summary["identityOk"])
        self.assertIsNone(payload["meta"]["fatal"])
        for name in PROBE.REQUIRED_CHECKS:
            self.assertIn(name, [c["check"] for c in payload["results"]], name)
        self.assertIn("0c.dist-matches-record", [c["check"] for c in payload["results"]])
        self.assert_cleanup()

    def test_browser_identity_is_recorded_from_the_session_not_the_environment(self):
        os.environ["FF_PROFILE"] = "C:\\this-is-not-the-profile"
        try:
            self.run_probe()
        finally:
            del os.environ["FF_PROFILE"]
        payload = self.saved()
        reported = payload["meta"]["session"]["capabilities"]["moz:profile"]
        # The recorded profile must come from the browser, be the one this run
        # created, and never be a caller-supplied label.
        self.assertEqual(os.path.abspath(reported),
                         os.path.abspath(self.launched[0]["profile"]))
        self.assertNotIn("this-is-not-the-profile", json.dumps(payload["meta"]))
        checks = {c["check"]: c for c in payload["results"]}
        self.assertTrue(checks["0e.session-profile"]["ok"])


class TestFailingRuns(RunHarness):
    def test_failed_check_exits_nonzero_and_names_the_check(self):
        code = self.run_probe(fake_kwargs={"answers": {"popup": "   "}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        self.assertEqual(payload["meta"]["summary"]["failedChecks"], ["6.popup-renders"])
        self.assertEqual(payload["meta"]["exitCode"], PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("6.popup-renders", payload["meta"]["exitReason"])

    def test_missing_announcement_page_exits_nonzero(self):
        code = self.run_probe(extra=["--announcement-ui", "ui/announcement/missing-manager-test.html"])
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        self.assertIn("14.announcement-page", payload["meta"]["summary"]["failedChecks"])

    def test_install_failure_leaves_an_incomplete_run(self):
        code = self.run_probe(fake_kwargs={"fail_install": True})
        self.assertEqual(code, PROBE.EXIT_INCOMPLETE)
        payload = self.saved()
        self.assertIn("1.install-no-manifest-error", payload["meta"]["summary"]["failedChecks"])
        self.assertIn("9.page-hook-MAIN-world", payload["meta"]["summary"]["missingChecks"])

    def test_missing_extension_uuid_leaves_an_incomplete_run(self):
        code = self.run_probe(fake_kwargs={"discover_uuid": False})
        self.assertEqual(code, PROBE.EXIT_INCOMPLETE)
        payload = self.saved()
        self.assertTrue(payload["meta"]["summary"]["missingChecks"])

    def test_check_level_exception_is_recorded_and_does_not_abort_the_run(self):
        # A protocol error while running one group of checks must fail exactly
        # those checks, keep the remaining checks running, and stay non-zero.
        code = self.run_probe(fake_kwargs={"fail_new_window": True})
        self.assertNotEqual(code, PROBE.EXIT_OK)
        payload = self.saved()
        failed = payload["meta"]["summary"]["failedChecks"]
        self.assertIn("9.page-hook-MAIN-world", failed)
        self.assertIn("10.bridge-overlay-ISOLATED", failed)
        executed = [c["check"] for c in payload["results"]]
        self.assertIn("15.open-announcement-target", executed)
        self.assertIn("12.capture-context-registered", executed)
        self.assertTrue(self.process.terminated)


class TestRuntimeAnomalyEvidence(RunHarness):
    def test_launch_timeout_is_non_zero_and_saves_evidence(self):
        def timeout(host, port, seconds, proc):
            raise TimeoutError("Marionette port never opened (synthetic)")

        code = self.run_probe(wait_for_port=timeout, startup_timeout=1)
        self.assertEqual(code, PROBE.EXIT_FATAL)
        payload = self.saved()
        self.assertEqual(payload["meta"]["exitCode"], PROBE.EXIT_FATAL)
        self.assertIn("TimeoutError", payload["meta"]["fatal"])
        self.assertTrue(payload["meta"]["summary"]["missingChecks"])
        self.assert_cleanup()

    def test_connection_refused_is_non_zero_and_saves_evidence(self):
        def refused(host, port, seconds, proc):
            raise ConnectionRefusedError("synthetic: nothing is listening")

        code = self.run_probe(wait_for_port=refused)
        self.assertEqual(code, PROBE.EXIT_FATAL)
        payload = self.saved()
        self.assertIn("ConnectionRefusedError", payload["meta"]["fatal"])
        self.assert_cleanup()


class TestV110TaskKindChecks(RunHarness):
    """The v1.1.0 checks must be able to fail, not merely to pass.

    A green run proves the checks exist; these cases prove each new check
    actually reads the thing it claims to read. The schema expectation is an
    equality against the probe's own ROUTE_SCHEMA_VERSION, so a record from any
    other build is rejected rather than tolerated.
    """

    def test_expected_schema_version_is_the_v110_record_version(self):
        self.assertEqual(PROBE.ROUTE_SCHEMA_VERSION, "1.9.0")
        self.assertIn("7.synthetic-observation-pipeline", PROBE.REQUIRED_CHECKS)

    def test_new_task_checks_are_required(self):
        for name in ("20.task-kind-verdicts", "21.research-planning-report-split",
                     "22.deep-research-capture-taskkind", "23.ui-task-filters",
                     "24.ui-research-model-split"):
            self.assertIn(name, PROBE.REQUIRED_CHECKS, name)

    def test_stale_schema_version_fails_the_pipeline_check(self):
        # A record left at the previous version must not be accepted.
        code = self.run_probe(fake_kwargs={"answers": {"turn": {
            "ok": True, "turns": 1, "verdict": "mismatch", "route": "gpt-5-5-mini",
            "req": "gpt-5-6-pro", "schemaVersion": "1.8.0"}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        self.assertIn("7.synthetic-observation-pipeline",
                      payload["meta"]["summary"]["failedChecks"])

    def test_future_schema_version_is_also_rejected(self):
        code = self.run_probe(fake_kwargs={"answers": {"turn": {
            "ok": True, "turns": 1, "verdict": "mismatch", "route": "gpt-5-5-mini",
            "req": "gpt-5-6-pro", "schemaVersion": "2.0.0"}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("7.synthetic-observation-pipeline",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_downgraded_image_task_fails_the_task_kind_check(self):
        # If a dedicated task were reported as a downgrade, check 20 must fail.
        code = self.run_probe(fake_kwargs={"answers": {"taskKinds": {
            "image": {"verdict": "suspected_downgrade", "taskKind": "image_generation",
                      "route": "gpt-5-6-pro", "report": None, "schemaVersion": "1.9.0"},
            "research": {"verdict": "deep_research", "taskKind": "deep_research",
                         "route": "gpt-5-6-pro", "report": "gpt-5-6-instant",
                         "schemaVersion": "1.9.0"}}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("20.task-kind-verdicts",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_report_model_folded_into_planner_fails_the_split_check(self):
        code = self.run_probe(fake_kwargs={"answers": {"researchSplit": {
            "verdict": "deep_research", "planner": "gpt-5-6-thinking",
            "report": "gpt-5-6-thinking"}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("21.research-planning-report-split",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_hook_that_never_sees_the_task_fails_check_22(self):
        # The capture path must derive the kind; a null kind means the hook
        # did not identify the Deep Research request.
        code = self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "hook-generated-uuid-1", "taskKind": None,
            "verdict": "normal", "captureContextId": "ctx-1"}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("22.deep-research-capture-taskkind",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_prefilled_capture_id_fails_check_22(self):
        # A captureId invented by the probe is not evidence the hook ran.
        code = self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "ff-probe-fabricated", "taskKind": "deep_research",
            "verdict": "deep_research", "captureContextId": "ctx-1"}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("22.deep-research-capture-taskkind",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_missing_task_filter_fails_the_ui_check(self):
        code = self.run_probe(fake_kwargs={"answers": {"uiFilters": {
            "filters": ["all", "normal"], "deepSelected": False, "imageSelected": False}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("23.ui-task-filters",
                      self.saved()["meta"]["summary"]["failedChecks"])

    def test_ui_report_row_showing_the_planner_fails(self):
        code = self.run_probe(fake_kwargs={"answers": {"uiSplit": {
            "planner": "gpt-5-6-thinking", "report": "gpt-5-6-thinking", "pairs": []}}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertIn("24.ui-research-model-split",
                      self.saved()["meta"]["summary"]["failedChecks"])


class TestCheck22CaptureIdentity(RunHarness):
    """Check 22 must prove the capture's identity, not merely its existence.

    Each counterexample breaks exactly one condition of the check and must fail
    the check and the whole run (exit 4). The legal peer (no overrides) must
    still exit 0. The check must be a required check, so a failing condition is
    never silently dropped.
    """

    CHECK = "22.deep-research-capture-taskkind"

    def assert_check_failed(self, code):
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        self.assertIn(self.CHECK, payload["meta"]["summary"]["failedChecks"])
        self.assertIn(self.CHECK, PROBE.REQUIRED_CHECKS)
        checks = {c["check"]: c for c in payload["results"]}
        self.assertFalse(checks[self.CHECK]["ok"])

    def test_legal_new_capture_passes(self):
        code = self.run_probe()
        self.assertEqual(code, PROBE.EXIT_OK)
        payload = self.saved()
        check = next(c for c in payload["results"] if c["check"] == self.CHECK)
        self.assertTrue(check["ok"], check)
        evidence = json.loads(check["detail"])
        # The marker is generated per run and shared by request and lookup.
        self.assertTrue(evidence["markerModel"].startswith("gpt-6-dr-"))
        self.assertNotIn(evidence["found"]["captureId"], evidence["beforeIds"])
        self.assertGreater(evidence["afterRevision"], evidence["beforeRevision"])

    def test_missing_capture_id_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": None, "taskKind": "deep_research", "verdict": "deep_research"}}}))

    def test_empty_capture_id_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "", "taskKind": "deep_research", "verdict": "deep_research"}}}))

    def test_blank_capture_id_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "   ", "taskKind": "deep_research", "verdict": "deep_research"}}}))

    def test_malformed_capture_id_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "hook-generated-uuid-1", "taskKind": "deep_research",
            "verdict": "deep_research"}}}))

    def test_missing_context_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drLock": {
            "tabCount": 1, "tabId": 4242, "stateRevision": 20, "ctxId": None,
            "ctxPageUrl": "https://chatgpt.com/", "ctxRevision": 11,
            "beforeIds": ["0f1e2d3c-4b5a-4978-8967-5a4b3c2d1e0f"]}}}))

    def test_mismatched_context_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "3f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d", "taskKind": "deep_research",
            "verdict": "deep_research", "captureContextId": "ctx-other"}}}))

    def test_native_fetch_fails(self):
        # If the shipped hook did not wrap fetch, the request never entered the
        # inspection path and the record cannot be attributed to it.
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drCapture": {
            "started": True, "fetchName": "fetch"}}}))

    def test_unstarted_request_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drCapture": {
            "started": False, "fetchName": "routeInspectorFetch"}}}))

    def test_old_record_with_valid_uuid_fails(self):
        # A well-formed id is not enough: it must be a capture that did not
        # already exist before the request was sent.
        old_id = "0f1e2d3c-4b5a-4978-8967-5a4b3c2d1e0f"
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": old_id, "taskKind": "deep_research", "verdict": "deep_research"}}}))

    def test_wrong_request_marker_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "3f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d", "taskKind": "deep_research",
            "verdict": "deep_research", "requestedModel": "gpt-6-dr-deadbeefdeadbeef"}}}))

    def test_wrong_tab_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "3f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d", "taskKind": "deep_research",
            "verdict": "deep_research", "tabId": 9999}}}))

    def test_wrong_page_url_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {
            "captureId": "3f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d", "taskKind": "deep_research",
            "verdict": "deep_research", "pageUrl": "https://chatgpt.com/c/other"}}}))

    def test_no_revision_growth_fails(self):
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drAfter": {
            "stateRevision": 20}}}))

    def test_no_capture_produced_fails(self):
        # The bounded poll times out when no capture carrying the marker exists;
        # that is a failure, never an optional skip.
        self.assert_check_failed(self.run_probe(fake_kwargs={"answers": {"drTurn": {}}}))

    def test_ambiguous_chatgpt_pages_fail(self):
        # Two chatgpt.com pages make the locked tab ambiguous.
        self.assert_check_failed(self.run_probe(fake_kwargs={"extra_chatgpt_pages": 1}))


class TestOutputDefaults(RunHarness):
    def test_omitting_out_creates_a_new_file_and_never_touches_history(self):
        history = probe_loader.HISTORICAL_RESULTS
        before = sha256(history)
        original_script_dir = PROBE.SCRIPT_DIR
        PROBE.SCRIPT_DIR = self.tmp
        try:
            code = self.run_probe(out=None)
        finally:
            PROBE.SCRIPT_DIR = original_script_dir
        self.assertEqual(code, PROBE.EXIT_OK)
        created = sorted(name for name in os.listdir(self.tmp)
                         if name.startswith("ff-probe-results-regression-"))
        self.assertEqual(len(created), 1, created)
        self.assertTrue(re.search(r"-\d{8}-\d{6}\.json$", created[0]))
        self.assertEqual(sha256(history), before,
                         "the historical ff-probe-results.json must be untouched")


if __name__ == "__main__":
    unittest.main(verbosity=2)
