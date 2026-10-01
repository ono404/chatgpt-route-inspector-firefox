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
