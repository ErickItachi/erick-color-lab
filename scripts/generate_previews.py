#!/usr/bin/env python3
"""Generate CINÉRA previews from the *exported* .cube files.

Every image is produced by re-importing the baked LUT from disk and applying
it with tetrahedral interpolation to synthetic, reproducible test scenes
(erick_color_lab.imaging.synthetic). Nothing here is a mock-up.

    python scripts/build_luts.py          # first, if exports are missing
    python scripts/generate_previews.py   # synthetic scenes -> previews/
    python scripts/generate_previews.py --media test-media/   # your own stills (local only)

Outputs
  previews/before-after/    log signal | neutral conversion | look  (per look)
  previews/contact-sheets/  Soft / Standard / Rich per look, collection overview,
                            cross-camera consistency sheet
  previews/curves/          tone-response curves and luminance histograms
  previews/reports/         clipping_report.{json,md}
  previews/index.html       local viewer (open in a browser)

PNG files hold Rec.709 / BT.1886 display values. Browsers interpret untagged
PNG as sRGB, so mid-tones look slightly different from a calibrated BT.1886
monitor; compare looks with each other, not with a reference display.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

from erick_color_lab.brand import BRAND, COLLECTIONS  # noqa: E402
from erick_color_lab.collection import enumerate_exports  # noqa: E402
from erick_color_lab.creative.look import Look  # noqa: E402
from erick_color_lab.imaging.synthetic import SCENES  # noqa: E402
from erick_color_lab.interpolation.lut3d import tetrahedral  # noqa: E402
from erick_color_lab.lut_baking.cube import read_cube  # noqa: E402
from erick_color_lab.pipeline import Transform  # noqa: E402
from erick_color_lab.transforms import colorspaces as cs  # noqa: E402
from erick_color_lab.transforms.transfer import acescct_decode, bt1886_eotf  # noqa: E402

OUT = REPO / "previews"
FONT_PATH = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
FONT_BOLD = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans-Bold.ttf"
REF_PROFILE = "slog3_sgamut3cine"
REF_SIZE = 65
SHOW_SCENES = ["colorchecker", "skin_ramp", "golden_hour_4000k", "blue_hour_10000k",
               "tungsten_3200k", "low_light", "exposure_bracket", "highlights", "hue_sweep"]
SCENE_LABEL = {
    "colorchecker": "ColorChecker D65", "skin_ramp": "Skin proxies -2/0/+2 EV",
    "golden_hour_4000k": "Warm light 4000 K (sim.)", "blue_hour_10000k": "Blue hour 10000 K (sim.)",
    "tungsten_3200k": "Tungsten 3200 K (sim.)", "low_light": "Night / practicals",
    "exposure_bracket": "Exposure -4..+4 EV", "highlights": "Highlights to +7 stops",
    "hue_sweep": "Hue sweep", "neutral_ramp": "Neutral ramp",
}
# validated categorical slots (dataviz reference palette, light surface)
SERIES = {"soft": "#2a78d6", "standard": "#eb6834", "rich": "#1baf7a"}
NEUTRAL_GREY = "#8a8986"
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
VARIANTS = ["soft", "standard", "rich"]


# ---------------------------------------------------------------------------
# image helpers
def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_PATH), size)


def to_img(display: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(display, 0, 1) * 255 + 0.5).astype(np.uint8))


def captioned(img: Image.Image, text: str, size=13, pad=6, bg=(18, 18, 17), fg=(235, 233, 228)) -> Image.Image:
    f = font(size)
    h = size + 2 * pad
    out = Image.new("RGB", (img.width, img.height + h), bg)
    out.paste(img, (0, h))
    ImageDraw.Draw(out).text((pad, pad - 1), text, font=f, fill=fg)
    return out


def hstack(imgs, gap=6, bg=(18, 18, 17)):
    h = max(i.height for i in imgs)
    out = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), h), bg)
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def vstack(imgs, gap=6, bg=(18, 18, 17)):
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs) + gap * (len(imgs) - 1)), bg)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def header(img: Image.Image, title: str, subtitle: str) -> Image.Image:
    h = 64
    out = Image.new("RGB", (max(img.width, 900), img.height + h), (10, 10, 10))
    d = ImageDraw.Draw(out)
    d.text((14, 10), title, font=font(20, bold=True), fill=(240, 239, 236))
    d.text((14, 38), subtitle, font=font(12), fill=(195, 194, 183))
    out.paste(img, (0, h))
    return out


def fit(img: Image.Image, width: int) -> Image.Image:
    if img.width == width:
        return img
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


# ---------------------------------------------------------------------------
# LUT application
class Applier:
    def __init__(self, rendering):
        self.rendering = rendering
        self.cache = {}

    def table(self, relpath):
        if relpath not in self.cache:
            self.cache[relpath] = read_cube(REPO / relpath).table
        return self.cache[relpath]

    def signal(self, profile, scene):
        flat = scene.reshape(-1, 3)
        if profile.kind == "display_rec709":
            sig = self.rendering.forward(flat, source="rec709")
        else:
            sig = profile.from_scene_ap1(flat)
        return np.clip(sig, 0, 1).reshape(scene.shape)

    def apply(self, export, scene):
        sig = self.signal(export.profile, scene)
        out = tetrahedral(self.table(export.relpath), sig.reshape(-1, 3))
        if export.profile.kind == "working_space":
            out = self.rendering.forward(acescct_decode(out))
        return out.reshape(scene.shape)

    def neutral(self, profile, scene):
        sig = self.signal(profile, scene).reshape(-1, 3)
        out = Transform(Look.neutral(), profile, self.rendering)(sig)
        if profile.kind == "working_space":
            out = self.rendering.forward(acescct_decode(out))
        return out.reshape(scene.shape)


def find(exports, look_id, variant, profile, size):
    for e in exports:
        if e.look.look_id == look_id and e.look.variant == variant and e.profile.id == profile and e.size == size:
            return e
    raise KeyError((look_id, variant, profile, size))


# ---------------------------------------------------------------------------
def before_after(exports, ap, scenes, look_ids, names):
    paths = []
    for lid in look_ids:
        ex = find(exports, lid, "standard", REF_PROFILE, REF_SIZE)
        rows = []
        for sk in SHOW_SCENES[:6]:
            sc = scenes[sk]
            log = ap.signal(ex.profile, sc)
            cells = [captioned(to_img(log), "S-Log3 signal (as recorded)"),
                     captioned(to_img(ap.neutral(ex.profile, sc)), "Neutral conversion only"),
                     captioned(to_img(ap.apply(ex, sc)), f"{names[lid]} Standard")]
            rows.append(captioned(hstack(cells), SCENE_LABEL[sk], size=12, bg=(30, 30, 28)))
        img = header(vstack(rows), f"{BRAND['product_line']} {ex.look.number} {names[lid].upper()} — before / after",
                     f"Exported LUT {ex.filename} applied with tetrahedral interpolation to synthetic test scenes")
        p = OUT / "before-after" / f"CINERA_{ex.look.number}_{names[lid].upper().replace(' ', '')}_before_after.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p, optimize=True)
        paths.append(p)
    return paths


def variant_sheets(exports, ap, scenes, look_ids, names):
    paths = []
    for lid in look_ids:
        rows = []
        for sk in SHOW_SCENES:
            sc = scenes[sk]
            ex0 = find(exports, lid, "standard", REF_PROFILE, REF_SIZE)
            cells = [captioned(to_img(ap.neutral(ex0.profile, sc)), "Neutral")]
            for v in VARIANTS:
                cells.append(captioned(to_img(ap.apply(find(exports, lid, v, REF_PROFILE, REF_SIZE), sc)), v.upper()))
            rows.append(captioned(hstack(cells), SCENE_LABEL[sk], size=12, bg=(30, 30, 28)))
        num = find(exports, lid, "standard", REF_PROFILE, REF_SIZE).look.number
        img = header(vstack(rows), f"{BRAND['product_line']} {num} {names[lid].upper()} — Soft / Standard / Rich",
                     "S-Log3 / S-Gamut3.Cine to Rec.709, 65^3, exported files. Synthetic scenes (see docs/LOOKS.md).")
        p = OUT / "contact-sheets" / f"CINERA_{num}_{names[lid].upper().replace(' ', '')}_variants.png"
        img.save(p, optimize=True)
        paths.append(p)
    return paths


def collection_sheet(exports, ap, scenes, look_ids, names):
    keys = ["colorchecker", "skin_ramp", "golden_hour_4000k", "blue_hour_10000k", "low_light"]
    ex0 = find(exports, look_ids[0], "standard", REF_PROFILE, REF_SIZE)
    rows = [captioned(hstack([fit(to_img(ap.neutral(ex0.profile, scenes[k])), 230) for k in keys]), "00 NEUTRAL (reference)", 12)]
    for lid in look_ids:
        for v in VARIANTS:
            ex = find(exports, lid, v, REF_PROFILE, REF_SIZE)
            rows.append(captioned(hstack([fit(to_img(ap.apply(ex, scenes[k])), 230) for k in keys]),
                                  f"{ex.look.number} {names[lid].upper()} — {v.upper()}", 12))
    img = header(vstack(rows, gap=4), f"{COLLECTIONS['cinera-vol-01']['name']} — {BRAND['tagline']}",
                 "15 variants, S-Log3 / S-Gamut3.Cine -> Rec.709 (65^3 exports). Columns: "
                 + " · ".join(SCENE_LABEL[k] for k in keys))
    p = OUT / "contact-sheets" / "CINERA_VOL01_collection_overview.png"
    img.save(p, optimize=True)
    return p


def profile_sheet(exports, ap, scenes, lid, names):
    """Same scene captured by every supported input -> same look."""
    from erick_color_lab.validation.checks import delta_e

    keys = ["colorchecker", "skin_ramp", "golden_hour_4000k"]
    ref = find(exports, lid, "standard", REF_PROFILE, REF_SIZE)
    ref_out = {k: ap.apply(ref, scenes[k]) for k in keys}
    profs = []
    for e in exports:
        if e.look.look_id == lid and e.look.variant == "standard" and e.size == REF_SIZE and e.profile.id not in [p.profile.id for p in profs]:
            profs.append(e)
    rows, stats = [], {}
    for e in profs:
        outs = [ap.apply(e, scenes[k]) for k in keys]
        de = np.concatenate([delta_e(o.reshape(-1, 3), ref_out[k].reshape(-1, 3), "rec709", ap.rendering) for o, k in zip(outs, keys)])
        stats[e.profile.label] = {"mean_de2000_vs_slog3cine": float(de.mean()), "p95": float(np.quantile(de, 0.95))}
        rows.append(captioned(hstack([fit(to_img(o), 300) for o in outs]),
                              f"{e.profile.label}  ->  {e.filename}   (ΔE00 vs S-Log3/S-Gamut3.Cine: mean {de.mean():.2f})", 12))
    img = header(vstack(rows, gap=4), f"{BRAND['product_line']} {ref.look.number} {names[lid].upper()} STANDARD — every input profile",
                 "The same synthetic scene encoded as each camera's signal, through each profile's exported LUT. "
                 "Differences come from gamut compression of each camera gamut and from the Rec.709 inverse path.")
    p = OUT / "contact-sheets" / f"CINERA_{ref.look.number}_{names[lid].upper().replace(' ', '')}_STANDARD_all_profiles.png"
    img.save(p, optimize=True)
    return p, stats


# ---------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c9c8c3")
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color="#e8e7e3", linewidth=0.6)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)


def end_labels(ax, x, items, min_gap=0.055):
    """Direct labels at line ends, dodged vertically so they never collide."""
    items = sorted(items, key=lambda t: t[1])
    ys = []
    for _, y in items:
        ys.append(max(y, ys[-1] + min_gap) if ys else y)
    shift = max(0.0, ys[-1] - 1.02) if ys else 0.0
    for (name, _), y in zip(items, ys):
        ax.annotate(name, (x, y - shift), xytext=(6, 0), textcoords="offset points",
                    fontsize=8, color=INK2, va="center", annotation_clip=False)


def curves_and_histograms(exports, ap, scenes, look_ids, names):
    paths = []
    stops = np.linspace(-8, 7, 600)
    neutral_scene = (0.18 * 2.0 ** stops)[:, None] * np.ones(3)
    combo = np.concatenate([scenes[k].reshape(-1, 3) for k in SHOW_SCENES])
    for lid in look_ids:
        ex = {v: find(exports, lid, v, REF_PROFILE, REF_SIZE) for v in VARIANTS}
        prof = ex["standard"].profile
        fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0), dpi=110, facecolor=SURFACE)
        # (a) neutral tone response
        ax = axes[0]
        _style(ax)
        sig = ap.signal(prof, neutral_scene[None])[0]
        yN = Transform(Look.neutral(), prof, ap.rendering)(sig) @ cs.luminance_weights("rec709")
        ax.plot(stops, yN, color=NEUTRAL_GREY, lw=1.6, ls=(0, (4, 3)), label="Neutral")
        ends = []
        for v in VARIANTS:
            out = tetrahedral(ap.table(ex[v].relpath), sig)
            y = bt1886_eotf(out) @ cs.luminance_weights("rec709")
            y = y ** (1 / 2.4)
            ax.plot(stops, y, color=SERIES[v], lw=2, label=v.capitalize())
            ends.append((v.capitalize(), float(y[-1])))
        end_labels(ax, stops[-1], ends)
        ax.set_xlim(stops[0], stops[-1] + 1.6)
        ax.set_xlabel("scene exposure (stops relative to 18 % grey)")
        ax.set_ylabel("display luma (BT.1886 encoded)")
        ax.set_title("Tone response (neutral input)", fontsize=10, color=INK, loc="left")
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
        # (b) per-channel response of Standard on a neutral input
        ax = axes[1]
        _style(ax)
        out = tetrahedral(ap.table(ex["standard"].relpath), sig)
        ends = []
        for i, (nm, col) in enumerate((("R", "#d03b3b"), ("G", "#0ca30c"), ("B", "#2a78d6"))):
            ax.plot(stops, out[:, i], color=col, lw=1.6, label=nm)
            ends.append((nm, float(out[-1, i])))
        end_labels(ax, stops[-1], ends)
        ax.set_xlim(stops[0], stops[-1] + 1.0)
        ax.set_xlabel("scene exposure (stops relative to 18 % grey)")
        ax.set_ylabel("display value (BT.1886 encoded)")
        ax.set_title("Standard — channel balance on a neutral ramp", fontsize=10, color=INK, loc="left")
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
        # (c) luminance histograms over all synthetic scenes
        ax = axes[2]
        _style(ax)
        sigc = ap.signal(prof, combo[None])[0]
        bins = np.linspace(0, 1, 65)
        yN = Transform(Look.neutral(), prof, ap.rendering)(sigc) @ cs.luminance_weights("rec709")
        h, _ = np.histogram(yN, bins)
        ax.step(bins[:-1], h / h.sum(), where="post", color=NEUTRAL_GREY, lw=1.4, ls=(0, (4, 3)), label="Neutral")
        for v in VARIANTS:
            y = bt1886_eotf(tetrahedral(ap.table(ex[v].relpath), sigc)) @ cs.luminance_weights("rec709")
            h, _ = np.histogram(y ** (1 / 2.4), bins)
            ax.step(bins[:-1], h / h.sum(), where="post", color=SERIES[v], lw=1.6, label=v.capitalize())
        ax.set_xlabel("display luma (BT.1886 encoded)")
        ax.set_ylabel("fraction of pixels")
        ax.set_title("Luma histogram — all synthetic scenes", fontsize=10, color=INK, loc="left")
        ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
        num = ex["standard"].look.number
        fig.suptitle(f"CINÉRA {num} {names[lid].upper()} — measured from exported 65³ LUTs (S-Log3 / S-Gamut3.Cine)",
                     x=0.01, ha="left", fontsize=11, color=INK, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        p = OUT / "curves" / f"CINERA_{num}_{names[lid].upper().replace(' ', '')}_curves.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, facecolor=SURFACE)
        plt.close(fig)
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
def clipping_report(exports, ap, scenes):
    combo = np.concatenate([scenes[k].reshape(-1, 3) for k in SHOW_SCENES])[None]
    rows = []
    neutral_cache = {}
    for e in exports:
        if e.size != REF_SIZE:
            continue
        out = ap.apply(e, combo)[0]
        if e.profile.id not in neutral_cache:
            n = ap.neutral(e.profile, combo)[0]
            neutral_cache[e.profile.id] = (float(np.mean(np.any(n >= 0.999, -1))), float(np.mean(np.any(n <= 0.001, -1))))
        nw, nb = neutral_cache[e.profile.id]
        rows.append({"file": e.filename, "profile": e.profile.id, "look": e.look.look_id, "variant": e.look.variant,
                     "white_clip_pct": 100 * float(np.mean(np.any(out >= 0.999, -1))),
                     "black_clip_pct": 100 * float(np.mean(np.any(out <= 0.001, -1))),
                     "neutral_white_clip_pct": 100 * nw, "neutral_black_clip_pct": 100 * nb})
    (OUT / "reports").mkdir(parents=True, exist_ok=True)
    (OUT / "reports/clipping_report.json").write_text(json.dumps(rows, indent=1) + "\n")
    L = ["# CINÉRA VOL. 01 — clipping report (synthetic scenes)", "",
         f"Pixels of all synthetic test scenes ({', '.join(SHOW_SCENES)}) encoded as each profile's signal and "
         "passed through the exported 65³ LUT. *White clip* = any channel ≥ 0.999, *black clip* = any channel ≤ 0.001. "
         "The neutral column is the CINÉRA Neutral Rendering alone (technical conversion, no look) for the same profile. "
         "The scenes intentionally contain +4 EV exposures, +7-stop highlights and saturated practical lights, so some "
         "clipping is expected for every look.", "",
         "| File | white clip % | black clip % | neutral white % | neutral black % |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['file']}` | {r['white_clip_pct']:.2f} | {r['black_clip_pct']:.2f} | "
                 f"{r['neutral_white_clip_pct']:.2f} | {r['neutral_black_clip_pct']:.2f} |")
    (OUT / "reports/clipping_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return rows


# ---------------------------------------------------------------------------
def index_html(sections, validation, clipping, profile_stats):
    def img(p):
        rel = p.relative_to(OUT).as_posix()
        return f'<a href="{rel}"><img loading="lazy" src="{rel}" alt="{html.escape(p.stem)}"></a>'

    s = validation["summary"] if validation else {}
    vrows = ""
    if validation:
        for r in validation["results"]:
            c = r["checks"]
            t = c["interpolation"]["tetrahedral"]
            vrows += (f"<tr><td>{html.escape(Path(r['file']).name)}</td><td class='{'ok' if r['pass'] else 'bad'}'>"
                      f"{'PASS' if r['pass'] else 'FAIL'}</td><td>{t['de2000_mean']:.3f}</td><td>{t['de2000_p99']:.3f}</td>"
                      f"<td>{c['skin_consistency']['exact_pipeline_spread_deg']:.1f}°</td>"
                      f"<td>{c['skin_consistency']['lut_vs_pipeline_de2000_max']:.2f}</td></tr>")
    crow = "".join(f"<tr><td>{html.escape(r['file'])}</td><td>{r['white_clip_pct']:.2f}</td><td>{r['black_clip_pct']:.2f}</td>"
                   f"<td>{r['neutral_white_clip_pct']:.2f}</td><td>{r['neutral_black_clip_pct']:.2f}</td></tr>" for r in clipping)
    prow = "".join(f"<tr><td>{html.escape(k)}</td><td>{v['mean_de2000_vs_slog3cine']:.2f}</td><td>{v['p95']:.2f}</td></tr>"
                   for k, v in profile_stats.items())
    body = "".join(f"<section><h2>{html.escape(t)}</h2><div class='grid'>{''.join(img(p) for p in ps)}</div></section>"
                   for t, ps in sections)
    page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CINÉRA Previews</title>
<style>
:root{{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e3e2de;--ok:#0a7d0a;--bad:#b42f2f}}
@media (prefers-color-scheme: dark){{:root{{--bg:#121211;--ink:#f0efec;--ink2:#c3c2b7;--line:#2c2c2a;--ok:#4fc94f;--bad:#e66767}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
header,main{{max-width:1200px;margin:0 auto;padding:16px}}
h1{{font-size:28px;letter-spacing:.18em;margin:8px 0 0}} .tag{{color:var(--ink2);margin:0 0 4px}}
h2{{font-size:18px;margin:28px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px}}
.grid img{{width:100%;height:auto;display:block;border-radius:4px;border:1px solid var(--line)}}
.note{{color:var(--ink2);font-size:13px}}
.tablewrap{{overflow-x:auto;max-height:480px;overflow-y:auto;border:1px solid var(--line);border-radius:4px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}}
th,td{{padding:4px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
th{{position:sticky;top:0;background:var(--bg)}} .ok{{color:var(--ok);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
</style></head><body>
<header><h1>CINÉRA</h1><p class="tag">{BRAND['tagline']} — {BRAND['signature']} · VOL. 01</p>
<p class="note">Local preview page (not the ERICK COLOR LAB app). Every image was rendered by applying the exported .cube files
to synthetic, reproducible test scenes. PNG values are Rec.709/BT.1886; browsers show them as sRGB, so compare looks with each other.
No photographic footage was used in these previews.</p></header>
<main>{body}
<section><h2>Cross-camera consistency (Signature Standard)</h2><div class="tablewrap"><table>
<tr><th>Input profile</th><th>mean ΔE00 vs S-Log3/S-Gamut3.Cine</th><th>p95</th></tr>{prow}</table></div></section>
<section><h2>Validation — {s.get('passed', '?')}/{s.get('files', '?')} files passed</h2>
<p class="note">Full report: reports/validation_report.md</p><div class="tablewrap"><table>
<tr><th>File</th><th>Result</th><th>ΔE00 mean</th><th>ΔE00 p99</th><th>skin hue spread</th><th>skin ΔE00 max</th></tr>{vrows}</table></div></section>
<section><h2>Clipping (synthetic scenes, 65³)</h2><div class="tablewrap"><table>
<tr><th>File</th><th>white %</th><th>black %</th><th>neutral white %</th><th>neutral black %</th></tr>{crow}</table></div></section>
</main></body></html>
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")


# ---------------------------------------------------------------------------
def media_mode(folder: Path, exports, ap, names, look_ids):
    """Apply the Rec.709 LUTs (standard variants) to the user's own stills.
    Images are treated as Rec.709/BT.1886 display-referred. Output stays in
    <folder>/_renders/ (git-ignored)."""
    outdir = folder / "_renders"
    outdir.mkdir(exist_ok=True)
    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff")]
    for f in files:
        im = Image.open(f).convert("RGB")
        im.thumbnail((1600, 1600))
        src = np.asarray(im, dtype=np.float64) / 255.0
        cells = [captioned(Image.fromarray(np.asarray(im)), "Original")]
        for lid in look_ids:
            e = find(exports, lid, "standard", "rec709_bt1886", REF_SIZE)
            out = tetrahedral(ap.table(e.relpath), src.reshape(-1, 3)).reshape(src.shape)
            to_img(out).save(outdir / f"{f.stem}_{e.look.token}.jpg", quality=92)
            cells.append(captioned(fit(to_img(out), 480), f"{e.look.number} {names[lid].upper()}"))
        vstack([hstack([fit(cells[0], 480)] + cells[1:3]), hstack(cells[3:])]).save(outdir / f"{f.stem}_CINERA_sheet.jpg", quality=90)
        print(f"rendered {f.name}")


def main(argv=None):
    ap_ = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("--media", type=Path, help="folder with your own stills (Rec.709); results stay local")
    args = ap_.parse_args(argv)

    exports, rendering = enumerate_exports(repo=REPO)
    missing = [e.relpath for e in exports if not (REPO / e.relpath).exists()]
    if missing:
        sys.exit(f"{len(missing)} exports missing — run scripts/build_luts.py first")
    ap = Applier(rendering)
    look_ids = COLLECTIONS["cinera-vol-01"]["looks"]
    names = {e.look.look_id: e.look.name for e in exports}

    if args.media:
        media_mode(args.media, exports, ap, names, look_ids)
        return

    scenes = {k: SCENES[k]() for k in SCENES}
    ba = before_after(exports, ap, scenes, look_ids, names)
    vs = variant_sheets(exports, ap, scenes, look_ids, names)
    ov = collection_sheet(exports, ap, scenes, look_ids, names)
    ps, pstats = profile_sheet(exports, ap, scenes, look_ids[0], names)
    cv = curves_and_histograms(exports, ap, scenes, look_ids, names)
    clip = clipping_report(exports, ap, scenes)
    (OUT / "reports/cross_profile_consistency.json").write_text(json.dumps(pstats, indent=1) + "\n")
    vpath = OUT / "reports/validation_report.json"
    validation = json.loads(vpath.read_text()) if vpath.exists() else None
    index_html([("Collection overview", [ov]), ("Soft / Standard / Rich", vs), ("Before / after", ba),
                ("Curves & histograms", cv), ("Every input profile", [ps])], validation, clip, pstats)
    for p in [*ba, *vs, ov, ps, *cv, OUT / "index.html"]:
        print(p.relative_to(REPO))


if __name__ == "__main__":
    main()
