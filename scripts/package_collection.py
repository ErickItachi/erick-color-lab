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

from erick_color_lab.brand import BRAND, COLLECTIONS  # noqa: E402

FOLDERS = {
    "rec709": "Rec709",
    "sony-slog3": "Sony S-Log3",
    "apple-log": "Apple Log",
    "canon-log3": "Canon Log 3",
    "creative-only": "Creative Only (ACEScct)",
}
DOCS = ["docs/INSTALLATION.md", "docs/COMPATIBILITY.md", "docs/LOOKS.md", "docs/COLOR_SCIENCE.md", "CHANGELOG.md"]
FORBIDDEN = re.compile(r"la\s*creme|fjr|private/|reference-private|third-party pack", re.IGNORECASE)

README = """{name} — {tagline}
{signature}

Versão da coleção: {version}

CONTEÚDO
  LUTs/Rec709                      Rec.709 -> Rec.709 (para footage Rec.709)
  LUTs/Sony S-Log3                 S-Log3 / S-Gamut3.Cine e S-Gamut3 -> Rec.709
  LUTs/Apple Log                   Apple Log / BT.2020 -> Rec.709
  LUTs/Canon Log 3                 Canon Log 3 / Cinema Gamut -> Rec.709
  LUTs/Creative Only (ACEScct)     ACEScct -> ACEScct (somente o look, sem conversão técnica)
  Previews/                        prévias das 15 variações
  Docs/                            instalação, compatibilidade, looks, color science, histórico

LOOKS
  01 SIGNATURE · 02 GOLDEN · 03 OLIVE · 04 BLUE HOUR · 05 ROMANCE
  Variações: SOFT · STANDARD · RICH    Resoluções: 33 e 65 (65 = máxima precisão)

NOME DOS ARQUIVOS
  CINERA_<NN>_<LOOK>_<VARIAÇÃO>_<ENTRADA>_TO_<SAÍDA>_<TAMANHO>.cube

IMPORTANTE
  - LUTs de câmera esperam o clip em Data Levels = Auto/Video (padrão do Resolve e do Premiere).
  - Não combine um LUT "Camera to Rec.709" com outra conversão da mesma câmera.
  - Faça exposição e balanço de branco antes do LUT.
  Detalhes: Docs/INSTALLATION.md e Docs/COMPATIBILITY.md

Integridade: MANIFEST.json traz o SHA-256 de cada arquivo.
(c) Erick Filmes. Uso sujeito a LICENCA.txt.
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", default="cinera-vol-01")
    ap.add_argument("--zip", action="store_true")
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
    (root / "Docs").mkdir(parents=True, exist_ok=True)
    for doc in DOCS:
        shutil.copy2(REPO / doc, root / "Docs" / Path(doc).name)
    (root / "LEIA-ME.txt").write_text(README.format(name=col["name"], tagline=BRAND["tagline"],
                                                    signature=BRAND["signature"], version=col["version"]), encoding="utf-8")
    lic = (REPO / "LICENSE.md").read_text(encoding="utf-8")
    (root / "LICENCA.txt").write_text(lic, encoding="utf-8")
    (root / "MANIFEST.json").write_text(json.dumps(pkg_manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

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


if __name__ == "__main__":
    main()
