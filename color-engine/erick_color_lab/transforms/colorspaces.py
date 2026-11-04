"""Colour spaces (primaries / white points) and RGB<->RGB matrices.

All primaries come from colour-science's RGB_COLOURSPACES dataset, which
implements the manufacturer / standards documents listed in REFERENCES.
Nothing here is hand-typed except the Oklab matrices, which are the published
values from Björn Ottosson, "A perceptual color space for image processing"
(2020) and are verified against ``colour.XYZ_to_Oklab`` in the tests.
"""

from __future__ import annotations

from functools import lru_cache

import colour
import numpy as np

# Engine gamut id -> colour-science dataset key
GAMUTS = {
    "rec709": "ITU-R BT.709",
    "rec2020": "ITU-R BT.2020",
    "sgamut3": "S-Gamut3",
    "sgamut3cine": "S-Gamut3.Cine",
    "cinema_gamut": "Cinema Gamut",
    "ap1": "ACEScg",
    "ap0": "ACES2065-1",
}

REFERENCES = {
    "rec709": "ITU-R BT.709-6 (2015)",
    "rec2020": "ITU-R BT.2020-2 (2015)",
    "sgamut3": "Sony, Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3",
    "sgamut3cine": "Sony, Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3",
    "cinema_gamut": "Canon, Cinema Gamut primaries (Canon EOS C-series documentation)",
    "ap1": "SMPTE ST 2065-1 / Academy S-2014-004 (ACEScg, AP1 primaries)",
    "ap0": "SMPTE ST 2065-1 (ACES2065-1, AP0 primaries)",
}

# Chromatic adaptation used when white points differ (D65 <-> ACES white).
# CAT02 matches the published Sony and Canon ACES IDT matrices (see tests).
# Because every camera-to-Rec.709 path adapts D65 -> ACES white and back with
# the same transform, the choice cancels out for neutral colours.
DEFAULT_CAT = "CAT02"


def colourspace(gamut_id: str) -> colour.RGB_Colourspace:
    try:
        return colour.RGB_COLOURSPACES[GAMUTS[gamut_id]]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown gamut id '{gamut_id}'. Known: {sorted(GAMUTS)}") from exc


@lru_cache(maxsize=None)
def _matrix(src: str, dst: str, cat: str) -> np.ndarray:
    s, d = colourspace(src), colourspace(dst)
    same_white = np.allclose(s.whitepoint, d.whitepoint, atol=1e-6)
    m = colour.matrix_RGB_to_RGB(s, d, chromatic_adaptation_transform=None if same_white else cat)
    m = np.asarray(m, dtype=np.float64)
    m.setflags(write=False)
    return m


def rgb_to_rgb_matrix(src: str, dst: str, cat: str = DEFAULT_CAT) -> np.ndarray:
    """3x3 matrix converting *linear* RGB from ``src`` to ``dst`` primaries."""
    return _matrix(src, dst, cat)


def apply_matrix(rgb: np.ndarray, m: np.ndarray) -> np.ndarray:
    return np.einsum("...j,ij->...i", rgb, m)


def convert(rgb: np.ndarray, src: str, dst: str, cat: str = DEFAULT_CAT) -> np.ndarray:
    if src == dst:
        return np.asarray(rgb, dtype=np.float64)
    return apply_matrix(np.asarray(rgb, dtype=np.float64), rgb_to_rgb_matrix(src, dst, cat))


@lru_cache(maxsize=None)
def luminance_weights(gamut_id: str) -> np.ndarray:
    """Y row of the RGB->XYZ matrix (relative luminance weights)."""
    w = np.asarray(colourspace(gamut_id).matrix_RGB_to_XYZ[1], dtype=np.float64)
    w.setflags(write=False)
    return w


def luminance(rgb: np.ndarray, gamut_id: str) -> np.ndarray:
    return rgb @ luminance_weights(gamut_id)


# ---------------------------------------------------------------------------
# Oklab (Ottosson 2020) — defined from *linear* Rec.709/sRGB primaries, D65.
# ---------------------------------------------------------------------------
_OKLAB_M1 = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]
)
_OKLAB_M2 = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)
_OKLAB_M1_INV = np.linalg.inv(_OKLAB_M1)
_OKLAB_M2_INV = np.linalg.inv(_OKLAB_M2)


def rec709_linear_to_oklab(rgb: np.ndarray) -> np.ndarray:
    lms = apply_matrix(rgb, _OKLAB_M1)
    return apply_matrix(np.cbrt(lms), _OKLAB_M2)


def oklab_to_rec709_linear(lab: np.ndarray) -> np.ndarray:
    lms_ = apply_matrix(lab, _OKLAB_M2_INV)
    return apply_matrix(lms_ ** 3, _OKLAB_M1_INV)


def oklab_to_lch(lab: np.ndarray):
    L = lab[..., 0]
    C = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360.0
    return L, C, h


def lch_to_oklab(L, C, h) -> np.ndarray:
    hr = np.radians(h)
    return np.stack([L, C * np.cos(hr), C * np.sin(hr)], axis=-1)
