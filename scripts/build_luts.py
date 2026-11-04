#!/usr/bin/env python3
"""Bake every CINÉRA export from the look/profile JSON files.

    python scripts/build_luts.py                      # whole collection, 33 + 65
    python scripts/build_luts.py --sizes 33           # only 33^3
    python scripts/build_luts.py --looks 01-signature --profiles slog3_sgamut3cine

Writes the .cube files under exports/<collection>/<profile folder>/ and
exports/<collection>/MANIFEST.json (checksums, inputs, outputs, look
fingerprints). The .cube files are build artifacts (git-ignored); the
manifest is committed so any rebuild can be verified bit-for-bit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

from erick_color_lab.brand import ENGINE_NAME, ENGINE_VERSION  # noqa: E402
from erick_color_lab.collection import enumerate_exports  # noqa: E402
from erick_color_lab.lut_baking.cube import CubeLUT, bake, write_cube  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", default="cinera-vol-01")
    ap.add_argument("--sizes", type=int, nargs="+", default=[33, 65])
    ap.add_argument("--looks", nargs="*", help="look ids (e.g. 01-signature) or tokens")
    ap.add_argument("--profiles", nargs="*", help="profile ids (e.g. slog3_sgamut3cine)")
    args = ap.parse_args(argv)

    exports, _ = enumerate_exports(args.collection, tuple(args.sizes), args.looks, args.profiles, REPO)
    manifest_path = REPO / "exports" / args.collection / "MANIFEST.json"
    manifest = {"files": {}}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    t0 = time.time()
    for i, ex in enumerate(exports, 1):
        table = bake(ex.transform, ex.size)
        sha = write_cube(REPO / ex.relpath, CubeLUT(table, ex.title, ex.header()))
        manifest["files"][ex.relpath] = {
            "sha256": sha,
            "size": ex.size,
            "look": ex.look.look_id,
            "variant": ex.look.variant,
            "look_version": ex.look.version,
            "look_parameters_sha256": ex.look.fingerprint(),
            "profile": ex.profile.id,
            "format": ex.profile.kind,
            "input": ex.profile.label,
            "signal_range": ex.profile.signal_range,
            "output": ex.transform.output_label,
            "rendering": ex.transform.rendering.id if ex.profile.kind != "working_space" else None,
        }
        print(f"[{i:3d}/{len(exports)}] {ex.relpath}")
    manifest.update({
        "collection": exports[0].collection["name"] if exports else args.collection,
        "collection_version": exports[0].collection["version"] if exports else None,
        "engine": f"{ENGINE_NAME} {ENGINE_VERSION}",
        "file_count": len(manifest["files"]),
    })
    manifest["files"] = dict(sorted(manifest["files"].items()))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"built {len(exports)} files in {time.time() - t0:.1f}s -> {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
