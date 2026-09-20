"""Build a tampered copy of a built dist tree, for reverse verification.

Same manifest.json, one JS file modified. Used to prove that the probe's
identity check rejects a package that a manifest-hash-only check would accept.

Usage:
  python tests/firefox-tooling/make_tampered_copy.py <src-dist> <out-xpi>

Writes the tampered tree next to <out-xpi> and prints the hashes needed to show
that the manifest is unchanged while one JS file is not.
"""
import hashlib
import os
import shutil
import sys
import zipfile

TARGET = "content/page-hook.js"


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 64
    src_dist, out_xpi = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    work = os.path.join(os.path.dirname(out_xpi), "tampered-src")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(src_dist, work)

    tampered = os.path.join(work, TARGET.replace("/", os.sep))
    with open(tampered, "ab") as handle:
        handle.write(b"\n// TAMPERED COPY FOR REVERSE VERIFICATION\n")

    files = []
    for root, _dirs, names in os.walk(work):
        for name in names:
            full = os.path.join(root, name)
            files.append(os.path.relpath(full, work).replace(os.sep, "/"))
    with zipfile.ZipFile(out_xpi, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(files):
            archive.write(os.path.join(work, rel.replace("/", os.sep)), rel)

    print("src dist     " + src_dist)
    print("tampered src " + work)
    print("tampered xpi " + out_xpi)
    print("manifest sha256 (must equal the real build) " + sha256(os.path.join(work, "manifest.json")))
    print("tampered file sha256 " + sha256(tampered))
    print("xpi sha256   " + sha256(out_xpi))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
