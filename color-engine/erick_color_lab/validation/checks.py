"""Technical validation of baked LUTs against the analytic pipeline.

Every exported .cube is *re-imported from disk* and compared with the exact
transform it was baked from. Tolerances are fixed in ``TOLERANCES`` (decided
before the first build and documented in docs/COLOR_SCIENCE.md) — a check
reports FAIL rather than silently loosening them.

Checks
------
integrity     strict parse, size, row count, finite, values within [0, 1]
precision     error at lattice nodes (file quantisation, 6 decimals)
interpolation CIEDE2000 between tetrahedral / trilinear LUT lookup and the
              exact transform at random + mid-cell points (perceived error)
continuity    neutral-axis response: monotone luminance, no reversals
banding       scene-built ramps (neutral, skin, sky chromaticities, -9..+7
              stops): largest output step per input 10-bit code, reversals
clipping      fraction of lattice outputs at 0 or 1, separately for the
              "picture" region of the input domain
gamut         fraction of lattice points out of [0, 1] *before* the final
              clip (after gamut compression)
consistency   skin-proxy hue stability across -2 / 0 / +2 EV (Oklab hue)
"""

from __future__ import annotations

import colour
import numpy as np

from ..interpolation.lut3d import tetrahedral, trilinear
from ..lut_baking.cube import read_cube
from ..transforms import colorspaces as cs
from ..transforms.transfer import acescct_decode, bt1886_eotf

TOLERANCES = {
    "node_max_abs": 1e-6,               # 6-decimal quantisation is 5e-7
    "de2000_mean": {33: 0.50, 65: 0.20},
    "de2000_p99": {33: 2.00, 65: 1.00},
    "neutral_reversals": 0,
    "banding_max_step_10bit": 6,        # largest jump between adjacent 10-bit input codes
    "banding_reversals": 0,
    "skin_hue_spread_deg": 8.0,         # across -2/0/+2 EV, per skin-proxy patch
}


def _display_xyz(rgb_display, output_kind, rendering):
    if output_kind == "acescct":
        rgb_display = rendering.forward(acescct_decode(rgb_display))
    lin = bt1886_eotf(np.clip(rgb_display, 0.0, 1.0))
    return colour.RGB_to_XYZ(lin, colour.RGB_COLOURSPACES["ITU-R BT.709"], apply_cctf_decoding=False)


def delta_e(a, b, output_kind, rendering):
    xa = _display_xyz(a, output_kind, rendering)
    xb = _display_xyz(b, output_kind, rendering)
    wp = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
    return colour.delta_E(colour.XYZ_to_Lab(xa, wp), colour.XYZ_to_Lab(xb, wp), method="CIE 2000")


def _luma_display(rgb, output_kind, rendering):
    if output_kind == "acescct":
        rgb = rendering.forward(acescct_decode(rgb))
    return bt1886_eotf(np.clip(rgb, 0, 1)) @ cs.luminance_weights("rec709")


def validate_lut(path, transform, rendering, seed: int = 7) -> dict:
    """Run every check for one exported file. ``transform`` is the analytic
    pipeline (signal -> output) the file was baked from."""
    res = {"file": str(path), "checks": {}}
    chk = res["checks"]
    out_kind = "acescct" if transform.profile.kind == "working_space" else "rec709"

    # --- integrity ---------------------------------------------------------
    lut = read_cube(path)
    t = lut.table
    n = lut.size
    chk["integrity"] = {
        "size": n,
        "rows": int(t.size // 3),
        "finite": bool(np.all(np.isfinite(t))),
        "in_unit_range": bool(t.min() >= 0.0 and t.max() <= 1.0),
        "domain": [list(lut.domain_min), list(lut.domain_max)],
        "pass": bool(np.all(np.isfinite(t)) and t.min() >= 0 and t.max() <= 1
                     and lut.domain_min == (0.0, 0.0, 0.0) and lut.domain_max == (1.0, 1.0, 1.0)),
    }

    # --- precision at nodes -------------------------------------------------
    g = np.linspace(0, 1, n)
    b_, g_, r_ = np.meshgrid(g, g, g, indexing="ij")
    nodes = np.stack([r_.ravel(), g_.ravel(), b_.ravel()], -1)
    exact_nodes = np.clip(transform(nodes), 0, 1)
    node_err = float(np.abs(exact_nodes - t.reshape(-1, 3)).max())
    chk["precision"] = {"node_max_abs": node_err, "tolerance": TOLERANCES["node_max_abs"],
                        "pass": node_err <= TOLERANCES["node_max_abs"]}

    # --- interpolation accuracy ----------------------------------------------
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 1, (20000, 3))
    mids = (np.floor(rng.uniform(0, n - 1, (5000, 3))) + 0.5) / (n - 1)  # cell centres: worst case
    pts = np.concatenate([pts, mids])
    exact = np.clip(transform(pts), 0, 1)
    interp = {}
    for name, fn in (("tetrahedral", tetrahedral), ("trilinear", trilinear)):
        de = delta_e(fn(t, pts), exact, out_kind, rendering)
        interp[name] = {"de2000_mean": float(de.mean()), "de2000_p99": float(np.quantile(de, 0.99)),
                        "de2000_max": float(de.max())}
    tol_m, tol_p = TOLERANCES["de2000_mean"].get(n, 0.5), TOLERANCES["de2000_p99"].get(n, 2.0)
    tet = interp["tetrahedral"]
    chk["interpolation"] = {**interp, "tolerance": {"mean": tol_m, "p99": tol_p},
                            "pass": tet["de2000_mean"] <= tol_m and tet["de2000_p99"] <= tol_p}

    # --- neutral continuity & banding -----------------------------------------
    # Ramps are built in *scene* space (a fixed chromaticity swept from -9 to
    # +7 stops) and encoded with the profile, so every sample is a physically
    # meaningful colour. Banding = largest local gain in output 10-bit codes per
    # input 10-bit code; reversal = output decreasing while input increases.
    from ..transforms.colorspaces import convert as _conv

    stops = np.linspace(-9.0, 7.0, 4096)
    directions = {"neutral": (1.0, 1.0, 1.0), "skin": (1.0, 0.72, 0.56), "sky": (0.55, 0.75, 1.0)}
    band = {}
    worst_step, worst_rev = 0.0, 0
    for name, d in directions.items():
        c = _conv(np.asarray(d, dtype=float), "rec709", "ap1")
        c = c / float(c @ cs.luminance_weights("ap1"))
        scene = 0.18 * 2.0 ** stops[:, None] * c
        if transform.profile.kind == "display_rec709":
            sig = rendering.forward(scene, source="rec709")
        else:
            sig = transform.profile.from_scene_ap1(scene)
        keep = np.all((sig >= 0.0) & (sig <= 1.0), axis=1)
        sig = sig[keep]
        y = tetrahedral(t, sig)
        lum = _luma_display(y, out_kind, rendering)
        enc = np.clip(lum, 0, 1) ** (1 / 2.4) * 1023.0
        d_in = np.max(np.abs(np.diff(sig, axis=0)), axis=1) * 1023.0
        d_out = np.diff(enc)
        ok = d_in > 1e-9
        gain = np.abs(d_out[ok]) / d_in[ok]
        rev = int(np.sum(d_out[ok] < -0.05 * np.maximum(d_in[ok], 1.0)))
        mx = float(gain.max()) if gain.size else 0.0
        band[name] = {"max_step_10bit": mx, "reversals": rev}
        worst_step, worst_rev = max(worst_step, mx), max(worst_rev, rev)
    chk["continuity"] = {"neutral_reversals": band["neutral"]["reversals"],
                         "pass": band["neutral"]["reversals"] <= TOLERANCES["neutral_reversals"]}
    chk["banding"] = {**band, "tolerance_max_step_10bit": TOLERANCES["banding_max_step_10bit"],
                      "pass": worst_step <= TOLERANCES["banding_max_step_10bit"] and worst_rev <= TOLERANCES["banding_reversals"]}

    # --- clipping -------------------------------------------------------------
    flat = t.reshape(-1, 3)
    lo = np.any(flat <= 0.0, axis=1)
    hi = np.any(flat >= 1.0, axis=1)
    picture = np.all((nodes >= 0.1) & (nodes <= 0.9), axis=1)
    chk["clipping"] = {
        "nodes_any_channel_at_0": float(lo.mean()),
        "nodes_any_channel_at_1": float(hi.mean()),
        "picture_region_at_0": float(lo[picture].mean()),
        "picture_region_at_1": float(hi[picture].mean()),
        "pass": True,  # informative: clipping of extreme inputs is expected; see report
    }

    # --- gamut (pre-clip) -------------------------------------------------------
    st = transform.stats(nodes)
    chk["gamut"] = {**st, "pass": True}

    # --- skin consistency -------------------------------------------------------
    # Hue is only meaningful with enough chroma: patches whose Oklab chroma is
    # below 0.02 at any exposure are excluded (reported as n_patches).
    from ..imaging.synthetic import skin_patches

    skin = skin_patches()  # 3 EV x 9 patches
    if transform.profile.kind == "display_rec709":
        sig = rendering.forward(skin, source="rec709")
    elif transform.profile.kind == "working_space":
        sig = transform.profile.from_scene_ap1(skin)
    else:
        sig = transform.profile.from_scene_ap1(skin)
    sig = np.clip(sig, 0, 1)

    def hue_spread(out):
        if out_kind == "acescct":
            out = rendering.forward(acescct_decode(out))
        _, C, h = cs.oklab_to_lch(cs.rec709_linear_to_oklab(bt1886_eotf(np.clip(out, 0, 1))))
        C, h = C.reshape(3, 9), h.reshape(3, 9)
        valid = C.min(axis=0) >= 0.02
        d = np.abs((h - h[1:2] + 180) % 360 - 180).max(axis=0)[valid]
        return (float(d.max()) if d.size else 0.0), int(valid.sum()), float(np.mean(h[1][valid])) if valid.any() else 0.0

    sp_lut, n_valid, mean_h = hue_spread(tetrahedral(t, sig))
    sp_exact, _, _ = hue_spread(transform(sig))
    chk["skin_consistency"] = {"max_hue_spread_deg": sp_lut, "exact_pipeline_spread_deg": sp_exact,
                               "n_patches": n_valid, "mean_hue_deg": mean_h,
                               "tolerance": TOLERANCES["skin_hue_spread_deg"],
                               "pass": sp_lut <= TOLERANCES["skin_hue_spread_deg"]}

    res["pass"] = all(c["pass"] for c in chk.values())
    return res
