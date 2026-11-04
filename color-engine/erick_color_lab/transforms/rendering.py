"""CINÉRA Neutral Rendering — scene-linear AP1 -> Rec.709 / BT.1886 display.

This is a *technical* stage shared by every look (looks never duplicate it):

1. Scene gamut compression in AP1 (ACES 1.3 Reference Gamut Compression,
   published parameters) — folds wide camera gamuts into AP1 smoothly.
2. Per-channel tone scale (``ToneScale``): highlight roll-off with a natural
   path to white, toe for rich blacks.
3. AP1 -> Rec.709 (linear, CAT02 ACES white -> D65).
4. Display gamut compression into Rec.709 (same algorithm; limits derived
   from the AP1 boundary so the whole AP1 gamut folds inside Rec.709) and a
   final clip to [0, 1].
5. ITU-R BT.1886 inverse EOTF (gamma 2.4).

Steps 2–5 are invertible, so ``inverse`` maps Rec.709 display values back to
scene AP1 and ``forward(inverse(v), scene_compression=False) == v`` within
floating point tolerance (verified in tests). Step 1 is only applied to camera
and working-space sources (Rec.709 sources have no wide-gamut excursions). This lets Rec.709 LUTs apply a
look as a *difference* from neutral: a neutral look is an exact identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..curves.tonescale import ToneScale
from ..gamut.compression import ACES_RGC, GamutCompression, boundary_limits
from . import colorspaces as cs
from .transfer import bt1886_eotf, bt1886_inverse_eotf


@dataclass
class Rendering:
    id: str = "cinera_neutral_rendering_v1"
    tone: ToneScale = field(default_factory=ToneScale)
    scene_rgc: GamutCompression = ACES_RGC
    display_threshold: tuple = (0.85, 0.85, 0.85)
    display_power: float = 1.2
    display_rgc: GamutCompression = field(init=False)

    def __post_init__(self):
        m = cs.rgb_to_rgb_matrix("ap1", "rec709")
        lim = boundary_limits(m)
        self.display_rgc = GamutCompression(tuple(self.display_threshold), lim, self.display_power)

    # ------------------------------------------------------------------
    def forward(self, ap1_scene: np.ndarray, return_stats: bool = False, scene_compression: bool = True):
        """``scene_compression`` (step 1) is used for camera / working-space
        sources. Rec.709 sources cannot contain wide-gamut camera excursions,
        so their path renders without it (and its inverse is never needed)."""
        x = self.scene_rgc.forward(ap1_scene) if scene_compression else np.asarray(ap1_scene, dtype=np.float64)
        y = self.tone.forward(x)
        r709 = cs.convert(y, "ap1", "rec709")
        r709 = self.display_rgc.forward(r709)
        stats = None
        if return_stats:
            stats = {
                "pre_clip_min": float(np.min(r709)),
                "pre_clip_max": float(np.max(r709)),
                "out_of_range_fraction": float(np.mean(np.any((r709 < -1e-6) | (r709 > 1 + 1e-6), axis=-1))),
            }
        out = bt1886_inverse_eotf(np.clip(r709, 0.0, 1.0))
        return (out, stats) if return_stats else out

    def inverse(self, rec709_display: np.ndarray) -> np.ndarray:
        """Exact inverse of ``forward(..., scene_compression=False)`` for any
        Rec.709 display value in [0, 1]: forward(inverse(v)) == v."""
        lin = bt1886_eotf(np.clip(np.asarray(rec709_display, dtype=np.float64), 0.0, 1.0))
        lin = self.display_rgc.inverse(lin)
        ap1 = cs.convert(lin, "rec709", "ap1")
        return self.tone.inverse(ap1)

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "Rendering":
        tone = ToneScale.from_dict(d["tone_scale"])
        dg = d.get("display_gamut_compression", {})
        return cls(
            id=d.get("id", "cinera_neutral_rendering_v1"),
            tone=tone,
            display_threshold=tuple(dg.get("threshold", (0.85, 0.85, 0.85))),
            display_power=float(dg.get("power", 1.2)),
        )

    @classmethod
    def from_file(cls, path) -> "Rendering":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
