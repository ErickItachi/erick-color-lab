"""Distance-based gamut compression (ACES Reference Gamut Compression).

Algorithm and the ACES 1.3 parameters are from the Academy's
"ACES Reference Gamut Compression" specification (ACES 1.3, 2021; Academy
S-2021-001 / aces-dev ``LMT.Academy.ReferenceGamutCompress.ctl``). The
implementation is cross-checked against the OpenColorIO builtin
``ACES-LMT - ACES 1.3 Reference Gamut Compression`` in the tests.

The same algorithm (with our own, documented parameters) is reused to fold
AP1 display colours into Rec.709 before the final clip.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ACES 1.3 RGC parameters (cyan, magenta, yellow == distances of R, G, B)
ACES_RGC_THRESHOLD = (0.815, 0.803, 0.880)
ACES_RGC_LIMIT = (1.147, 1.264, 1.312)
ACES_RGC_POWER = 1.2


@dataclass(frozen=True)
class GamutCompression:
    threshold: tuple = ACES_RGC_THRESHOLD
    limit: tuple = ACES_RGC_LIMIT
    power: float = ACES_RGC_POWER

    def _scale(self):
        thr = np.asarray(self.threshold, dtype=np.float64)
        lim = np.asarray(self.limit, dtype=np.float64)
        p = self.power
        return thr, (lim - thr) / (((1.0 - thr) / (lim - thr)) ** (-p) - 1.0) ** (1.0 / p)

    def _distances(self, rgb):
        ach = np.max(rgb, axis=-1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.where(ach == 0.0, 0.0, (ach - rgb) / np.abs(ach))
        return ach, d

    def forward(self, rgb):
        rgb = np.asarray(rgb, dtype=np.float64)
        thr, s = self._scale()
        p = self.power
        ach, d = self._distances(rgb)
        x = np.maximum(d - thr, 0.0) / s
        cd = np.where(d < thr, d, thr + s * x / (1.0 + x ** p) ** (1.0 / p))
        return ach - cd * np.abs(ach)

    def inverse(self, rgb):
        rgb = np.asarray(rgb, dtype=np.float64)
        thr, s = self._scale()
        p = self.power
        ach, cd = self._distances(rgb)
        # valid only for cd < thr + s (the compressed range); clamp just inside
        x = np.clip((cd - thr) / s, 0.0, 1.0 - 1e-9)
        xp = x ** p
        d = np.where(cd < thr, cd, thr + s * (xp / (1.0 - xp)) ** (1.0 / p))
        return ach - d * np.abs(ach)


ACES_RGC = GamutCompression()


def boundary_limits(src_to_dst: np.ndarray, samples: int = 65, margin: float = 1.01) -> tuple:
    """Per-channel distance limits so the *source* gamut boundary (unit cube
    surface) lands on the destination gamut boundary after compression.

    Derived from the matrices only — no invented constants.
    """
    t = np.linspace(0.0, 1.0, samples)
    a, b = np.meshgrid(t, t, indexing="ij")
    a, b = a.ravel(), b.ravel()
    faces = []
    for axis in range(3):
        for val in (0.0, 1.0):
            f = np.empty((a.size, 3))
            others = [i for i in range(3) if i != axis]
            f[:, axis] = val
            f[:, others[0]] = a
            f[:, others[1]] = b
            faces.append(f)
    surf = np.concatenate(faces)
    surf = surf[np.max(surf, axis=1) > 1e-3]
    dst = surf @ src_to_dst.T
    ach = np.max(dst, axis=1, keepdims=True)
    d = (ach - dst) / np.abs(ach)
    lim = np.maximum(d.max(axis=0) * margin, 1.0001)
    return tuple(float(v) for v in lim)
