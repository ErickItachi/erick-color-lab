#!/usr/bin/env python3
"""Re-import every exported .cube and validate it against the analytic pipeline.

    python scripts/validate_luts.py                 # everything in the manifest
    python scripts/validate_luts.py --sizes 33 --looks 01-signature

Also verifies each file's SHA-256 against exports/<collection>/MANIFEST.json.
Writes previews/reports/validation_report.json and validation_report.md.
Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

from erick_color_lab.brand import ENGINE_NAME, ENGINE_VERSION  # noqa: E402
from erick_color_lab.collection import enumerate_exports  # noqa: E402
from erick_color_lab.validation.checks import TOLERANCES, validate_lut  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", default="cinera-vol-01")
    ap.add_argument("--sizes", type=int, nargs="+", default=[33, 65])
    ap.add_argument("--looks", nargs="*")
    ap.add_argument("--profiles", nargs="*")
    ap.add_argument("--report", default="previews/reports/validation_report")
    args = ap.parse_args(argv)

    manifest = json.loads((REPO / "exports" / args.collection / "MANIFEST.json").read_text())
    exports, rendering = enumerate_exports(args.collection, tuple(args.sizes), args.looks, args.profiles, REPO)
    results, t0 = [], time.time()
    for i, ex in enumerate(exports, 1):
        path = REPO / ex.relpath
        if not path.exists():
            results.append({"file": ex.relpath, "pass": False, "error": "missing (run build_luts.py)"})
            continue
        r = validate_lut(path, ex.transform, rendering)
        r["file"] = ex.relpath
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = manifest["files"].get(ex.relpath, {}).get("sha256")
        r["checks"]["manifest"] = {"sha256": sha, "expected": expected, "pass": sha == expected}
        r["pass"] = all(c["pass"] for c in r["checks"].values())
        results.append(r)
        c = r["checks"]
        tet = c["interpolation"]["tetrahedral"]
        print(f"[{i:3d}/{len(exports)}] {'PASS' if r['pass'] else 'FAIL'} {ex.filename}  "
              f"dE00 mean {tet['de2000_mean']:.3f} p99 {tet['de2000_p99']:.3f} max {tet['de2000_max']:.2f}  "
              f"band {max(c['banding'][k]['max_step_10bit'] for k in ('neutral', 'skin', 'sky')):.2f}  "
              f"skin {c['skin_consistency']['max_hue_spread_deg']:.1f}deg")

    n_pass = sum(r["pass"] for r in results)
    summary = {"engine": f"{ENGINE_NAME} {ENGINE_VERSION}", "collection": args.collection,
               "files": len(results), "passed": n_pass, "failed": len(results) - n_pass,
               "tolerances": {k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in TOLERANCES.items()},
               "seconds": round(time.time() - t0, 1)}
    out = REPO / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps({"summary": summary, "results": results}, indent=1) + "\n")
    out.with_suffix(".md").write_text(markdown(summary, results), encoding="utf-8")
    print(f"{n_pass}/{len(results)} passed -> {out.with_suffix('.md').relative_to(REPO)}")
    return 0 if n_pass == len(results) else 1


def markdown(summary, results) -> str:
    L = ["# CINÉRA VOL. 01 — LUT validation report", "",
         f"Engine: {summary['engine']} · files: {summary['files']} · **passed: {summary['passed']}** · failed: {summary['failed']}", "",
         "Every file below was re-imported from disk with the strict .cube reader and compared with the analytic "
         "pipeline it was baked from. ΔE = CIEDE2000 on the Rec.709 display output (Creative-Only files are "
         "evaluated through the CINÉRA Neutral Rendering). Tolerances: see `color-engine/erick_color_lab/validation/checks.py`.", "",
         "| File | Result | node err | ΔE00 mean / p99 / max (tetra) | ΔE00 p99 (trilinear) | banding max step (10-bit) | out-of-range before clip | skin hue spread |",
         "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "checks" not in r:
            L.append(f"| `{Path(r['file']).name}` | **FAIL** ({r.get('error')}) | | | | | | |")
            continue
        c = r["checks"]
        tet, tri = c["interpolation"]["tetrahedral"], c["interpolation"]["trilinear"]
        band = max(c["banding"][k]["max_step_10bit"] for k in ("neutral", "skin", "sky"))
        L.append(f"| `{Path(r['file']).name}` | {'PASS' if r['pass'] else '**FAIL**'} | {c['precision']['node_max_abs']:.1e} | "
                 f"{tet['de2000_mean']:.3f} / {tet['de2000_p99']:.3f} / {tet['de2000_max']:.2f} | {tri['de2000_p99']:.3f} | "
                 f"{band:.2f} | {100 * c['gamut']['out_of_range_fraction']:.1f}% | {c['skin_consistency']['max_hue_spread_deg']:.1f}° |")
    failing = [r for r in results if not r["pass"]]
    if failing:
        L += ["", "## Failures", ""]
        for r in failing:
            bad = [k for k, v in r.get("checks", {}).items() if not v.get("pass", False)]
            L.append(f"- `{Path(r['file']).name}`: {', '.join(bad) or r.get('error')}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
