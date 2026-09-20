"""Real-Firefox verification via raw Marionette protocol (stdlib only).

Usage:
  python ff-marionette.py --xpi <built.xpi> [--expect-manifest-sha256 <sha>]
                          [--host 127.0.0.1] [--port 2828]
                          [--out <results.json>]
                          [--label <text>] [--commit <sha>]
                          [--announcement-ui ui/announcement/index.html]

The caller launches Firefox with `-marionette -profile <dedicated temp profile>`;
this script never touches a daily-driver profile. If --expect-manifest-sha256 is
given, the XPI's packaged manifest.json is hashed first and the run aborts on a
mismatch, so an old or stale XPI can never be reported as this build.

Output: JSON object with a `meta` block (date, label, commit, XPI + manifest
hashes, Firefox version) and the `results` list.
"""
import argparse, hashlib, json, os, re, socket, sys, time, zipfile

DEFAULT_OUT = r"D:\LAB\火狐浏览器插件制作2\ff-probe-results.json"
EXT_ID = "chatgpt-route-inspector-firefox@local"


def parse_args():
    parser = argparse.ArgumentParser(description="Real-Firefox Marionette verification probe.")
    parser.add_argument("--xpi", required=True, help="XPI built from the current dist/firefox")
    parser.add_argument("--expect-manifest-sha256", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2828)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--label", default="")
    parser.add_argument("--commit", default="")
    parser.add_argument("--announcement-ui", default="ui/announcement/index.html")
    return parser.parse_args()


ARGS = parse_args()
OUT = []
META = {
    "date": time.strftime("%Y-%m-%d"),
    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "label": ARGS.label,
    "commit": ARGS.commit,
    "xpi": ARGS.xpi,
    "xpiSha256": None,
    "manifestSha256": None,
    "manifestsMatchExpected": None,
    "manifestVersion": None,
    "geckoId": None,
    "strictMinVersion": None,
    "firefoxVersion": None,
    "profile": os.environ.get("FF_PROFILE", ""),
    "notes": [],
}


def log(name, ok, detail=""):
    OUT.append({"check": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:280]) if detail else ""), flush=True)


def save():
    payload = {"meta": META, "results": OUT}
    with open(ARGS.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)


def read_xpi_manifest():
    """Hash and validate the packaged manifest before touching the browser."""
    with open(ARGS.xpi, "rb") as handle:
        META["xpiSha256"] = hashlib.sha256(handle.read()).hexdigest()
    with zipfile.ZipFile(ARGS.xpi) as archive:
        raw = archive.read("manifest.json")
    META["manifestSha256"] = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(raw.decode("utf-8"))
    META["manifestVersion"] = manifest.get("version")
    gecko = (manifest.get("browser_specific_settings") or {}).get("gecko") or {}
    META["geckoId"] = gecko.get("id")
    META["strictMinVersion"] = gecko.get("strict_min_version")
    META["packagedFiles"] = len([n for n in zipfile.ZipFile(ARGS.xpi).namelist() if not n.endswith("/")])
    if ARGS.expect_manifest_sha256:
        META["manifestsMatchExpected"] = META["manifestSha256"] == ARGS.expect_manifest_sha256


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
            if not chunk: raise ConnectionError("eof")
            self.buf += chunk
        ln, rest = self.buf.split(b":", 1)
        n = int(ln)
        while len(rest) < n:
            chunk = self.s.recv(65536)
            if not chunk: raise ConnectionError("eof")
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
                    raise RuntimeError(f"{method} -> {msg[2]}")
                return msg[3]
            # ignore async events / mismatched messages

    def close(self):
        try: self.s.close()
        except Exception: pass


# --- preflight: the XPI must be this build before any browser interaction ------
# NOTE: Firefox >= ~156 rejects WebDriver:ExecuteScript in privileged (extension)
# browsing contexts unless the browser is started with -remote-allow-system-access.
# Without that flag every extension-context check below fails with
# "unsupported operation". See README-FIREFOX.md.
read_xpi_manifest()
if META["manifestsMatchExpected"] is False:
    log("0a.xpi-manifest-hash", False,
        f"packaged manifest {META['manifestSha256']} != expected {ARGS.expect_manifest_sha256}")
    save()
    raise SystemExit(2)
log("0a.xpi-identity", META["manifestsMatchExpected"] is not False,
    f"version={META['manifestVersion']} gecko={META['geckoId']} "
    f"min={META['strictMinVersion']} manifest_sha256={META['manifestSha256']}")

m = Marionette(ARGS.host, ARGS.port)
try:
    sess = m.cmd("WebDriver:NewSession", {"capabilities": {
        "moz:firefoxOptions": {"prefs": {"xpinstall.signatures.required": False}}
    }})
    log("0.session", bool(sess.get("sessionId")), sess.get("sessionId"))
except Exception as e:
    log("0.session", False, e); m.close(); save(); raise SystemExit(1)

try:
    META["firefoxVersion"] = m.cmd("WebDriver:ExecuteScript", {"script": "return navigator.userAgent", "args": []})["value"]
except Exception as e:
    META["firefoxVersion"] = f"unavailable: {e}"


def exe(script, args=None):
    return m.cmd("WebDriver:ExecuteScript", {"script": script, "args": args or []})["value"]


def nav(url):
    m.cmd("WebDriver:Navigate", {"url": url})


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


def open_extension_page(url):
    shexe("return (async (u) => { const t = await chrome.tabs.create({url: u}); return t.id; })(arguments[0])", [url])
    time.sleep(2)
    return find_handle(url.split(EXT + "/", 1)[-1])


try:
    time.sleep(2)
    uuid = None
    try:
        try: m.cmd("Addon:Uninstall", {"id": EXT_ID})
        except Exception: pass
        time.sleep(1)
        r = m.cmd("Addon:Install", {"path": ARGS.xpi, "temporary": True})
        log("1.install-no-manifest-error", True, r.get("value", r))
    except Exception as e:
        log("1.install-no-manifest-error", False, e); raise SystemExit(1)
    try:
        time.sleep(3)
        handles_all = handles()
        url = None
        for h in handles_all:
            try:
                m.cmd("WebDriver:SwitchToWindow", {"handle": h})
                url = m.cmd("WebDriver:GetCurrentURL")["value"]
            except Exception:
                continue
            found = re.search(r"moz-extension://([0-9a-f-]{36})(/ui/onboarding/index\.html)?", url or "")
            if found:
                uuid = found.group(1)
                break
        log("1b.addon-uuid", bool(uuid), f"handles={len(handles_all)} uuid={uuid} last_url={(url or '')[:120]}")
    except Exception as e:
        log("1b.addon-uuid", False, e)
    if not uuid:
        log("1b.addon-registered", False, "uuid not found"); raise SystemExit(1)
    EXT = f"moz-extension://{uuid}"
    shell = h  # onboarding tab handle = our shell inside extension context

    def shexe(script, args=None):
        m.cmd("WebDriver:SwitchToWindow", {"handle": shell})
        return exe(script, args)

    # --- extension-context probes (same principal/binding as background page) ---
    log("2.ext-namespaces", shexe("return {c: typeof chrome, b: typeof browser, url: location.href}"))
    try:
        v = shexe("return (async () => { await chrome.storage.local.set({ffprobe: 42}); const g = await chrome.storage.local.get('ffprobe'); return g.ffprobe; })()")
        log("3.ext-chrome.storage-promise", v == 42, v)
    except Exception as e:
        log("3.ext-chrome.storage-promise", False, e)
    try:
        v = shexe("return (async () => { const r = await chrome.runtime.sendMessage({type:'route:get-state'}); return {ok: r.ok, hasState: !!r.state, schemaVersion: ((r.state.turns||[])[0]||{}).schemaVersion || null}; })()")
        log("4.ext-get-state-roundtrip", v.get("ok") and v.get("hasState"), v)
    except Exception as e:
        log("4.ext-get-state-roundtrip", False, e)
    try:
        v = shexe("return (async () => ({tabs: (await chrome.tabs.query({})).length, lang: chrome.i18n.getUILanguage(), url: chrome.runtime.getURL('ui/popup/index.html'), version: chrome.runtime.getManifest().version}))()")
        log("5.ext-tabs-i18n-getURL", isinstance(v, dict) and str(v.get("url")).startswith("moz-extension://") and v.get("version") == META["manifestVersion"], v)
    except Exception as e:
        log("5.ext-tabs-i18n-getURL", False, e)

    # --- open popup via extension tabs API, read its DOM ---
    try:
        popup = open_extension_page(EXT + "/ui/popup/index.html")
        t = exe("return document.body ? document.body.textContent.slice(0, 200) : null") if popup else None
        log("6.popup-renders", bool(t and len(t.strip()) > 10), t)
    except Exception as e:
        log("6.popup-renders", False, e); popup = None
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        obs = {"captureId": "ff-probe-1", "source": "page_fetch", "captureMode": "live",
               "phase": "completed", "observedAt": now, "startedAt": now, "completedAt": now,
               "pageUrl": "https://chatgpt.com/c/ffprobe", "requestedModel": "gpt-5-6-pro",
               "resolvedModelSlug": "gpt-5-5-mini"}
        v = shexe("return (async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o}); const t0 = (r.state.turns||[])[0]||{}; return {ok:r.ok, turns:(r.state.turns||[]).length, verdict:t0.verdict, route:t0.routeModel, req:t0.requestedModel, schemaVersion:t0.schemaVersion}; })(arguments[0])", [obs])
        log("7.synthetic-observation-pipeline",
            v.get("ok") and v.get("turns") == 1 and v.get("req") == "gpt-5-6-pro"
            and v.get("schemaVersion") == "1.7.0", v)
    except Exception as e:
        log("7.synthetic-observation-pipeline", False, e)
    try:
        # Popup filters turns by active tab id (by design, same as Chromium), so a
        # synthetic observation owned by another tab won't show there. Dashboard
        # lists all turns -> the right surface to assert UI display.
        dash = open_extension_page(EXT + "/ui/dashboard/index.html")
        if dash:
            m.cmd("WebDriver:SwitchToWindow", {"handle": dash})
            time.sleep(1)
            t = exe("return document.body.textContent") or ""
            log("8.dashboard-shows-turn", ("GPT 5.6 Pro" in t) and ("GPT 5.5 mini" in t or "gpt-5-5-mini" in t), t[:300])
        else:
            log("8.dashboard-shows-turn", False, "no dashboard handle")
    except Exception as e:
        log("8.dashboard-shows-turn", False, e)

    try:
        w = m.cmd("WebDriver:NewWindow", {"type": "tab"})
        w = w.get("value", w) if isinstance(w, dict) else w
        w = w["handle"]
        m.cmd("WebDriver:SwitchToWindow", {"handle": w})
        nav("https://chatgpt.com/"); time.sleep(8)
        v = exe("return {fetchName: (window.fetch && window.fetch.name) || null, overlay: !!document.getElementById('chatgpt-route-inspector-root'), url: location.href}")
        log("9.page-hook-MAIN-world", v.get("fetchName") == "routeInspectorFetch", v)
        log("10.bridge-overlay-ISOLATED", v.get("overlay") is True, v)
        # v1.0.7: the announcement hint is gated on the running version (1.0.7).
        try:
            hint = exe("return (() => { const root = document.getElementById('chatgpt-route-inspector-root'); if (!root || !root.shadowRoot) return {root: !!root}; const sr = root.shadowRoot; const star = sr.getElementById('notice-star'); return {root: true, notice: !!sr.getElementById('route-notice'), star: !!star, error: !!sr.getElementById('notice-error')}; })()")
            log("11.notice-hint-1.0.7", hint.get("notice") is True and hint.get("star") is True, hint)
        except Exception as e:
            log("11.notice-hint-1.0.7", False, e)
    except Exception as e:
        log("9.page-hook-MAIN-world", False, e); log("10.bridge-overlay-ISOLATED", False, e)

    # v1.0.7: MAIN/bridge handshake must register a capture context for the page tab.
    try:
        time.sleep(2)
        v = shexe("return (async () => { const r = await chrome.runtime.sendMessage({type:'route:get-state'}); const contexts = r.state.captureContexts || {}; const ids = Object.keys(contexts); return {ok: r.ok, count: ids.length, sample: ids.length ? contexts[ids[0]] : null}; })()")
        log("12.capture-context-registered", v.get("ok") and v.get("count", 0) >= 1, v)
    except Exception as e:
        log("12.capture-context-registered", False, e)

    # v1.0.7: synthetic auto-thinking route must be classified as auto_reasoning.
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        obs = {"captureId": "ff-probe-auto", "source": "page_fetch", "captureMode": "live",
               "phase": "completed", "observedAt": now, "startedAt": now, "completedAt": now,
               "pageUrl": "https://chatgpt.com/c/ffprobe", "requestedModel": "gpt-5-6",
               "resolvedModelSlug": "gpt-5-6-auto-thinking", "serverModelSlug": "gpt-5-6-auto-thinking"}
        v = shexe("return (async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o}); const t = (r.state.turns||[]).find(x => x.captureId === 'ff-probe-auto') || {}; return {ok:r.ok, verdict:t.verdict, route:t.routeModel, schemaVersion:t.schemaVersion}; })(arguments[0])", [obs])
        log("13.auto-reasoning-verdict", v.get("ok") and v.get("verdict") == "auto_reasoning" and v.get("route") == "gpt-5-6-auto-thinking", v)
    except Exception as e:
        log("13.auto-reasoning-verdict", False, e)

    # v1.0.7: the announcement page must be shipped, local, and render its body.
    try:
        page = open_extension_page(f"{EXT}/{ARGS.announcement_ui}")
        if page:
            m.cmd("WebDriver:SwitchToWindow", {"handle": page})
            time.sleep(1)
            v = exe("return {title: document.title, text: document.body ? document.body.textContent.slice(0, 400) : null, script: !!document.querySelector('script[src=\"index.js\"]'), href: document.getElementById('notice-poll') ? document.getElementById('notice-poll').getAttribute('href') : null}")
            text = v.get("text") or ""
            log("14.announcement-page", ("1.0.7" in text) and v.get("script") is True and str(v.get("href", "")).startswith("https://x.com/"), v)
        else:
            log("14.announcement-page", False, "no announcement handle")
    except Exception as e:
        log("14.announcement-page", False, e)

    # v1.0.7: closing the notice must not disturb route history.
    try:
        v = shexe("return (async () => { const before = await chrome.runtime.sendMessage({type:'route:get-state'}); const r = await chrome.runtime.sendMessage({type:'route:open-announcement'}); const after = await chrome.runtime.sendMessage({type:'route:get-state'}); return {before: (before.state.turns||[]).length, after: (after.state.turns||[]).length, ok: r.ok}; })()")
        log("15.open-announcement-message", v.get("ok") is True and v.get("before") == v.get("after"), v)
    except Exception as e:
        log("15.open-announcement-message", False, e)
finally:
    save()
    try: m.cmd("WebDriver:DeleteSession", {})
    except Exception: pass
    m.close()
print("saved " + ARGS.out)
