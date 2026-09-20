"""Loader + fixtures for the Firefox verification tooling regression tests.

Everything here is synthetic: the tests never touch a real browser, a real
ChatGPT account, the daily-driver profile, or the repository's historical
evidence files.
"""
import importlib.util
import os
import sys
import zipfile

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROBE_PATH = os.path.join(REPO_ROOT, "ff-marionette.py")
# Historical evidence that must never be written by a default run.
HISTORICAL_RESULTS = os.path.join(REPO_ROOT, "ff-probe-results.json")


def load_probe(path=None):
    """Import ff-marionette.py (the file name is not a valid module name)."""
    target = path or PROBE_PATH
    spec = importlib.util.spec_from_file_location("ff_marionette_probe", target)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ff_marionette_probe"] = module
    spec.loader.exec_module(module)
    return module


# --- synthetic artifacts ----------------------------------------------------
MANIFEST = (
    '{\n'
    '  "manifest_version": 3,\n'
    '  "name": "synthetic",\n'
    '  "version": "1.0.7",\n'
    '  "background": { "scripts": ["background/service-worker.js"] },\n'
    '  "browser_specific_settings": {\n'
    '    "gecko": {\n'
    '      "id": "chatgpt-route-inspector-firefox@local",\n'
    '      "strict_min_version": "128.0"\n'
    '    }\n'
    '  }\n'
    '}\n'
)

DIST_FILES = {
    "manifest.json": MANIFEST.encode("utf-8"),
    "background/service-worker.js": b"// background v1\nexport const x = 1;\n",
    "content/page-hook.js": b"// page hook v1\nconsole.log('hook');\n",
    "content/bridge.js": b"// bridge v1\n",
    "ui/popup/index.html": b"<!doctype html><html><body>popup</body></html>\n",
    "ui/announcement/index.html": b"<!doctype html><html><body>1.0.7</body></html>\n",
}


def write_dist(root, files=None):
    files = DIST_FILES if files is None else files
    for rel, data in files.items():
        full = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
    return root


def zip_dist(dist_dir, xpi_path, extra=None, overrides=None):
    """Package a synthetic dist tree into an XPI-shaped zip."""
    overrides = overrides or {}
    with zipfile.ZipFile(xpi_path, "w", zipfile.ZIP_DEFLATED) as archive:
        entries = []
        for root, _dirs, names in os.walk(dist_dir):
            for name in names:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, dist_dir).replace(os.sep, "/")
                entries.append(rel)
        for rel in sorted(entries):
            payload = overrides.get(rel)
            if payload is None:
                with open(os.path.join(dist_dir, rel.replace("/", os.sep)), "rb") as handle:
                    payload = handle.read()
            archive.writestr(rel, payload)
        for rel, payload in (extra or {}).items():
            archive.writestr(rel, payload)
    return xpi_path


def build_record(probe, dist_dir, xpi_path):
    """Mirror what scripts/package-firefox.mjs writes next to the XPI."""
    hashes = probe.hash_tree(dist_dir)
    return {
        "version": "1.0.7",
        "geckoId": "chatgpt-route-inspector-firefox@local",
        "strictMinVersion": "128.0",
        "distDir": dist_dir,
        "createdAt": "2026-09-20T00:00:00.000Z",
        "manifestSha256": hashes["manifest.json"],
        "fileCount": len(hashes),
        "fileHashes": hashes,
        "xpiPath": xpi_path,
        "xpiSha256": probe.sha256_file(xpi_path),
    }
