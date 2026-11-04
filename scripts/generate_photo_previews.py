#!/usr/bin/env python3
"""Photo previews: real photographs through every input profile + exported LUT.

Source images: Unsplash / Pexels photographs (free commercial use under the
Unsplash and Pexels licences), stored in test-media/photos/ (git-ignored);
credits in previews/photo-tests/CREDITOS.md. Landscape frames are shown in a
2.39:1 cinema crop.

For each photo and each profile:
  photo (Rec.709 display)
    -> exact inverse of the CINERA Neutral Rendering  (scene-linear AP1)
    -> encoded as that profile's signal (S-Log3, Apple Log, Canon Log 3, ACEScct)
       = SIMULATED camera signal (not footage recorded by the camera)
    -> exported .cube applied at the end (read from disk, tetrahedral)
Rec.709 profile: the photo is used directly as the Rec.709 input.

    python scripts/generate_photo_previews.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

import matplotlib  # noqa: E402

from erick_color_lab.collection import enumerate_exports  # noqa: E402
from erick_color_lab.interpolation.lut3d import tetrahedral  # noqa: E402
from erick_color_lab.lut_baking.cube import read_cube  # noqa: E402
from erick_color_lab.transforms.transfer import acescct_decode, acescct_encode  # noqa: E402

PHOTOS = {  # id: (description, photographer / source)
    "p_stairs": ("retrato · pele escura", "Prime Cinematics (Pexels)"),
    "p_field": ("família · campo, fim de tarde", "Jessica Rockowitz (Unsplash)"),
    "p_door": ("documental · interior", "tkirkgoz (Pexels)"),
    "p_red_night": ("noite · vestido vermelho", "dauphotographer (Pexels)"),
    "p_family_white": ("família · festa ao ar livre", "Ron Lach (Pexels)"),
    "p_celebration": ("celebração · luzes", "cottonbro studio (Pexels)"),
    "p_forest": ("natureza · neblina", "Guy Bowden (Unsplash)"),
    "p_ocean": ("pôr do sol · mar", "Gontran Isnard (Unsplash)"),
    "p_rain_street": ("cidade · chuva", "Nikhil (Pexels)"),
}
SRC = REPO / "test-media/photos"
OUT = REPO / "previews/photo-tests"
CELL_H = 300
FONT = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
FONT_B = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans-Bold.ttf"
BG = (18, 18, 18)
INK = (238, 234, 225)
PROFILES = ["rec709_bt1886", "slog3_sgamut3cine", "slog3_sgamut3", "applelog_bt2020", "clog3_cinemagamut", "acescct_ap1"]
LOOKS = ["01-signature", "02-golden", "03-olive", "04-blue-hour", "05-romance"]


def fetch():
    missing = [pid for pid in PHOTOS if not (SRC / f"{pid}.png").exists()]
    if missing:
        sys.exit(f"missing photos in {SRC}: {missing}")


def load(pid, max_side=1200):
    im = Image.open(SRC / f"{pid}.png").convert("RGB")
    w, h = im.size
    if w > h:  # cinema crop for landscape frames
        nh = round(w / 2.39)
        if nh < h:
            top = (h - nh) // 2
            im = im.crop((0, top, w, top + nh))
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    return np.asarray(im, dtype=np.float64) / 255.0


def f(size, bold=False):
    return ImageFont.truetype(str(FONT_B if bold else FONT), size)


def to_img(a):
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    return im.resize((round(im.width * CELL_H / im.height), CELL_H), Image.LANCZOS)


def cap(im, text, size=14):
    h = size + 14
    out = Image.new("RGB", (im.width, im.height + h), BG)
    out.paste(im, (0, h))
    ImageDraw.Draw(out).text((6, 5), text, font=f(size), fill=INK)
    return out


def row(cells, gap=6):
    out = Image.new("RGB", (sum(c.width for c in cells) + gap * (len(cells) - 1), max(c.height for c in cells)), BG)
    x = 0
    for c in cells:
        out.paste(c, (x, 0))
        x += c.width + gap
    return out


def col(rows, gap=10):
    out = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows) + gap * (len(rows) - 1)), BG)
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + gap
    return out


def titled(body, title, sub):
    h = 78
    out = Image.new("RGB", (body.width + 40, body.height + h + 40), BG)
    d = ImageDraw.Draw(out)
    d.text((20, 16), title, font=f(26, True), fill=INK)
    d.text((20, 52), sub, font=f(13), fill=(190, 188, 180))
    out.paste(body, (20, h))
    return out


def main():
    fetch()
    exports, rendering = enumerate_exports(sizes=(65,), repo=REPO)
    ex = {(e.look.look_id, e.look.variant, e.profile.id): e for e in exports}
    tables = {}

    def table(e):
        if e.relpath not in tables:
            tables[e.relpath] = read_cube(REPO / e.relpath).table
        return tables[e.relpath]

    photos = {pid: load(pid) for pid in PHOTOS}
    scene = {pid: rendering.inverse(img.reshape(-1, 3), ) for pid, img in photos.items()}

    def signal(pid, prof):
        img = photos[pid]
        if prof.kind == "display_rec709":
            return img
        sc = scene[pid]
        sig = acescct_encode(sc) if prof.kind == "working_space" else prof.from_scene_ap1(sc)
        return np.clip(sig, 0, 1).reshape(img.shape)

    def apply(e, sig):
        out = tetrahedral(table(e), sig.reshape(-1, 3))
        if e.profile.kind == "working_space":
            out = rendering.forward(acescct_decode(out))
        return out.reshape(sig.shape)

    OUT.mkdir(parents=True, exist_ok=True)
    note = "Fotos: Unsplash / Pexels (licenças de uso livre). Sinal de câmera SIMULADO a partir da foto; LUT exportado (65³) aplicado no final, sem retoque depois do LUT."
    written = []
    # 1) one sheet per profile: signal | 5 looks (standard)
    for pid_prof in PROFILES:
        prof = ex[("01-signature", "standard", pid_prof)].profile
        rows = []
        for pid, (desc, _) in PHOTOS.items():
            sig = signal(pid, prof)
            label = "entrada Rec.709 (original)" if prof.kind == "display_rec709" else f"sinal {prof.file_token} (simulado)"
            cells = [cap(to_img(sig), label)]
            for lid in LOOKS:
                e = ex[(lid, "standard", pid_prof)]
                cells.append(cap(to_img(apply(e, sig)), f"{e.look.number} {e.look.name.upper()}"))
            rows.append(cap(row(cells), desc, 13))
        img = titled(col(rows), f"CINÉRA VOL. 01 · {prof.label}",
                     f"Arquivos: CINERA_<NN>_<LOOK>_STANDARD_{prof.file_token}_TO_{'ACESCCT' if prof.kind == 'working_space' else 'REC709'}_65.cube   ·   {note}")
        p = OUT / f"CINERA_FOTOS_{prof.file_token}.jpg"
        img.save(p, quality=90)
        written.append(p)
    # 2) one sheet per look: original | soft | standard | rich (S-Log3 / S-Gamut3.Cine chain)
    for lid in LOOKS:
        rows = []
        for pid, (desc, _) in PHOTOS.items():
            cells = [cap(to_img(photos[pid]), "original")]
            for v in ("soft", "standard", "rich"):
                e = ex[(lid, v, "slog3_sgamut3cine")]
                cells.append(cap(to_img(apply(e, signal(pid, e.profile))), v.upper()))
            rows.append(cap(row(cells), desc, 13))
        e = ex[(lid, "standard", "slog3_sgamut3cine")]
        img = titled(col(rows), f"CINÉRA {e.look.number} {e.look.name.upper()} · Soft / Standard / Rich",
                     "Cadeia: foto -> sinal S-Log3/S-Gamut3.Cine (simulado) -> LUT exportado. " + note)
        p = OUT / f"CINERA_FOTOS_{e.look.number}_{e.look.name.upper().replace(' ', '')}_variacoes.jpg"
        img.save(p, quality=90)
        written.append(p)
    credits = "\n".join(f"- {d} — foto: {c}" for d, c in PHOTOS.values())
    (OUT / "CREDITOS.md").write_text(
        "# Créditos das fotos\n\nFotos do Unsplash e do Pexels, usadas sob as licenças Unsplash / Pexels (uso comercial livre).\n\n"
        + credits + "\n\nO sinal de câmera (S-Log3, Apple Log, Canon Log 3, ACEScct) foi **simulado** a partir de cada foto "
        "(inversa exata do CINÉRA Neutral Rendering seguida da codificação do perfil). Não é footage gravada por essas câmeras. "
        "Nenhum ajuste foi feito depois do LUT.\n", encoding="utf-8")
    for p in written:
        print(p.relative_to(REPO))


if __name__ == "__main__":
    main()
