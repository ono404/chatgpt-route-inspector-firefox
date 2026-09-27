"""Real-Firefox verification probe over the raw Marionette protocol (stdlib only).

This script owns its browser: it creates a brand-new dedicated temporary
profile, launches Firefox on a port this process picked, connects, runs the
checks, shuts that instance down and (by default) removes the profile it made.
It never attaches to, and never stops, a browser it did not start.

Identity is verified *before* the browser is touched. A pass requires the full
packaged content to match an expectation that was produced by this build, not
by re-reading the package under test:

  * ``--expect-build-record release/<name>.build.json``
      expected XPI sha256 + per-file hashes + manifest sha256, written by
      ``scripts/package-firefox.mjs`` from the same ``dist/firefox`` tree.
  * ``--expect-xpi-sha256 <sha>``
      a bare expected whole-archive sha256, for callers that have no record.

The probe then cross-checks three things that must all agree: the packaged
archive, the ``--dist`` tree it was built from, and the build record. A
manifest hash is still recorded, but on its own it never passes identity.

Damaged input never produces a traceback: an unreadable XPI, a missing or
malformed packaged manifest, and a missing/invalid build record are all turned
into failed checks plus a written result file (exit code 2), because in each
case identity simply could not be established.

Once connected, the connection is treated as untrusted until the browser has
reported a ``moz:profile`` equal to the profile this run created. Until then no
Addon, storage, navigation or session command is sent at all, and the session
is deliberately left undeleted - it may belong to a browser this run does not
own.

Exit codes (all non-zero codes mean "do not trust this run"):
  0   every expected check ran and passed
  2   artifact identity rejected -> aborts before any browser interaction
  3   runtime/anomaly: launch, connect, protocol or cleanup failure
  4   one or more checks ran and failed, including a safety abort
  5   incomplete: a required check never ran after an ordinary failure
  6   refused to overwrite an existing --out file (previous evidence is safe)
  64  bad command line

Usage:
  ff-marionette.py --xpi <built.xpi> --expect-build-record <record.json>
                   [--expect-xpi-sha256 <sha>] [--dist <dir>]
                   [--announcement-ui ui/announcement/index.html]
                   [--out <results.json>] [--force] [--label <text>]
                   [--commit <sha>] [--firefox <firefox.exe>]
                   [--host 127.0.0.1] [--port <n>] [--startup-timeout 90]
                   [--keep-profile] [--keep-browser]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

# --- exit codes -------------------------------------------------------------
EXIT_OK = 0
EXIT_IDENTITY = 2
EXIT_FATAL = 3
EXIT_CHECKS_FAILED = 4
EXIT_INCOMPLETE = 5
EXIT_OUTPUT_EXISTS = 6
EXIT_USAGE = 64

EXT_ID = "chatgpt-route-inspector-firefox@local"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FIREFOX = r"C:\Program Files\Mozilla Firefox\firefox.exe"

# Checks every complete run must produce. A run that does not produce them is
# reported as incomplete (exit 5) instead of silently passing.
REQUIRED_CHECKS = [
    "0a.xpi-sha256",
    "0b.xpi-contents",
    "0d.manifest-sha256",
    "0.session",
    "0e.session-profile",
    "1.install-no-manifest-error",
    "1b.addon-uuid",
    "2.ext-namespaces",
    "3.ext-chrome.storage-promise",
    "4.ext-get-state-roundtrip",
    "5.ext-tabs-i18n-getURL",
    "6.popup-renders",
    "7.synthetic-observation-pipeline",
    "8.dashboard-shows-turn",
    "9.page-hook-MAIN-world",
    "10.bridge-overlay-ISOLATED",
    "11.overlay-suspect-hint",
    "12.capture-context-registered",
    "13.auto-reasoning-verdict",
    "14.announcement-page",
    "15.open-announcement-target",
    "16.suspected-downgrade-verdict",
    "17.work-unverifiable-verdict",
    "18.failed-phase-not-completed",
    "19.new-chat-navigation-association",
]
# Only demanded when a build record was supplied.
REQUIRED_WITH_RECORD = ["0c.dist-matches-record", "0f.build-record"]


# --- small helpers ----------------------------------------------------------
def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def walk_files(base):
    """Relative posix-style paths of every file under `base`, sorted."""
    found = []
    for root, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(root, name)
            found.append(os.path.relpath(full, base).replace(os.sep, "/"))
    return sorted(found)


def hash_tree(base):
    return {rel: sha256_file(os.path.join(base, rel)) for rel in walk_files(base)}


def zip_entries(path):
    """{relative path: sha256 of its bytes} for every file in the archive."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        return {n: sha256_bytes(archive.read(n)) for n in sorted(names)}


def read_xpi_manifest(path):
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("manifest.json")
    except KeyError:
        raise ValueError("the archive has no manifest.json at its root")
    return sha256_bytes(raw), json.loads(raw.decode("utf-8"))


def default_out_path(script_dir, label, stamp=None):
    """A fresh, non-colliding results path. Never the historical default file."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", label or "probe").strip("-") or "probe"
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(script_dir, "ff-probe-results-%s-%s.json" % (slug, stamp))
    candidate, index = base, 1
    while os.path.exists(candidate):
        index += 1
        candidate = "%s-%d.json" % (base[:-5], index)
    return candidate


def decide_exit_code(identity_ok, fatal, failed_checks, missing_checks, aborted=None):
    """Pure aggregation: only a complete, fully green run may exit 0.

    `aborted` carries a reason string when the run deliberately stopped early
    for safety (e.g. the connected browser was not the instance this run
    launched). That is a failed precondition, so it is reported as "checks
    failed" even though the remaining checks were never attempted.
    """
    if not identity_ok:
        return EXIT_IDENTITY
    if fatal is not None:
        return EXIT_FATAL
    if aborted:
        return EXIT_CHECKS_FAILED
    if missing_checks:
        return EXIT_INCOMPLETE
    if failed_checks:
        return EXIT_CHECKS_FAILED
    return EXIT_OK


def exit_reason(code, identity_ok, fatal, failed_checks, missing_checks, aborted=None):
    if code == EXIT_OK:
        return "all expected checks ran and passed"
    if code == EXIT_IDENTITY:
        return "artifact identity rejected before browser interaction"
    if code == EXIT_FATAL:
        return "runtime anomaly: %s" % (fatal,)
    if code == EXIT_CHECKS_FAILED and aborted:
        return "aborted for safety (%s); failed checks: %s" % (
            aborted, ", ".join(failed_checks) or "none recorded")
    if code == EXIT_INCOMPLETE:
        return "required checks did not run: %s" % ", ".join(missing_checks)
    if code == EXIT_CHECKS_FAILED:
        return "checks failed: %s" % ", ".join(failed_checks)
    return "unknown"


# --- artifact identity ------------------------------------------------------
def verify_identity(xpi_path, dist_dir, expected_xpi_sha256, record, record_path):
    """Return (checks, meta). Runs entirely offline, before any browser work.

    Never raises: a package that cannot be read produces failed checks and a
    `parseError` in meta, so the caller can still write a usable result file.
    Fields that could not be read stay None instead of being guessed.
    """
    checks = []
    meta = {
        "xpi": xpi_path,
        "distDir": dist_dir,
        "buildRecordPath": record_path,
        "expectedXpiSha256": expected_xpi_sha256,
        "xpiSha256": None,
        "manifestSha256": None,
        "manifestVersion": None,
        "geckoId": None,
        "strictMinVersion": None,
        "packagedFiles": None,
        "distFileCount": None,
        "parseError": None,
    }

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:600]})
        print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:280]) if detail else ""), flush=True)

    if not os.path.isfile(xpi_path):
        add("0a.xpi-sha256", False, "XPI not found: %s" % xpi_path)
        add("0b.xpi-contents", False, "XPI not found")
        add("0d.manifest-sha256", False, "XPI not found")
        meta["parseError"] = "XPI not found: %s" % xpi_path
        return checks, meta

    try:
        meta["xpiSha256"] = sha256_file(xpi_path)
    except Exception as error:
        meta["parseError"] = "XPI could not be hashed (%s: %s)" % (type(error).__name__, error)

    manifest = None
    entries = None
    try:
        manifest_sha, manifest = read_xpi_manifest(xpi_path)
        meta["manifestSha256"] = manifest_sha
        meta["manifestVersion"] = manifest.get("version")
        gecko = (manifest.get("browser_specific_settings") or {}).get("gecko") or {}
        meta["geckoId"] = gecko.get("id")
        meta["strictMinVersion"] = gecko.get("strict_min_version")
        entries = zip_entries(xpi_path)
        meta["packagedFiles"] = len(entries)
    except Exception as error:
        reason = "package could not be parsed (%s: %s)" % (type(error).__name__, error)
        meta["parseError"] = reason
        add("0b.xpi-contents", False, reason)
        if record is not None:
            add("0c.dist-matches-record", False, reason)
        add("0d.manifest-sha256", False, reason)

    # 0a: the whole archive must equal the expectation this build produced.
    #     This only needs the file bytes, so it is evaluated even when the
    #     archive cannot be parsed as a zip.
    if meta["xpiSha256"] is None:
        pass  # already reported as a parse error
    elif not expected_xpi_sha256:
        add("0a.xpi-sha256", False,
            "no expected XPI sha256 supplied (pass --expect-build-record or --expect-xpi-sha256)")
    else:
        add("0a.xpi-sha256", meta["xpiSha256"] == expected_xpi_sha256,
            "actual=%s expected=%s" % (meta["xpiSha256"], expected_xpi_sha256))

    if entries is None:
        return checks, meta

    # 0b: package contents must equal the --dist tree, both paths and bytes.
    if not os.path.isdir(dist_dir):
        add("0b.xpi-contents", False, "dist dir not found: %s" % dist_dir)
    else:
        dist_hashes = hash_tree(dist_dir)
        meta["distFileCount"] = len(dist_hashes)
        problems = []
        for name in sorted(set(dist_hashes) - set(entries)):
            problems.append("missing from XPI: %s" % name)
        for name in sorted(set(entries) - set(dist_hashes)):
            problems.append("not in dist: %s" % name)
        for name in sorted(set(entries) & set(dist_hashes)):
            if entries[name] != dist_hashes[name]:
                problems.append("content differs: %s" % name)
        add("0b.xpi-contents", not problems,
            ("%d files identical to XPI" % len(dist_hashes)) if not problems else "; ".join(problems[:10]))

    # 0c: the record must describe this very dist tree (chain: dist -> record -> XPI).
    if record is None:
        pass
    else:
        recorded = record.get("fileHashes") or {}
        dist_hashes = hash_tree(dist_dir) if os.path.isdir(dist_dir) else {}
        problems = []
        if record.get("xpiPath") and os.path.abspath(record["xpiPath"]) != os.path.abspath(xpi_path):
            problems.append("record xpiPath=%s but probing %s" % (record["xpiPath"], xpi_path))
        if record.get("distDir") and os.path.abspath(record["distDir"]) != os.path.abspath(dist_dir):
            problems.append("record distDir=%s but checking %s" % (record["distDir"], dist_dir))
        for name in sorted(set(recorded) - set(dist_hashes)):
            problems.append("recorded file absent from dist: %s" % name)
        for name in sorted(set(dist_hashes) - set(recorded)):
            problems.append("dist file not in record: %s" % name)
        for name in sorted(set(dist_hashes) & set(recorded)):
            if dist_hashes[name] != recorded[name]:
                problems.append("dist content differs from record: %s" % name)
        for name in sorted(set(recorded) - set(entries)):
            problems.append("recorded file absent from XPI: %s" % name)
        for name in sorted(set(entries) & set(recorded)):
            if entries[name] != recorded[name]:
                problems.append("XPI content differs from record: %s" % name)
        add("0c.dist-matches-record", not problems,
            ("%d recorded files agree" % len(recorded)) if not problems else "; ".join(problems[:10]))

    # 0d: the manifest hash is recorded, and must agree with the record if any.
    #     It is never accepted as identity on its own.
    if record is not None and record.get("manifestSha256"):
        add("0d.manifest-sha256", meta["manifestSha256"] == record["manifestSha256"],
            "sha256=%s version=%s gecko=%s min=%s (record=%s)" % (
                meta["manifestSha256"], meta["manifestVersion"], meta["geckoId"],
                meta["strictMinVersion"], record["manifestSha256"]))
    else:
        add("0d.manifest-sha256", True,
            "sha256=%s version=%s gecko=%s min=%s (recorded only; not an identity condition)" % (
                meta["manifestSha256"], meta["manifestVersion"], meta["geckoId"],
                meta["strictMinVersion"]))
    return checks, meta


# --- browser lifecycle ------------------------------------------------------
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_profile(root):
    """Brand-new, empty, dedicated profile directory owned by this run."""
    path = tempfile.mkdtemp(prefix="ff-ri-probe-", dir=root)
    with open(os.path.join(path, "user.js"), "w", encoding="utf-8") as handle:
        handle.write('user_pref("browser.shell.checkDefaultBrowser", false);\n')
        handle.write('user_pref("browser.startup.page", 0);\n')
        handle.write('user_pref("datareporting.policy.dataSubmissionEnabled", false);\n')
        handle.write('user_pref("app.update.auto", false);\n')
        handle.write('user_pref("app.update.enabled", false);\n')
        handle.write('user_pref("toolkit.telemetry.enabled", false);\n')
    return path


def launch_firefox(firefox_exe, profile_dir, port):
    if not os.path.isfile(firefox_exe):
        raise RuntimeError("Firefox executable not found: %s" % firefox_exe)
    with open(os.path.join(profile_dir, "user.js"), "a", encoding="utf-8") as handle:
        handle.write('user_pref("marionette.port", %d);\n' % port)
        handle.write('user_pref("marionette.enabled", true);\n')
    argv = [
        firefox_exe,
        "-headless",
        "-no-remote",
        "-marionette",
        "-remote-allow-system-access",
        "-profile", profile_dir,
        "about:blank",
    ]
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        cwd=os.path.dirname(firefox_exe),
    )
    return proc, argv


def wait_for_port(host, port, timeout, proc):
    """Wait for this instance's Marionette listener; fail if it died first."""
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        code = proc.poll()
        if code is not None:
            raise RuntimeError("Firefox exited during startup with code %s" % code)
        # Never let a single connect attempt overshoot the configured budget.
        remaining = max(0.2, deadline - time.time())
        try:
            probe = socket.create_connection((host, port), timeout=min(2.0, remaining))
            probe.close()
            return
        except OSError as error:
            last_error = error
        time.sleep(min(0.5, max(0.0, deadline - time.time())))
    raise TimeoutError(
        "Marionette port %s:%d not reachable within %ss (last error: %s)"
        % (host, port, timeout, last_error))


def stop_firefox(proc):
    """Stop only the process object this run created."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=30)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=15)
        except Exception:
            pass


def remove_profile(profile_dir):
    """Delete only a directory this run created inside the system temp dir.

    Returns True when the directory is verifiably gone. Removal is best-effort:
    a browser killed mid-initialisation can recreate files after the first
    attempt, so the caller records the real outcome instead of assuming it.
    """
    if not profile_dir:
        return True
    temp_root = os.path.realpath(tempfile.gettempdir())
    target = os.path.realpath(profile_dir)
    if not target.startswith(temp_root + os.sep):
        return False
    for _attempt in range(3):
        shutil.rmtree(target, ignore_errors=True)
        if not os.path.exists(target):
            return True
        time.sleep(0.5)
    return not os.path.exists(target)


class Marionette:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=30)
        self.s.settimeout(120)
        self.buf = b""
        self.msgid = 0
        self._read_msg()

    def _read_msg(self):
        while b":" not in self.buf:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("eof")
            self.buf += chunk
        ln, rest = self.buf.split(b":", 1)
        n = int(ln)
        while len(rest) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("eof")
            rest += chunk
        self.buf = rest[n:]
        return json.loads(rest[:n].decode())

    def cmd(self, method, params=None):
        self.msgid += 1
        mid = self.msgid
        payload = json.dumps([0, mid, method, params or {}]).encode()
        self.s.sendall(str(len(payload)).encode() + b":" + payload)
        while True:
            msg = self._read_msg()
            if isinstance(msg, list) and len(msg) == 4 and msg[0] == 1 and msg[1] == mid:
                if msg[2]:
                    raise RuntimeError("%s -> %s" % (method, msg[2]))
                return msg[3]
            # ignore async events / mismatched messages

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# --- the checks themselves --------------------------------------------------
def run_browser_checks(m, meta, args, results):
    """Run every browser-side check.

    Individual checks record their own failures and never abort the run - with
    one exception: the connected browser must be the instance this run created.
    Until that is verified nothing else is sent, because every remaining check
    would act on a browser of unknown provenance.

    Returns {"trusted": bool, "aborted": reason_or_None}. `aborted` is set when
    the run stops early for safety rather than because checks merely failed.
    """
    EXT = None
    shell = None

    def add(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": str(detail)[:600]})
        print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:280]) if detail else ""), flush=True)

    def exe(script, script_args=None):
        return m.cmd("WebDriver:ExecuteScript", {"script": script, "args": script_args or []})["value"]

    def handles():
        value = m.cmd("WebDriver:GetWindowHandles")
        return value["value"] if isinstance(value, dict) else value

    def find_handle(fragment):
        for handle in handles():
            try:
                m.cmd("WebDriver:SwitchToWindow", {"handle": handle})
                if fragment in (m.cmd("WebDriver:GetCurrentURL")["value"] or ""):
                    return handle
            except Exception:
                continue
        return None

    def shexe(script, script_args=None):
        m.cmd("WebDriver:SwitchToWindow", {"handle": shell})
        return exe(script, script_args)

    def open_extension_page(url):
        shexe("return (async (u) => { const t = await chrome.tabs.create({url: u}); return t.id; })(arguments[0])", [url])
        time.sleep(2)
        return find_handle(url.split(EXT + "/", 1)[-1])

    # --- session ---
    session = meta.get("session") or {}
    caps = session.get("capabilities") or {}
    add("0.session", bool(session.get("sessionId")), session.get("sessionId"))

    # --- the connected browser must be the instance this run launched ---
    # This is a precondition, not a report line: while it is unresolved the
    # connection is untrusted, so no Addon / storage / navigation / session
    # command may be sent. Only the socket is closed afterwards.
    profile_trusted = False
    try:
        reported = caps.get("moz:profile") or ""
        launched = meta["launch"]["profileDir"]
        same = bool(reported) and os.path.normcase(os.path.realpath(reported)) == os.path.normcase(os.path.realpath(launched))
        temp_root = os.path.realpath(tempfile.gettempdir())
        inside_temp = os.path.realpath(launched).startswith(temp_root + os.sep)
        profile_trusted = same and inside_temp
        add("0e.session-profile", profile_trusted,
            "browser says moz:profile=%s pid=%s launched=%s inside_temp=%s" % (
                reported, meta["launch"]["pid"], launched, inside_temp))
    except Exception as error:
        add("0e.session-profile", False, "profile check raised (%s: %s)" % (type(error).__name__, error))

    if not profile_trusted:
        detail = ("connection identity not verified; no Addon, storage, navigation or "
                  "session command was sent, and the session was left untouched")
        add("0f.untrusted-connection", False, detail)
        meta["connectionTrusted"] = False
        return {"trusted": False,
                "aborted": "connected browser is not the profile this run created"}

    # Only now may the connection be used.
    try:
        meta["firefoxVersion"] = exe("return navigator.userAgent")
    except Exception as error:
        meta["firefoxVersion"] = "unavailable: %s" % (error,)

    # --- install ---
    installed = False
    try:
        try:
            m.cmd("Addon:Uninstall", {"id": EXT_ID})
        except Exception:
            pass
        time.sleep(1)
        r = m.cmd("Addon:Install", {"path": args.xpi, "temporary": True})
        installed = True
        add("1.install-no-manifest-error", True, r.get("value", r))
    except Exception as error:
        add("1.install-no-manifest-error", False, error)

    uuid = None
    if installed:
        try:
            time.sleep(3)
            handles_all = handles()
            url = None
            for handle in handles_all:
                try:
                    m.cmd("WebDriver:SwitchToWindow", {"handle": handle})
                    url = m.cmd("WebDriver:GetCurrentURL")["value"]
                except Exception:
                    continue
                found = re.search(r"moz-extension://([0-9a-f-]{36})(/ui/onboarding/index\.html)?", url or "")
                if found:
                    uuid = found.group(1)
                    break
            add("1b.addon-uuid", bool(uuid), "handles=%d uuid=%s last_url=%s" % (len(handles_all), uuid, (url or "")[:120]))
        except Exception as error:
            add("1b.addon-uuid", False, error)
    if not uuid:
        add("1b.addon-registered", False, "uuid not found; browser checks aborted")
        meta["connectionTrusted"] = True
        return {"trusted": True, "aborted": None}
    EXT = "moz-extension://" + uuid
    shell = handle

    # --- extension-context probes (same principal/binding as background page) ---
    try:
        v = shexe("return {c: typeof chrome, b: typeof browser, url: location.href}")
        add("2.ext-namespaces",
            isinstance(v, dict) and v.get("c") == "object" and str(v.get("url", "")).startswith("moz-extension://"), v)
    except Exception as error:
        add("2.ext-namespaces", False, error)
    try:
        v = shexe("return (async () => { await chrome.storage.local.set({ffprobe: 42}); const g = await chrome.storage.local.get('ffprobe'); return g.ffprobe; })()")
        add("3.ext-chrome.storage-promise", v == 42, v)
    except Exception as error:
        add("3.ext-chrome.storage-promise", False, error)
    try:
        v = shexe("return (async () => { const r = await chrome.runtime.sendMessage({type:'route:get-state'}); return {ok: r.ok, hasState: !!r.state, schemaVersion: ((r.state.turns||[])[0]||{}).schemaVersion || null}; })()")
        add("4.ext-get-state-roundtrip", v.get("ok") and v.get("hasState"), v)
    except Exception as error:
        add("4.ext-get-state-roundtrip", False, error)
    try:
        v = shexe("return (async () => ({tabs: (await chrome.tabs.query({})).length, lang: chrome.i18n.getUILanguage(), url: chrome.runtime.getURL('ui/popup/index.html'), version: chrome.runtime.getManifest().version}))()")
        add("5.ext-tabs-i18n-getURL",
            isinstance(v, dict) and str(v.get("url")).startswith("moz-extension://")
            and v.get("version") == meta["identity"]["manifestVersion"], v)
    except Exception as error:
        add("5.ext-tabs-i18n-getURL", False, error)

    # --- open popup via extension tabs API, read its DOM ---
    try:
        popup = open_extension_page(EXT + "/ui/popup/index.html")
        t = exe("return document.body ? document.body.textContent.slice(0, 200) : null") if popup else None
        add("6.popup-renders", bool(t and len(t.strip()) > 10), t)
    except Exception as error:
        add("6.popup-renders", False, error)
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        obs = {"captureId": "ff-probe-1", "source": "page_fetch", "captureMode": "live",
               "phase": "completed", "observedAt": now, "startedAt": now, "completedAt": now,
               "pageUrl": "https://chatgpt.com/c/ffprobe", "requestedModel": "gpt-5-6-pro",
               "resolvedModelSlug": "gpt-5-5-mini"}
        v = shexe("return (async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o}); const t0 = (r.state.turns||[])[0]||{}; return {ok:r.ok, turns:(r.state.turns||[]).length, verdict:t0.verdict, route:t0.routeModel, req:t0.requestedModel, schemaVersion:t0.schemaVersion}; })(arguments[0])", [obs])
        add("7.synthetic-observation-pipeline",
            v.get("ok") and v.get("turns") == 1 and v.get("req") == "gpt-5-6-pro"
            and v.get("schemaVersion") == "1.8.0", v)
    except Exception as error:
        add("7.synthetic-observation-pipeline", False, error)
    try:
        # Popup filters turns by active tab id (by design, same as Chromium), so a
        # synthetic observation owned by another tab won't show there. Dashboard
        # lists all turns -> the right surface to assert UI display.
        dash = open_extension_page(EXT + "/ui/dashboard/index.html")
        if dash:
            m.cmd("WebDriver:SwitchToWindow", {"handle": dash})
            time.sleep(1)
            t = exe("return document.body.textContent") or ""
            add("8.dashboard-shows-turn", ("GPT 5.6 Pro" in t) and ("GPT 5.5 mini" in t or "gpt-5-5-mini" in t), t[:300])
        else:
            add("8.dashboard-shows-turn", False, "no dashboard handle")
    except Exception as error:
        add("8.dashboard-shows-turn", False, error)

    try:
        w = m.cmd("WebDriver:NewWindow", {"type": "tab"})
        w = w.get("value", w) if isinstance(w, dict) else w
        w = w["handle"]
        m.cmd("WebDriver:SwitchToWindow", {"handle": w})
        m.cmd("WebDriver:Navigate", {"url": "https://chatgpt.com/"})
        time.sleep(8)
        v = exe("return {fetchName: (window.fetch && window.fetch.name) || null, overlay: !!document.getElementById('chatgpt-route-inspector-root'), url: location.href}")
        add("9.page-hook-MAIN-world", v.get("fetchName") == "routeInspectorFetch", v)
        add("10.bridge-overlay-ISOLATED", v.get("overlay") is True, v)
        # v1.0.9: the 1.0.7 upgrade-notice overlay entry was removed upstream.
        # A completed live response without resolved_model_slug must surface the
        # "suspected downgrade" hint in the overlay, linking the fixed notice URL.
        # Synthetic observation injected via window.postMessage: this verifies
        # bridge -> background -> overlay rendering only; it does NOT exercise
        # page-hook capture parsing (the real navigation chain is covered by
        # check 19).
        try:
            tab_ctx = shexe("return (async () => { const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'});"
                            " if (!tabs.length) return {error: 'no chatgpt tab'};"
                            " const tabId = tabs[0].id;"
                            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
                            " const ctx = st && st.captureContexts ? st.captureContexts[tabId] : null;"
                            " if (!ctx) return {error: 'no capture context for tab', tabId: tabId};"
                            " return {tabId: tabId, ctx: ctx.id}; })()")
            if not (isinstance(tab_ctx, dict) and tab_ctx.get("ctx")):
                raise RuntimeError("context lookup failed: %r" % (tab_ctx,))
            now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            obs = {"captureId": "ff-probe-suspect-live", "captureContextId": tab_ctx["ctx"],
                   "source": "page_fetch", "captureMode": "live", "phase": "completed",
                   "observedAt": now, "startedAt": now, "completedAt": now,
                   "pageUrl": "https://chatgpt.com/", "requestedModel": "gpt-5-6-pro",
                   "serverModelSlug": "gpt-5-6-pro"}
            if not find_handle("https://chatgpt.com"):
                raise RuntimeError("chatgpt.com tab handle not found")
            posted = exe("return (() => { window.postMessage({source: 'chatgpt-route-inspector', version: 1,"
                         " observation: arguments[0]}, location.origin); return {posted: true}; })()", [obs])
            if not (isinstance(posted, dict) and posted.get("posted")):
                raise RuntimeError("postMessage dispatch failed: %r" % (posted,))
            sent = shexe("return (async (o, tabId) => { const r = await chrome.runtime.sendMessage({type:'route:get-state'});"
                         " const t = (r.state.turns||[]).find(x => x.captureId === 'ff-probe-suspect-live') || {};"
                         " return {ok: r.ok, verdict: t.verdict, tabId: tabId,"
                         " turnTabId: t.tabId === undefined ? null : t.tabId,"
                         " turnCtx: t.captureContextId || null}; })(arguments[0], arguments[1])",
                        [obs, tab_ctx["tabId"]])
            if not (isinstance(sent, dict) and sent.get("ok") and sent.get("verdict") == "suspected_downgrade"
                    and sent.get("turnTabId") == tab_ctx.get("tabId") and sent.get("turnCtx") == tab_ctx.get("ctx")):
                add("11.overlay-suspect-hint", False, {"stage": "observation", "sent": sent, "tabCtx": tab_ctx})
            else:
                if not find_handle("https://chatgpt.com"):
                    raise RuntimeError("chatgpt.com tab handle not found")
                hint = None
                for _ in range(20):
                    time.sleep(0.5)
                    hint = exe("return (() => { const root = document.getElementById('chatgpt-route-inspector-root');"
                               " if (!root || !root.shadowRoot) return {root: !!root}; const sr = root.shadowRoot;"
                               " const link = sr.getElementById('suspect-link');"
                               " return {root: true, suspect: !!sr.getElementById('suspect-trigger'),"
                               " legacy: !!sr.getElementById('notice-star'),"
                               " href: link ? link.getAttribute('href') : null}; })()")
                    if isinstance(hint, dict) and hint.get("suspect"):
                        break
                add("11.overlay-suspect-hint",
                    isinstance(hint, dict) and hint.get("suspect") is True and hint.get("legacy") is False
                    and str(hint.get("href", "")).startswith("https://rinotice.liu-qi.cn/"),
                    {"hint": hint, "sent": sent})
        except Exception as error:
            add("11.overlay-suspect-hint", False, error)
    except Exception as error:
        add("9.page-hook-MAIN-world", False, error)
        add("10.bridge-overlay-ISOLATED", False, error)

    # v1.0.7: MAIN/bridge handshake must register a capture context for the page tab.
    try:
        time.sleep(2)
        v = shexe("return (async () => { const r = await chrome.runtime.sendMessage({type:'route:get-state'}); const contexts = r.state.captureContexts || {}; const ids = Object.keys(contexts); return {ok: r.ok, count: ids.length, sample: ids.length ? contexts[ids[0]] : null}; })()")
        add("12.capture-context-registered", v.get("ok") and v.get("count", 0) >= 1, v)
    except Exception as error:
        add("12.capture-context-registered", False, error)

    # v1.0.7: synthetic auto-thinking route must be classified as auto_reasoning.
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        obs = {"captureId": "ff-probe-auto", "source": "page_fetch", "captureMode": "live",
               "phase": "completed", "observedAt": now, "startedAt": now, "completedAt": now,
               "pageUrl": "https://chatgpt.com/c/ffprobe", "requestedModel": "gpt-5-6",
               "resolvedModelSlug": "gpt-5-6-auto-thinking", "serverModelSlug": "gpt-5-6-auto-thinking"}
        v = shexe("return (async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o}); const t = (r.state.turns||[]).find(x => x.captureId === 'ff-probe-auto') || {}; return {ok:r.ok, verdict:t.verdict, route:t.routeModel, schemaVersion:t.schemaVersion}; })(arguments[0])", [obs])
        add("13.auto-reasoning-verdict", v.get("ok") and v.get("verdict") == "auto_reasoning" and v.get("route") == "gpt-5-6-auto-thinking", v)
    except Exception as error:
        add("13.auto-reasoning-verdict", False, error)

    # v1.0.9: the packaged announcement page must still ship and render its body.
    try:
        page = open_extension_page("%s/%s" % (EXT, args.announcement_ui))
        if page:
            m.cmd("WebDriver:SwitchToWindow", {"handle": page})
            time.sleep(1)
            v = exe("return {title: document.title, text: document.body ? document.body.textContent.slice(0, 400) : null, script: !!document.querySelector('script[src=\"index.js\"]'), href: document.getElementById('notice-poll') ? document.getElementById('notice-poll').getAttribute('href') : null}")
            text = v.get("text") or ""
            add("14.announcement-page",
                ("1.0.9" in text) and v.get("script") is True and str(v.get("href", "")).startswith("https://x.com/"), v)
        else:
            add("14.announcement-page", False, "no announcement handle")
    except Exception as error:
        add("14.announcement-page", False, error)

    # v1.0.9: opening the announcement goes to the fixed public HTTPS notice site
    # (UPGRADE_NOTICE_URL) in a new tab; route history must not change. The tab's
    # real URL is verified browser-side via WebDriver (the extension has no tabs
    # permission, so chrome.tabs.query hides third-party URLs). Real navigation;
    # only the browser's ordinary request is recorded, no inspection data attached.
    try:
        v = shexe("return (async () => { const beforeIds = (await chrome.tabs.query({})).map(t => t.id);"
                  " const before = ((await chrome.runtime.sendMessage({type:'route:get-state'})).state.turns||[]).length;"
                  " const r = await chrome.runtime.sendMessage({type:'route:open-announcement'});"
                  " let newId = null; for (let i = 0; i < 20 && newId === null; i++) {"
                  "  await new Promise(res => setTimeout(res, 500));"
                  "  const tabs = await chrome.tabs.query({});"
                  "  const fresh = tabs.filter(t => !beforeIds.includes(t.id));"
                  "  if (fresh.length) newId = fresh[fresh.length - 1].id; }"
                  " return {ok: r.ok, newId: newId, before: before}; })()")
        if not (isinstance(v, dict) and v.get("ok") and isinstance(v.get("newId"), int)):
            add("15.open-announcement-target", False, {"stage": "open", "result": v})
        else:
            # The tab is listed in chrome.tabs immediately, but the Marionette
            # handle list can lag; retry instead of failing on enumeration jitter.
            notice_handle = None
            for _ in range(30):
                notice_handle = find_handle("rinotice.liu-qi.cn")
                if notice_handle is not None:
                    break
                time.sleep(0.5)
            real_url = str(m.cmd("WebDriver:GetCurrentURL")["value"]) if notice_handle else None
            if notice_handle is None or not real_url.startswith("https://rinotice.liu-qi.cn"):
                add("15.open-announcement-target", False, {"stage": "verify", "result": v, "realUrl": real_url})
            else:
                time.sleep(2)
                page = exe("return {finalUrl: location.href, title: document.title,"
                           " text: document.body ? document.body.textContent.trim().slice(0, 120) : null}")
                # Close the notice tab browser-side; chrome.tabs.remove rejects
                # ids from a context without the tabs permission in Firefox.
                m.cmd("WebDriver:CloseWindow")
                cleanup = shexe("return (async () => { const after = ((await chrome.runtime.sendMessage("
                                "{type:'route:get-state'})).state.turns||[]).length; return {after: after}; })()")
                add("15.open-announcement-target",
                    isinstance(page, dict) and bool(page.get("finalUrl"))
                    and isinstance(cleanup, dict) and cleanup.get("after") == v.get("before"),
                    {"openedTab": {"id": v["newId"], "url": real_url}, "page": page,
                     "history": {"before": v.get("before"), "after": (cleanup or {}).get("after")}})
    except Exception as error:
        add("15.open-announcement-target", False, error)

    # v1.0.9: suspected_downgrade conditions must mirror upstream
    # (tests/unit/turns.test.ts): only a completed live/reload network response
    # without resolved_model_slug; responding/failed/resolved-present stay normal.
    # Synthetic observations in the extension context, no browser navigation.
    try:
        v = shexe("return (async () => { const mk = (over) => { const now = new Date().toISOString();"
                  " return Object.assign({captureId: 'ff-probe-sus', source: 'page_fetch', captureMode: 'live',"
                  " observedAt: now, startedAt: now, completedAt: now, pageUrl: 'https://chatgpt.com/c/ffprobe',"
                  " requestedModel: 'gpt-5-6-pro', serverModelSlug: 'gpt-5-6-pro'}, over,"
                  " {captureId: 'ff-probe-sus-' + over.phase + (over.resolvedModelSlug ? '-res' : '')}); };"
                  " const rd = async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o});"
                  " const t = (r.state.turns||[]).find(x => x.captureId === o.captureId) || {}; return t.verdict; };"
                  " return {completed: await rd(mk({phase: 'completed'})),"
                  " responding: await rd(mk({phase: 'responding'})),"
                  " failed: await rd(mk({phase: 'failed', completedAt: null})),"
                  " resolved: await rd(mk({phase: 'completed', resolvedModelSlug: 'gpt-5-6-pro'}))}; })()")
        add("16.suspected-downgrade-verdict",
            isinstance(v, dict) and v.get("completed") == "suspected_downgrade"
            and v.get("responding") == "normal" and v.get("failed") == "normal"
            and v.get("resolved") == "normal", v)
    except Exception as error:
        add("16.suspected-downgrade-verdict", False, error)

    # v1.0.9: a completed -wm Work response is work_unverifiable; a responding
    # one is not (mirrors tests/unit/turns.test.ts). Synthetic, extension context.
    try:
        v = shexe("return (async () => { const mk = (phase) => { const now = new Date().toISOString();"
                  " return {captureId: 'ff-probe-wm-' + phase, source: 'page_fetch', captureMode: 'live',"
                  " phase: phase, observedAt: now, startedAt: now, completedAt: phase === 'completed' ? now : null,"
                  " pageUrl: 'https://chatgpt.com/c/ffprobe', requestedModel: 'gpt-6-astra-wm',"
                  " serverModelSlug: 'gpt-6-astra-wm'}; };"
                  " const rd = async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o});"
                  " const t = (r.state.turns||[]).find(x => x.captureId === o.captureId) || {}; return t.verdict; };"
                  " return {completed: await rd(mk('completed')), responding: await rd(mk('responding'))}; })()")
        add("17.work-unverifiable-verdict",
            isinstance(v, dict) and v.get("completed") == "work_unverifiable"
            and v.get("responding") == "normal", v)
    except Exception as error:
        add("17.work-unverifiable-verdict", False, error)

    # v1.0.9: a failed record must keep phase=failed with its error code; it may
    # not be reported as completed or borrow the downgrade suspicion.
    try:
        v = shexe("return (async () => { const now = new Date().toISOString();"
                  " const r = await chrome.runtime.sendMessage({type:'route:observation', observation:"
                  " {captureId: 'ff-probe-failed', source: 'page_fetch', captureMode: 'live', phase: 'failed',"
                  " errorCode: 'stream_parse_failed', observedAt: now, startedAt: now, completedAt: null,"
                  " pageUrl: 'https://chatgpt.com/c/ffprobe', requestedModel: 'gpt-5-6-pro'}});"
                  " const t = (r.state.turns||[]).find(x => x.captureId === 'ff-probe-failed') || {};"
                  " return {phase: t.phase, errorCode: t.errorCode, completedAt: t.completedAt, verdict: t.verdict}; })()")
        add("18.failed-phase-not-completed",
            isinstance(v, dict) and v.get("phase") == "failed"
            and v.get("errorCode") == "stream_parse_failed" and v.get("completedAt") is None
            and v.get("verdict") != "suspected_downgrade" and v.get("verdict") != "work_unverifiable", v)
    except Exception as error:
        add("18.failed-phase-not-completed", False, error)

    # v1.0.9 (revised 2026-09-27 review-fix): the new-chat navigation fix is
    # verified through the code under test only. The real page-hook from the
    # XPI under test parses the controlled creation request and generates the
    # capture id itself; its wrapped history.pushState drives the tracker
    # navigation. page-hook only inspects same-origin requests
    # (isAllowedRequest), so a controlled SSE response from another origin can
    # never enter the inspection path; the responses here are chatgpt.com's
    # real unauthenticated rejections, and the "server identity" is correlated
    # through the request body the way the request parser reads it. Synthetic
    # traffic through real capture code - not real account traffic. Nothing
    # prefills captureId/captureContextId, and no route:observation or
    # synthetic postMessage envelope is sent in this check.
    try:
        marker_model = "gpt-5-6-pro-navcheck"
        temp_path = "/c/local-chatgpt%3Anavcheck-draft"
        formal_path = "/c/navcheck-conv"
        unrelated_path = "/c/navcheck-unrelated"

        def nav_poll(script, args=None, want=None, tries=24):
            value = None
            for _ in range(tries):
                value = shexe(script, args or [])
                if want is not None and want(value):
                    return value
                time.sleep(0.5)
            return value

        # 1) locate the chatgpt.com tab and its current capture context
        tab_ctx = nav_poll(
            "return (async () => { /* navcheck-a-ctx */"
            " const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'});"
            " if (!tabs.length) return {error: 'no chatgpt tab'};"
            " const tabId = tabs[0].id;"
            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
            " const ctx = st && st.captureContexts ? st.captureContexts[tabId] : null;"
            " if (!ctx) return {error: 'no capture context for tab', tabId: tabId};"
            " return {tabId: tabId, ctx: ctx.id}; })()",
            want=lambda v: isinstance(v, dict) and v.get("ctx"))
        if not isinstance(tab_ctx, dict) or not tab_ctx.get("ctx"):
            raise RuntimeError("tab/context lookup failed: %r" % (tab_ctx,))
        creation_ctx = tab_ctx["ctx"]

        def go_page():
            if not find_handle("https://chatgpt.com"):
                raise RuntimeError("chatgpt.com tab handle not found")

        def start_request(conversation_id, marker):
            go_page()
            # "" means a brand-new chat (body conversation_id null); Marionette
            # turns Python None into undefined, so "" is the sentinel here.
            # Fire-and-forget: the creation request must still be in flight
            # while the page navigates, like the real new-chat flow.
            return exe("return (function (conversationId) { /* " + marker + " */"
                       " const cid = conversationId === '' ? null : conversationId;"
                       " const detail = {fetchName: (window.fetch && window.fetch.name) || null,"
                       "  location: location.href};"
                       " try { window.fetch('/backend-api/f/conversation',"
                       "  {method: 'POST', body: JSON.stringify({model: '" + marker_model + "',"
                       "   conversation_id: cid, messages: [{id: 'navcheck-input'}]}) })"
                       "  .catch(function () {}); } catch (e) { detail.err = String((e && e.message) || e); }"
                       " detail.started = true;"
                       " return detail; })(arguments[0])", [conversation_id])

        def requested_poll(marker):
            return (
                "return (async (conversationId) => { /* " + marker + " */"
                " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
                " const t = (st.turns||[]).find(x => x.requestedModel === '" + marker_model + "'"
                "  && (!conversationId || x.conversationId === conversationId)) || {};"
                " return {captureId: t.captureId || null, ctx: t.captureContextId || null,"
                "  phase: t.phase || null, errorCode: t.errorCode || null}; })()")

        # 2) the page starts the creation request (conversation_id null) and
        #    navigates to the temporary draft URL while the request is in
        #    flight, in one script execution, exactly like the real new-chat
        #    order; the page-hook under test generates the capture id and its
        #    wrapped pushState drives the tracker navigation
        kick = start_request("", "navcheck-b-fetch")
        exe("return (function () { /* navcheck-d-temp-push */"
            " history.pushState({}, '', '" + temp_path + "');"
            " return {pushed: true, url: location.pathname}; })()")
        requested = nav_poll(requested_poll("navcheck-c-requested"), [""],
                             want=lambda v: isinstance(v, dict) and v.get("captureId")
                             and v.get("phase") in ("requested", "failed"))
        if not (isinstance(requested, dict) and requested.get("captureId")
                and requested.get("ctx") == creation_ctx):
            raise RuntimeError("requested observation not generated by page-hook: requested=%r kick=%r"
                               % (requested, kick))
        nav_capture = requested["captureId"]

        # 3) the tracker under test must have kept the creation context id
        #    across the temporary URL (v1.0.9 fix semantic)
        temp_ctx = nav_poll(
            "return (async (captureId) => { /* navcheck-e-temp-ctx */"
            " const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'});"
            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
            " const ctx = st && st.captureContexts ? st.captureContexts[tabs[0].id] : null;"
            " const t = (st.turns||[]).find(x => x.captureId === captureId) || {};"
            " return {ctxId: ctx ? ctx.id : null, turnCtx: t.captureContextId || null,"
            "  pageUrl: ctx ? ctx.pageUrl : null}; })(arguments[0])", [nav_capture],
            want=lambda v: isinstance(v, dict) and v.get("ctxId"))
        temp_ok = isinstance(temp_ctx, dict) and temp_ctx.get("ctxId") == creation_ctx

        # 4) the real response (unauthenticated rejection) arrives after the
        #    navigation and must land in the same capture record
        settled = nav_poll(
            "return (async (captureId) => { /* navcheck-f-response */"
            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
            " const t = (st.turns||[]).find(x => x.captureId === captureId) || {};"
            " return {phase: t.phase || null, errorCode: t.errorCode || null,"
            "  ctx: t.captureContextId || null}; })(arguments[0])", [nav_capture],
            want=lambda v: isinstance(v, dict) and v.get("phase") not in (None, "requested"))
        response_ok = isinstance(settled, dict) and settled.get("phase") == "failed" and \
            bool(settled.get("errorCode")) and settled.get("ctx") == creation_ctx

        # 5) a follow-up creation request carries the conversation correlation
        #    in its body, exactly like the request parser reads it; the tracker
        #    under test then assigns the conversation to the current context
        kick2 = start_request("navcheck-conv", "navcheck-e2-fetch")
        identity = nav_poll(requested_poll("navcheck-f-identity"), ["navcheck-conv"],
                            want=lambda v: isinstance(v, dict) and v.get("captureId")
                            and v.get("captureId") != nav_capture)
        if not (isinstance(identity, dict) and identity.get("captureId")
                and identity.get("ctx") == creation_ctx):
            raise RuntimeError("correlated request was not associated: %r" % (identity,))

        # 6) navigate to the formal conversation URL: the promoted creation
        #    must keep the same context id
        go_page()
        exe("return (function () { /* navcheck-g-formal-push */"
            " history.pushState({}, '', '" + formal_path + "');"
            " return {pushed: true, url: location.pathname}; })()")
        formal_ctx = nav_poll(
            "return (async (captureId) => { /* navcheck-h-formal-ctx */"
            " const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'});"
            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
            " const ctx = st && st.captureContexts ? st.captureContexts[tabs[0].id] : null;"
            " return {ctxId: ctx ? ctx.id : null, turnCtx: ((st.turns||[])"
            "  .find(x => x.captureId === captureId) || {}).captureContextId || null}; })(arguments[0])",
            [identity["captureId"]],
            want=lambda v: isinstance(v, dict) and v.get("ctxId") == creation_ctx)
        formal_ok = isinstance(formal_ctx, dict) and formal_ctx.get("ctxId") == creation_ctx

        # 7) the overlay must still show this record as the current one
        def overlay_text(marker):
            return exe("return (() => { /* " + marker + " */"
                       " const root = document.getElementById('chatgpt-route-inspector-root');"
                       " if (!root || !root.shadowRoot) return {overlay: false, text: ''};"
                       " const el = root.shadowRoot.querySelector('.probe') || root.shadowRoot.querySelector('.disconnected');"
                       " return {overlay: true, text: el ? String(el.textContent).slice(0, 500) : ''}; })()")
        go_page()
        shown = None
        for _ in range(20):
            time.sleep(0.5)
            shown = overlay_text("navcheck-j-overlay")
            if isinstance(shown, dict) and "navcheck" in str(shown.get("text", "")).lower():
                break
        overlay_ok = isinstance(shown, dict) and shown.get("overlay") is True and \
            "navcheck" in str(shown.get("text", "")).lower()

        # 8) switching to an unrelated conversation must retire the record
        go_page()
        exe("return (function () { /* navcheck-k-unrelated-push */"
            " history.pushState({}, '', '" + unrelated_path + "');"
            " return {pushed: true}; })()")
        unrelated = nav_poll(
            "return (async (captureId) => { /* navcheck-l-unrelated */"
            " const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'});"
            " const st = (await chrome.runtime.sendMessage({type:'route:get-state'})).state;"
            " const ctx = st && st.captureContexts ? st.captureContexts[tabs[0].id] : null;"
            " const currentTurns = (st.turns||[]).filter(x => x.captureContextId === (ctx ? ctx.id : null));"
            " return {ctxId: ctx ? ctx.id : null,"
            "  oursCurrent: currentTurns.some(x => x.captureId === captureId)}; })(arguments[0])",
            [nav_capture],
            want=lambda v: isinstance(v, dict) and v.get("ctxId") not in (None, creation_ctx))
        unrelated_ctx = unrelated.get("ctxId") if isinstance(unrelated, dict) else None
        gone = overlay_text("navcheck-m-overlay-gone")
        gone_ok = isinstance(gone, dict) and "navcheck" not in str(gone.get("text", "")).lower()

        add("19.new-chat-navigation-association",
            bool(temp_ok and formal_ok and response_ok and overlay_ok and unrelated_ctx
                 and unrelated_ctx != creation_ctx and gone_ok
                 and isinstance(kick, dict) and kick.get("started") is True
                 and isinstance(kick2, dict) and kick2.get("started") is True),
            {"captureId": nav_capture, "creationCtx": creation_ctx,
             "tempCtx": (temp_ctx or {}).get("ctxId"), "tempPageUrl": (temp_ctx or {}).get("pageUrl"),
             "responseArrived": {"phase": (settled or {}).get("phase"), "errorCode": (settled or {}).get("errorCode"),
                                 "ctx": (settled or {}).get("ctx")},
             "correlatedCaptureId": (identity or {}).get("captureId"),
             "formalCtx": (formal_ctx or {}).get("ctxId"),
             "overlayShown": (shown or {}).get("text", "")[:120],
             "unrelatedCtx": unrelated_ctx, "overlayAfterSwitch": (gone or {}).get("text", "")[:120]})
    except Exception as error:
        add("19.new-chat-navigation-association", False, error)

    # Note (v1.0.9): the upstream "extension disconnected -> refresh page"
    # overlay card is covered by upstream tests with a mocked context failure
    # (tests/integration/bridge-lifecycle.test.ts). A real-browser trigger is
    # not reproducible on Firefox 156: after Addon:Install (update) and
    # Addon:Uninstall the page's content script does not survive as an orphan,
    # so its overlay buttons can no longer call anything. Three probe runs
    # (results kept in docs/upgrade-2026-09-27/) recorded the finding; the
    # scenario was therefore not kept as a required browser check.

    meta["connectionTrusted"] = True
    return {"trusted": True, "aborted": None}


# --- argument parsing -------------------------------------------------------
class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        raise SystemExit(EXIT_USAGE)


def parse_args(argv):
    parser = Parser(description="Real-Firefox Marionette verification probe (owns its browser).")
    parser.add_argument("--xpi", required=True, help="XPI built from the current dist/firefox")
    parser.add_argument("--expect-build-record", default=None,
                        help="build record written by scripts/package-firefox.mjs for THIS build")
    parser.add_argument("--expect-xpi-sha256", default=None,
                        help="expected whole-archive sha256 (alternative to --expect-build-record)")
    parser.add_argument("--dist", default=os.path.join(SCRIPT_DIR, "dist", "firefox"),
                        help="dist tree the XPI was packaged from")
    parser.add_argument("--out", default=None,
                        help="results path; omitted -> fresh non-colliding name; existing file is refused")
    parser.add_argument("--force", action="store_true", help="allow overwriting an existing --out file")
    parser.add_argument("--label", default="")
    parser.add_argument("--commit", default="")
    parser.add_argument("--firefox", default=DEFAULT_FIREFOX)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 -> pick a free port for this run")
    parser.add_argument("--startup-timeout", type=float, default=90.0)
    parser.add_argument("--announcement-ui", default="ui/announcement/index.html")
    parser.add_argument("--keep-profile", action="store_true", help="do not delete the temp profile afterwards")
    parser.add_argument("--keep-browser", action="store_true", help="do not stop the browser this run started")
    return parser.parse_args(argv)


def git_state(repo_dir, fallback_commit):
    info = {"repoDir": repo_dir, "available": False, "head": None, "dirty": None,
            "porcelain": None, "error": None}

    def run(*argv):
        p = subprocess.run(["git", "-C", repo_dir, *argv], capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or "").strip() or "exit %s" % p.returncode)
        return p.stdout

    try:
        info["head"] = run("rev-parse", "HEAD").strip()
        porcelain = run("status", "--porcelain", "-uall")
        info["porcelain"] = porcelain.strip()
        info["dirty"] = bool(porcelain.strip())
        info["available"] = True
    except Exception as error:
        info["error"] = "%s" % (error,)
    info["labelCommit"] = fallback_commit
    return info


def load_build_record(path):
    """Return (record, error). Never raises; never invents an expectation."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except FileNotFoundError:
        return None, "build record not found: %s" % path
    except Exception as error:
        return None, "build record is not readable JSON (%s: %s)" % (type(error).__name__, error)
    if not isinstance(record, dict):
        return None, "build record is a JSON %s, expected an object" % type(record).__name__
    if not isinstance(record.get("xpiSha256"), str) or not record.get("xpiSha256"):
        return None, "build record has no usable string field xpiSha256"
    for key, expected_type in (("manifestSha256", str), ("fileHashes", dict),
                               ("distDir", str), ("xpiPath", str)):
        value = record.get(key)
        if value is not None and not isinstance(value, expected_type):
            return None, "build record field %s has type %s, expected %s" % (
                key, type(value).__name__, expected_type.__name__)
    if not isinstance(record.get("fileHashes"), dict) or not record["fileHashes"]:
        return None, "build record has no usable fileHashes map"
    return record, None


def ensure_output_writable(out_path):
    """Fail fast when the results file could never be written.

    Deliberately creates nothing. An earlier version wrote a zero-byte probe
    file into the destination directory and deleted it again to prove
    writability; that left `.ff-probe-write-probe-*` artefacts next to the
    evidence. Only the target and its parent are inspected here, and the real
    write happens once, at the very end.
    """
    parent = os.path.dirname(out_path) or "."
    try:
        os.makedirs(parent, exist_ok=True)
    except Exception as error:
        return "output directory cannot be created (%s: %s)" % (type(error).__name__, error)
    if not os.path.isdir(parent):
        return "output directory is not a directory: %s" % parent
    if os.path.isdir(out_path):
        return "output path is an existing directory: %s" % out_path
    if not os.access(parent, os.W_OK):
        return "output directory is not writable: %s" % parent
    return None


# --- main -------------------------------------------------------------------
def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    # Marionette's Addon:Install requires an absolute path, and all identity
    # hashing must be cwd-independent.
    args.xpi = os.path.abspath(args.xpi)
    if args.expect_build_record:
        args.expect_build_record = os.path.abspath(args.expect_build_record)
    args.dist = os.path.abspath(args.dist)

    # Output protection happens first: never touch an existing evidence file and
    # never start a browser just to discover that the results cannot be saved.
    out_path = args.out or default_out_path(SCRIPT_DIR, args.label)
    if os.path.exists(out_path) and not args.force:
        if os.path.isdir(out_path):
            sys.stderr.write("refusing to use an existing directory as the results file: %s\n" % out_path)
        else:
            sys.stderr.write("refusing to overwrite existing results file: %s\n" % out_path)
        sys.stderr.write("pass --force to overwrite, or choose another --out\n")
        return EXIT_OUTPUT_EXISTS
    output_error = ensure_output_writable(out_path)
    if output_error:
        sys.stderr.write("cannot write results to %s: %s\n" % (out_path, output_error))
        sys.stderr.write("choose a writable --out; no file was created or changed\n")
        return EXIT_FATAL

    # From here on every failure must still leave a usable result file, so the
    # whole run is covered by one handler that records how far it got.
    meta = {
        "schema": "ff-probe/2",
        "date": time.strftime("%Y-%m-%d"),
        "startedAt": started_at,
        "finishedAt": None,
        "label": args.label,
        "probeFile": os.path.abspath(__file__),
        "probeSha256": None,
        "stage": "start",
        "reachedStages": [],
        "identity": None,
        "expectation": {
            "source": ("build-record: %s" % args.expect_build_record) if args.expect_build_record
                      else ("--expect-xpi-sha256" if args.expect_xpi_sha256 else "none"),
            "expectedXpiSha256": args.expect_xpi_sha256,
            "buildRecordSha256": None,
            "buildRecordError": None,
        },
        "git": None,
        "launch": None,
        "session": None,
        "browserLaunched": False,
        "browserConnected": False,
        "connectionTrusted": None,
        "firefoxVersion": None,
        "fatal": None,
        "summary": None,
        "exitCode": None,
        "exitReason": None,
        "resultsPath": os.path.abspath(out_path),
        "notes": [],
    }

    results = []
    record = None
    record_error = None
    identity_ok = False
    fatal = None
    aborted = None
    proc = None
    connection = None
    profile_dir = None
    profile_removed = None

    def stage(name):
        meta["stage"] = name
        meta["reachedStages"].append(name)

    try:
        stage("probe-hash")
        try:
            meta["probeSha256"] = sha256_file(os.path.abspath(__file__))
        except Exception as error:
            meta["notes"].append("probe sha256 unavailable: %s" % (error,))
        stage("git")
        meta["git"] = git_state(SCRIPT_DIR, args.commit)

        if args.expect_build_record:
            stage("build-record")
            record, record_error = load_build_record(args.expect_build_record)
            if record_error:
                results.append({"check": "0f.build-record", "ok": False, "detail": record_error})
                print("FAIL 0f.build-record | %s" % record_error, flush=True)
                meta["expectation"]["buildRecordError"] = record_error
            else:
                results.append({"check": "0f.build-record", "ok": True,
                                "detail": "xpiSha256=%s manifestSha256=%s files=%d" % (
                                    record["xpiSha256"][:16],
                                    str(record.get("manifestSha256"))[:16],
                                    len(record["fileHashes"]))})
                print("PASS 0f.build-record | xpi=%s files=%d" % (
                    record["xpiSha256"][:16], len(record["fileHashes"])), flush=True)
                try:
                    meta["expectation"]["buildRecordSha256"] = sha256_file(args.expect_build_record)
                except Exception as error:
                    meta["notes"].append("build record sha256 unavailable: %s" % (error,))

        stage("identity")
        expected_sha = args.expect_xpi_sha256 or (record or {}).get("xpiSha256")
        meta["expectation"]["expectedXpiSha256"] = expected_sha
        identity_checks, identity_meta = verify_identity(
            args.xpi, args.dist, expected_sha, record, args.expect_build_record or "")
        results.extend(identity_checks)
        meta["identity"] = identity_meta
        identity_ok = all(check["ok"] for check in identity_checks)
        if record_error:
            # An unusable expectation source means identity was not established,
            # however the remaining checks turned out.
            identity_ok = False

        if identity_ok:
            stage("browser")
            port = args.port or free_port()
            profile_root = os.path.join(tempfile.gettempdir(), "ff-ri-probe-profiles")
            os.makedirs(profile_root, exist_ok=True)
            profile_dir = make_profile(profile_root)
            proc, argv_launch = launch_firefox(args.firefox, profile_dir, port)
            meta["browserLaunched"] = True
            meta["launch"] = {
                "firefoxExe": args.firefox,
                "pid": proc.pid,
                "host": args.host,
                "port": port,
                "profileDir": profile_dir,
                "cmdline": argv_launch,
                "launchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "expectedManifestVersion": identity_meta["manifestVersion"],
            }
            print("launched firefox pid=%s port=%s profile=%s" % (proc.pid, port, profile_dir), flush=True)
            wait_for_port(args.host, port, args.startup_timeout, proc)
            stage("connect")
            connection = Marionette(args.host, port)
            meta["browserConnected"] = True
            session = connection.cmd("WebDriver:NewSession", {"capabilities": {
                "moz:firefoxOptions": {"prefs": {"xpinstall.signatures.required": False}}
            }})
            caps = session.get("capabilities") or {}
            meta["session"] = {
                "sessionId": session.get("sessionId"),
                "capabilities": {k: caps.get(k) for k in
                                 ("browserName", "browserVersion", "platformName",
                                  "moz:profile", "moz:buildID", "moz:headless",
                                  "moz:geckodriverVersion")},
            }
            stage("checks")
            # Nothing beyond WebDriver:NewSession is sent until the checks have
            # verified that this connection is the browser this run created.
            verdict = run_browser_checks(connection, meta, args, results)
            aborted = verdict["aborted"]
        else:
            meta["notes"].append("identity rejected; browser was not launched, connected, installed to or uninstalled from")
    except BaseException as error:  # includes TimeoutError, ConnectionError, RuntimeError
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            fatal = RuntimeError("interrupted: %s" % (error,))
        else:
            fatal = error
        print("FATAL [%s] %s: %s" % (meta["stage"], type(error).__name__, error), flush=True)
    finally:
        # Cleanup must never swallow the failure we already recorded, and must
        # never send a state-changing command to a connection whose identity was
        # not verified - including the session teardown, which would act on
        # whatever browser happens to be on the other end of the socket.
        try:
            if connection is not None:
                if meta.get("connectionTrusted"):
                    try:
                        connection.cmd("WebDriver:DeleteSession", {})
                    except Exception:
                        pass
                else:
                    meta["notes"].append(
                        "session was not deleted: this connection was never verified as the browser this run created")
                connection.close()
        except Exception:
            pass
        if not args.keep_browser:
            stop_firefox(proc)
        if args.keep_profile:
            profile_removed = False
        else:
            profile_removed = remove_profile(profile_dir)

    if fatal is not None:
        meta["fatal"] = "%s: %s" % (type(fatal).__name__, fatal)

    executed = {c["check"] for c in results}
    required = list(REQUIRED_CHECKS)
    if args.expect_build_record:
        required += REQUIRED_WITH_RECORD
    failed_checks = [c["check"] for c in results if not c["ok"]]
    missing_checks = [name for name in required if name not in executed]
    code = decide_exit_code(identity_ok, fatal, failed_checks, missing_checks, aborted)
    meta["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta["summary"] = {
        "executed": len(results),
        "passed": sum(1 for c in results if c["ok"]),
        "failed": len(failed_checks),
        "failedChecks": failed_checks,
        "requiredChecks": required,
        "missingChecks": missing_checks,
        "identityOk": identity_ok,
        "aborted": aborted,
        "stage": meta["stage"],
        "browserLaunched": meta["browserLaunched"],
        "browserConnected": meta["browserConnected"],
        "connectionTrusted": meta.get("connectionTrusted"),
        "profileDir": profile_dir,
        "profileDirRemoved": profile_removed,
        "profilesKeptByRequest": bool(args.keep_profile),
        "browserStoppedByThisRun": (not args.keep_browser) and proc is not None,
    }
    if profile_removed is False and profile_dir:
        meta["notes"].append("temporary profile could not be fully removed: %s" % profile_dir)
    meta["exitCode"] = code
    meta["exitReason"] = exit_reason(code, identity_ok, fatal, failed_checks, missing_checks, aborted)

    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"meta": meta, "results": results}, handle, ensure_ascii=False, indent=1)
    except Exception as error:
        sys.stderr.write("failed to write results to %s: %s\n" % (out_path, error))
        return EXIT_FATAL

    print("%d passed / %d failed / %d missing -> exit %d (%s)"
          % (meta["summary"]["passed"], len(failed_checks), len(missing_checks), code, meta["exitReason"]))
    print("saved %s" % out_path)
    return code


if __name__ == "__main__":
    sys.exit(main())
