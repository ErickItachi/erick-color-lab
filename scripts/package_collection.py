#!/usr/bin/env python3
"""Assemble the CINÉRA commercial package locally (never publishes anything).

    python scripts/package_collection.py          # -> release/CINERA_VOL_01_v<version>/
    python scripts/package_collection.py --zip    # + .zip next to it

Safety gates (the package is not created if any fails):
  1. every .cube listed in MANIFEST.json exists and matches its SHA-256
  2. every file passed scripts/validate_luts.py (previews/reports/validation_report.json)
  3. no third-party names or private material anywhere in the package
     (case-insensitive scan of all text files and file names)
release/ is git-ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

from erick_color_lab.brand import COLLECTIONS  # noqa: E402

FOLDERS = {
    "rec709": "Rec709",
    "sony-slog3": "Sony S-Log3",
    "apple-log": "Apple Log",
    "canon-log3": "Canon Log 3",
    "creative-only": "Creative Only (ACEScct)",
}
# Customer-facing documents only (internal engineering docs are never shipped)
CUSTOMER_DOCS = {
    "docs/customer/LEIA-ME.md": "00 - LEIA-ME.md",
    "docs/customer/GUIA_DE_INSTALACAO.md": "01 - Guia de Instalacao.md",
    "docs/customer/CATALOGO_DOS_LOOKS.md": "02 - Catalogo dos Looks.md",
    "docs/customer/LICENCA_DE_USO.md": "03 - Licenca de Uso.md",
}
FORBIDDEN = re.compile(r"la\s*creme|fjr|private/|reference-private|third-party pack|rascunho", re.IGNORECASE)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", default="cinera-vol-01")
    ap.add_argument("--zip", action="store_true", help="one zip with the whole package")
    ap.add_argument("--split-zips", action="store_true",
                    help="one zip per LUT folder + Previews (for uploading folder by folder)")
    args = ap.parse_args(argv)

    col = COLLECTIONS[args.collection]
    manifest = json.loads((REPO / "exports" / args.collection / "MANIFEST.json").read_text())
    report = json.loads((REPO / "previews/reports/validation_report.json").read_text())
    passed = {r["file"] for r in report["results"] if r["pass"]}

    errors = []
    for rel, meta in manifest["files"].items():
        p = REPO / rel
        if not p.exists():
            errors.append(f"missing {rel} (run build_luts.py)")
        elif sha(p) != meta["sha256"]:
            errors.append(f"checksum mismatch {rel}")
        if rel not in passed:
            errors.append(f"not validated / failed: {rel}")
    if errors:
        sys.exit("package aborted:\n  " + "\n  ".join(errors[:20]))

    name = f"CINERA_VOL_01_v{col['version']}"
    root = REPO / "release" / name
    if root.exists():
        shutil.rmtree(root)
    pkg_manifest = {"collection": col["name"], "version": col["version"], "files": {}}
    for rel, meta in manifest["files"].items():
        src = REPO / rel
        folder = FOLDERS[Path(rel).parent.name]
        dst = root / "LUTs" / folder / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        pkg_manifest["files"][dst.relative_to(root).as_posix()] = {
            k: meta[k] for k in ("sha256", "size", "input", "output", "format", "look", "variant", "look_version")}
    for d in ("contact-sheets", "before-after", "curves"):
        for png in sorted((REPO / "previews" / d).glob("*.png")):
            (root / "Previews").mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, root / "Previews" / png.name)
    for src, dst in CUSTOMER_DOCS.items():
        shutil.copy2(REPO / src, root / dst)
    (root / "MANIFEST.json").write_text(json.dumps(pkg_manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    # one manifest per LUT folder, so each folder can be delivered on its own
    for sub in (root / "LUTs").iterdir():
        part = {"collection": col["name"], "version": col["version"],
                "files": {Path(k).name: v for k, v in pkg_manifest["files"].items() if Path(k).parent.name == sub.name}}
        (sub / "MANIFEST.json").write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # gate 3: no third-party names or private material
    hits = []
    for f in root.rglob("*"):
        if FORBIDDEN.search(f.name):
            hits.append(f"name: {f.relative_to(root)}")
        if f.is_file() and f.suffix.lower() in (".txt", ".md", ".json", ".cube"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            m = FORBIDDEN.search(text)
            if m:
                hits.append(f"{f.relative_to(root)}: '{m.group(0)}'")
    if hits:
        shutil.rmtree(root)
        sys.exit("package aborted — forbidden content:\n  " + "\n  ".join(hits[:20]))

    n_cube = len(list(root.rglob("*.cube")))
    print(f"package: {root.relative_to(REPO)}  ({n_cube} LUTs, previews, docs) — not published")
    if args.zip:
        zp = root.parent / f"{name}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    z.write(f, Path(name) / f.relative_to(root))
        print(f"zip: {zp.relative_to(REPO)}  {zp.stat().st_size / 1e6:.1f} MB")
    if args.split_zips:
        out = root.parent / f"{name}_split"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir()
        parts = {f"LUTs - {sub.name}": sub for sub in sorted((root / "LUTs").iterdir())}
        parts["Previews"] = root / "Previews"
        for title, folder in parts.items():
            zp = out / f"CINERA_VOL_01 - {title}.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for f in sorted(folder.rglob("*")):
                    if f.is_file():
                        z.write(f, Path(folder.name) / f.relative_to(folder))
            print(f"zip: {zp.relative_to(REPO)}  {zp.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
