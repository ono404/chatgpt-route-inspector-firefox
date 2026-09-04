"""Real-Firefox verification via raw Marionette protocol (stdlib only)."""
import socket, json, time, glob, os, sys

HOST, PORT = "127.0.0.1", 2828
PROFILE = r"C:\Users\gyjxjkg\AppData\Local\Temp\ff-route-test-profile3"
XPI = r"C:\Users\gyjxjkg\AppData\Local\Temp\route-inspector-firefox-test.xpi"
OUT_PATH = r"D:\LAB\火狐浏览器插件制作2\ff-probe-results.json"
OUT = []

def log(name, ok, detail=""):
    OUT.append({"check": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:280]) if detail else ""), flush=True)

class Marionette:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=30)
        self.s.settimeout(120)
        self.buf = b""
        self.msgid = 0
        self._read_msg()  # handshake greeting

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

m = Marionette()
try:
    sess = m.cmd("WebDriver:NewSession", {"capabilities": {
        "moz:firefoxOptions": {"prefs": {"xpinstall.signatures.required": False}}
    }})
    log("0.session", bool(sess.get("sessionId")), sess.get("sessionId"))
except Exception as e:
    log("0.session", False, e); m.close(); raise SystemExit(1)

def exe(script, args=None):
    return m.cmd("WebDriver:ExecuteScript", {"script": script, "args": args or []})["value"]
def nav(url):
    m.cmd("WebDriver:Navigate", {"url": url})

try:
    time.sleep(2)
    uuid = None
    # Release Firefox enforces signing: only temporary installs work, and their
    # UUID lives in memory only. But the background's onInstalled handler opens
    # the onboarding page in a tab on install -> read its URL to learn the UUID.
    # (This also proves the background listener + tabs.create work.)
    try:
        try: m.cmd("Addon:Uninstall", {"id": "chatgpt-route-inspector-firefox@local"})
        except Exception: pass
        time.sleep(1)
        r = m.cmd("Addon:Install", {"path": XPI, "temporary": True})
        log("1.install-no-manifest-error", True, r.get("value", r))
    except Exception as e:
        log("1.install-no-manifest-error", False, e); raise SystemExit(1)
    try:
        import re as _re
        time.sleep(3)
        handles = m.cmd("WebDriver:GetWindowHandles")
        handles = handles["value"] if isinstance(handles, dict) else handles
        for h in handles:
            try:
                m.cmd("WebDriver:SwitchToWindow", {"handle": h})
                url = m.cmd("WebDriver:GetCurrentURL")["value"]
            except Exception:
                continue
            m2 = _re.search(r"moz-extension://([0-9a-f-]{36})(/ui/onboarding/index\.html)?", url or "")
            if m2:
                uuid = m2.group(1)
                break
        log("1b.addon-uuid", bool(uuid), f"handles={len(handles)} uuid={uuid} last_url={(url or '')[:120]}")
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
        v = shexe("return (async () => { const r = await chrome.runtime.sendMessage({type:'route:get-state'}); return {ok: r.ok, hasState: !!r.state}; })()")
        log("4.ext-get-state-roundtrip", v.get("ok") and v.get("hasState"), v)
    except Exception as e:
        log("4.ext-get-state-roundtrip", False, e)
    try:
        v = shexe("return (async () => ({tabs: (await chrome.tabs.query({})).length, lang: chrome.i18n.getUILanguage(), url: chrome.runtime.getURL('ui/popup/index.html')}))()")
        log("5.ext-tabs-i18n-getURL", isinstance(v, dict) and str(v.get("url")).startswith("moz-extension://"), v)
    except Exception as e:
        log("5.ext-tabs-i18n-getURL", False, e)

    # --- open popup via extension tabs API, read its DOM ---
    try:
        shexe("return (async (u) => { const t = await chrome.tabs.create({url: u}); return t.id; })(arguments[0])", [EXT + "/ui/popup/index.html"])
        time.sleep(2)
        handles = m.cmd("WebDriver:GetWindowHandles")
        handles = handles["value"] if isinstance(handles, dict) else handles
        popup = None
        for h2 in handles:
            m.cmd("WebDriver:SwitchToWindow", {"handle": h2})
            if "ui/popup/index.html" in (m.cmd("WebDriver:GetCurrentURL")["value"] or ""):
                popup = h2
                break
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
        v = shexe("return (async (o) => { const r = await chrome.runtime.sendMessage({type:'route:observation', observation:o}); const t0 = (r.state.turns||[])[0]||{}; return {ok:r.ok, turns:(r.state.turns||[]).length, verdict:t0.verdict, route:t0.routeModel, req:t0.requestedModel}; })(arguments[0])", [obs])
        log("7.synthetic-observation-pipeline", v.get("ok") and v.get("turns") == 1 and v.get("req") == "gpt-5-6-pro", v)
    except Exception as e:
        log("7.synthetic-observation-pipeline", False, e)
    try:
        # Popup filters turns by active tab id (by design, same as Chromium), so a
        # synthetic observation owned by another tab won't show there. Dashboard
        # lists all turns -> the right surface to assert UI display.
        shexe("return (async (u) => { const t = await chrome.tabs.create({url: u}); return t.id; })(arguments[0])", [EXT + "/ui/dashboard/index.html"])
        time.sleep(2)
        handles = m.cmd("WebDriver:GetWindowHandles")
        handles = handles["value"] if isinstance(handles, dict) else handles
        dash = None
        for h2 in handles:
            m.cmd("WebDriver:SwitchToWindow", {"handle": h2})
            if "ui/dashboard/index.html" in (m.cmd("WebDriver:GetCurrentURL")["value"] or ""):
                dash = h2
                break
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
        nav("https://chatgpt.com/"); time.sleep(6)
        v = exe("return {fetchName: (window.fetch && window.fetch.name) || null, overlay: !!document.getElementById('chatgpt-route-inspector-root'), url: location.href}")
        log("9.page-hook-MAIN-world", v.get("fetchName") == "routeInspectorFetch", v)
        log("10.bridge-overlay-ISOLATED", v.get("overlay") is True, v)
    except Exception as e:
        log("9.page-hook-MAIN-world", False, e); log("10.bridge-overlay-ISOLATED", False, e)
finally:
    json.dump(OUT, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try: m.cmd("WebDriver:DeleteSession", {})
    except Exception: pass
    m.close()
print("saved " + OUT_PATH)
