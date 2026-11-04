"""Creative operators — the mathematical meaning of every look parameter.

Input and output of ``apply_look`` are **scene-linear AP1** (ACEScg) values.
Operators run in three domains, in this fixed order:

A. scene-linear AP1      exposure, white balance, black density, colour matrix
B. ACEScct (log)         contrast/pivot, lift/gamma/gain, tonal balance
                         (shadows / midtones / highlights; attenuated on skin
                         by skin.protect), RGB curves,
                         highlight compression (hue-preserving shoulder)
C. Oklab (perceptual)    colour separation, Hue vs Hue / Sat / Lum,
                         saturation mapping (global, shadows, highlights,
                         soft chroma limit), skin protection & skin pull

A neutral parameter set is an exact identity (verified in tests).
"""

from __future__ import annotations

import numpy as np

from ..curves.spline import MonotoneCurve, PeriodicCurve, smoothstep
from ..transforms import colorspaces as cs
from ..transforms.transfer import acescct_decode, acescct_encode
from .look import Look

GREY = 0.18
CCT_BLACK = float(acescct_encode(0.0))            # ACEScct of scene 0.0 (0.0729)
CCT_WHITE = float(acescct_encode(GREY * 2 ** 6.5))  # LGG white reference (+6.5 stops)
L_GREY = float(np.cbrt(GREY))                     # Oklab L of an 18 % neutral
# Floor for the chroma/lightness ratio C/L: Oklab L of a neutral 6 stops below
# grey. Keeps every ratio-based mask well-conditioned near black (sensor
# noise / sub-black codes) where C/L would otherwise diverge.
L_FLOOR = float(np.cbrt(GREY * 2.0 ** -6))
# Hue-keyed operations fade in with *absolute* Oklab chroma: hue is
# ill-conditioned when C -> 0 (dark, low-chroma colours), so masks keyed on
# hue would otherwise vary steeply there.
HUE_CHROMA_FADE = (0.0, 0.03)
DEEP_SHADOW_FADE = (-9.0, -4.5)  # stops: perceptual operations fade in over this range
BLACK_NEUTRAL_FADE = (-10.0, -6.0)  # stops: tonal-balance tints fade in over this range
_W_AP1 = cs.luminance_weights("ap1")
_M_AP1_709 = cs.rgb_to_rgb_matrix("ap1", "rec709")
_M_709_AP1 = cs.rgb_to_rgb_matrix("rec709", "ap1")


def _stops(y):
    return np.log2(np.maximum(y, 1e-10) / GREY)


# ---------------------------------------------------------------------------
# A. scene-linear
# ---------------------------------------------------------------------------
def white_balance_gains(warmth: float, tint: float) -> np.ndarray:
    g = np.array([2.0 ** (warmth / 2.0), 2.0 ** tint, 2.0 ** (-warmth / 2.0)])
    return g / float(g @ _W_AP1)  # unit luminance: balance does not change exposure


def black_density(x, offset: float):
    """offset < 0: smooth density on luminance, Y' = Y^2 / (Y + d), applied as a
    common RGB scale (hue and saturation preserved — rich blacks, no hue skew).
    offset > 0: neutral matte lift (x + offset)."""
    if offset == 0.0:
        return x
    if offset > 0.0:
        return x + offset
    d = -offset
    Y = np.maximum(x @ _W_AP1, 0.0)  # non-physical Y <= 0 -> k = 0 (continuous at 0)
    k = Y / (Y + d)
    return x * k[..., None]


# ---------------------------------------------------------------------------
# B. ACEScct
# ---------------------------------------------------------------------------
def contrast(cct, amount: float, pivot: float, hue_preservation: float = 0.0):
    """Log contrast around ``pivot``. ``hue_preservation`` blends from
    per-channel contrast (0, the classic log grade — skews hue with exposure)
    to luminance contrast with constant RGB ratios (1, hue/chroma preserved)."""
    per_channel = pivot + (cct - pivot) * amount
    if hue_preservation <= 0.0:
        return per_channel
    lin = acescct_decode(cct)
    Y = np.maximum(lin @ _W_AP1, 0.0)
    cy = acescct_encode(Y)
    Y2 = acescct_decode(pivot + (cy - pivot) * amount)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(Y > 0.0, Y2 / np.maximum(Y, 1e-12), 0.0)
    ratio_kept = acescct_encode(lin * np.maximum(k, 0.0)[..., None])
    return per_channel + hue_preservation * (ratio_kept - per_channel)


def lift_gamma_gain(cct, p: dict):
    lift = np.asarray(p["lift"]) + p["master_lift"]
    gamma = np.asarray(p["gamma"]) * p["master_gamma"]
    gain = np.asarray(p["gain"]) * p["master_gain"]
    if np.allclose(lift, 0) and np.allclose(gamma, 1) and np.allclose(gain, 1):
        return cct
    v = (cct - CCT_BLACK) / (CCT_WHITE - CCT_BLACK)
    y = gain * (v + lift * (1.0 - v))
    y = np.sign(y) * np.abs(y) ** (1.0 / gamma)
    return CCT_BLACK + y * (CCT_WHITE - CCT_BLACK)


def tonal_masks(lin_ap1, shadow_end, highlight_start, softness):
    e = _stops(np.maximum(lin_ap1 @ _W_AP1, 0.0))
    sh = smoothstep(shadow_end + softness, shadow_end - softness, e)
    hi = smoothstep(highlight_start - softness, highlight_start + softness, e)
    mid = np.clip(1.0 - sh - hi, 0.0, 1.0)
    return sh, mid, hi


def tonal_balance(cct, lin_ap1, p: dict, weight=None):
    """``weight`` (0..1 per pixel) attenuates the offsets — used by skin
    protection so split-toning never tints skin."""
    offs = [np.asarray(p[k], dtype=np.float64) for k in ("shadows", "midtones", "highlights")]
    if all(np.allclose(o, 0) for o in offs):
        return cct
    if p["preserve_luma"]:
        offs = [o - float(o @ _W_AP1) for o in offs]
    sh, mid, hi = tonal_masks(lin_ap1, p["shadow_end"], p["highlight_start"], p["softness"])
    delta = sh[..., None] * offs[0] + mid[..., None] * offs[1] + hi[..., None] * offs[2]
    # tints fade out toward black: shadows are tinted, pure black stays neutral
    e = _stops(np.maximum(lin_ap1 @ _W_AP1, 0.0))
    delta = delta * smoothstep(BLACK_NEUTRAL_FADE[0], BLACK_NEUTRAL_FADE[1], e)[..., None]
    if weight is not None:
        delta = delta * weight[..., None]
    return cct + delta


def rgb_curves(cct, p: dict):
    out = cct
    if p["master"]:
        out = MonotoneCurve(p["master"])(out)
    chans = []
    for i, k in enumerate(("red", "green", "blue")):
        c = out[..., i]
        chans.append(MonotoneCurve(p[k])(c) if p[k] else c)
    return np.stack(chans, axis=-1)


def highlight_compression(lin_ap1, threshold: float, strength: float):
    """Hue-preserving shoulder on the max channel, evaluated in ACEScct."""
    if strength <= 0.0:
        return lin_ap1
    m = np.max(lin_ap1, axis=-1)
    mc = acescct_encode(np.maximum(m, 0.0))
    over = np.maximum(mc - threshold, 0.0)
    mc2 = np.where(mc > threshold, threshold + over / (1.0 + strength * over), mc)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(m > 0.0, acescct_decode(mc2) / m, 1.0)
    return lin_ap1 * k[..., None]


# ---------------------------------------------------------------------------
# C. Oklab
# ---------------------------------------------------------------------------
def _wrap(dh):
    return (dh + 180.0) % 360.0 - 180.0


def skin_mask(h, ratio, center, width, C=None):
    m_h = np.exp(-0.5 * (_wrap(h - center) / width) ** 2)
    m_r = smoothstep(0.015, 0.045, ratio) * (1.0 - smoothstep(0.20, 0.32, ratio))
    m = m_h * m_r
    if C is not None:
        m = m * smoothstep(HUE_CHROMA_FADE[0], HUE_CHROMA_FADE[1], C)
    return m


def skin_weight(lin_ap1, skin: dict):
    """Skin mask evaluated on scene-linear AP1 (Oklab hue and C/L ratio)."""
    lab = cs.rec709_linear_to_oklab(cs.apply_matrix(lin_ap1, _M_AP1_709))
    L, C, h = cs.oklab_to_lch(lab)
    ratio = C / np.maximum(L, L_FLOOR)
    return skin_mask(h, ratio, skin["hue_center"], skin["hue_width"], C)


def perceptual(lin_ap1, p: dict):
    sat, skin, sep = p["saturation"], p["skin"], p["color_separation"]
    hue_curves = [p["hue_vs_hue"], p["hue_vs_sat"], p["hue_vs_lum"]]
    neutral = (
        sep["amount"] == 0.0 and not any(hue_curves)
        and sat["global"] == 1.0 and sat["shadows"] == 1.0 and sat["highlights"] == 1.0
        and skin["pull"] == 0.0
    )
    if neutral and sat["chroma_knee"] is None:
        return lin_ap1
    rgb709 = cs.apply_matrix(lin_ap1, _M_AP1_709)
    lab = cs.rec709_linear_to_oklab(rgb709)
    L, C, h = cs.oklab_to_lch(lab)
    ratio = C / np.maximum(L, L_FLOOR)
    # Validity: fade every perceptual operation out where a cone response
    # approaches zero (edge of the physically meaningful domain), avoiding
    # the cube-root singularity of Oklab and keeping the transform smooth.
    lms = cs.apply_matrix(rgb709, cs._OKLAB_M1)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(np.max(np.abs(lms), -1) > 0, np.min(lms, -1) / np.max(np.abs(lms), -1), 0.0)
    w_valid = smoothstep(0.0, 0.04, q)
    # Deep-shadow fade: below ~-5 stops colour estimates are dominated by
    # noise / sub-black codes; perceptual edits fade out smoothly so luminance
    # stays monotone toward black.
    e = 3.0 * np.log2(np.maximum(L, 1e-6) / L_GREY)  # stops relative to grey
    w_valid = w_valid * smoothstep(DEEP_SHADOW_FADE[0], DEEP_SHADOW_FADE[1], e)

    if neutral:
        dh = np.zeros_like(h)
        S = np.ones_like(h)
        M = np.ones_like(h)
    else:
        w_hue = smoothstep(HUE_CHROMA_FADE[0], HUE_CHROMA_FADE[1], C)
        w_c = smoothstep(0.01, 0.06, ratio) * w_valid * w_hue  # neutrals / low chroma / out-of-domain untouched
        m_skin = skin_mask(h, ratio, skin["hue_center"], skin["hue_width"], C)
        protect = 1.0 - skin["protect"] * m_skin
        g = w_valid  # global operations also fade out of the valid domain

        dh = -sep["amount"] * np.sin(2.0 * np.radians(h - sep["axis_hue"]))
        dh = dh + PeriodicCurve(p["hue_vs_hue"], 0.0)(h)
        dh = dh * w_c * protect + skin["pull"] * m_skin * w_valid * (-_wrap(h - skin["hue_center"]))

        tb = p["tonal_balance"]
        sh = smoothstep(tb["shadow_end"] + tb["softness"], tb["shadow_end"] - tb["softness"], e)
        hi = smoothstep(tb["highlight_start"] - tb["softness"], tb["highlight_start"] + tb["softness"], e)
        s_tone = (1 - sh - hi).clip(0, 1) + sh * sat["shadows"] + hi * sat["highlights"]
        s_hue = PeriodicCurve(p["hue_vs_sat"], 1.0)(h)
        s_hue = 1.0 + (s_hue - 1.0) * w_c
        S = np.maximum(sat["global"] * s_tone * s_hue, 0.0) ** (protect * g)

        M = PeriodicCurve(p["hue_vs_lum"], 1.0)(h)
        M = np.maximum(1.0 + (M - 1.0) * w_c, 1e-3) ** (protect * g)

    C2 = C * S
    C3 = C2
    if sat["chroma_knee"] is not None:
        # soft chroma limit on the exposure-invariant ratio C/L (tanh shoulder, C1)
        knee, lim = sat["chroma_knee"], sat["chroma_limit"]
        Lf = np.maximum(L, L_FLOOR)
        r2 = C2 / Lf
        r3 = knee + (lim - knee) * np.tanh((r2 - knee) / (lim - knee))
        C3 = np.where(r2 > knee, C2 + (r3 * Lf - C2) * w_valid, C2)
    L2 = L * np.cbrt(M)
    lab2 = cs.lch_to_oklab(L2, C3, h + dh)
    return cs.apply_matrix(cs.oklab_to_rec709_linear(lab2), _M_709_AP1)


# ---------------------------------------------------------------------------
def apply_look(lin_ap1: np.ndarray, look: Look) -> np.ndarray:
    p = look.parameters
    x = np.asarray(lin_ap1, dtype=np.float64)

    # A. scene-linear
    if p["exposure"]:
        x = x * 2.0 ** p["exposure"]
    wb = p["white_balance"]
    if wb["warmth"] or wb["tint"]:
        x = x * white_balance_gains(wb["warmth"], wb["tint"])
    x = black_density(x, p["black_offset"])
    m = np.asarray(p["color_matrix"], dtype=np.float64)
    if not np.allclose(m, np.eye(3)):
        x = cs.apply_matrix(x, m)

    # B. ACEScct
    cct = acescct_encode(x)
    c = p["contrast"]
    if c["amount"] != 1.0:
        cct = contrast(cct, c["amount"], c["pivot"], c["hue_preservation"])
    cct = lift_gamma_gain(cct, p["lift_gamma_gain"])
    tb_weight = None
    if p["skin"]["protect"] > 0:
        tb_weight = 1.0 - p["skin"]["protect"] * skin_weight(x, p["skin"])
    cct = tonal_balance(cct, acescct_decode(cct), p["tonal_balance"], tb_weight)
    cct = rgb_curves(cct, p["curves"])
    x = acescct_decode(cct)
    hc = p["highlight_compression"]
    x = highlight_compression(x, hc["threshold"], hc["strength"])

    # C. Oklab
    return perceptual(x, p)
