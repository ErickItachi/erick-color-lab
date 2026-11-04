"""CINÉRA Neutral Rendering — scene-linear AP1 -> Rec.709 / BT.1886 display.

This is a *technical* stage shared by every look (looks never duplicate it):

(Scene gamut compression — ACES 1.3 RGC — is part of the *camera input*
stage, see ``profiles.Profile``, so creative operators never receive
wide-gamut camera excursions.)

2. Per-channel tone scale (``ToneScale``): highlight roll-off with a natural
   path to white, toe for rich blacks.
3. AP1 -> Rec.709 (linear, CAT02 ACES white -> D65).
4. Display gamut compression into Rec.709 (same algorithm; limits derived
   from the AP1 boundary so the whole AP1 gamut folds inside Rec.709) and a
   final clip to [0, 1].
5. ITU-R BT.1886 inverse EOTF (gamma 2.4).

Steps 2–5 are invertible, so ``inverse`` maps Rec.709 display values back to
scene AP1 and ``forward(inverse(v)) == v`` within floating point tolerance
(verified in tests). This lets Rec.709 LUTs apply a
look as a *difference* from neutral: a neutral look is an exact identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..curves.tonescale import ToneScale
from ..gamut.compression import GamutCompression, boundary_limits
from . import colorspaces as cs
from .transfer import bt1886_eotf, bt1886_inverse_eotf


@dataclass
class Rendering:
    id: str = "cinera_neutral_rendering_v1"
    tone: ToneScale = field(default_factory=ToneScale)
    display_threshold: tuple = (0.85, 0.85, 0.85)
    display_power: float = 1.2
    rec709_source_threshold: tuple = (0.95, 0.95, 0.95)
    rec709_source_limit: tuple = (1.05, 1.05, 1.05)
    display_rgc: GamutCompression = field(init=False)
    display_rgc_rec709_source: GamutCompression = field(init=False)

    def __post_init__(self):
        m = cs.rgb_to_rgb_matrix("ap1", "rec709")
        lim = boundary_limits(m)
        # camera / working-space sources: fold the whole AP1 gamut into Rec.709
        self.display_rgc = GamutCompression(tuple(self.display_threshold), lim, self.display_power)
        # Rec.709 sources: only creative overshoots need folding; a gentle,
        # well-conditioned pair keeps forward(inverse(v)) exact and smooth.
        self.display_rgc_rec709_source = GamutCompression(
            tuple(self.rec709_source_threshold), tuple(self.rec709_source_limit), self.display_power)

    def _drgc(self, source: str) -> GamutCompression:
        return self.display_rgc_rec709_source if source == "rec709" else self.display_rgc

    # ------------------------------------------------------------------
    def forward(self, ap1_scene: np.ndarray, return_stats: bool = False, source: str = "scene"):
        """``source`` = "scene" (camera / working space) or "rec709" (Rec.709 footage path)."""
        y = self.tone.forward(np.asarray(ap1_scene, dtype=np.float64))
        r709 = cs.convert(y, "ap1", "rec709")
        r709 = self._drgc(source).forward(r709)
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
        """Exact inverse of ``forward(..., source="rec709")`` for any Rec.709
        display value in [0, 1]."""
        lin = bt1886_eotf(np.clip(np.asarray(rec709_display, dtype=np.float64), 0.0, 1.0))
        lin = self.display_rgc_rec709_source.inverse(lin)
        ap1 = cs.convert(lin, "rec709", "ap1")
        return self.tone.inverse(ap1)

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "Rendering":
        tone = ToneScale.from_dict(d["tone_scale"])
        dg = d.get("display_gamut_compression", {})
        dr = d.get("display_gamut_compression_rec709_source", {})
        return cls(
            id=d.get("id", "cinera_neutral_rendering_v1"),
            tone=tone,
            display_threshold=tuple(dg.get("threshold", (0.85, 0.85, 0.85))),
            display_power=float(dg.get("power", 1.2)),
            rec709_source_threshold=tuple(dr.get("threshold", (0.95, 0.95, 0.95))),
            rec709_source_limit=tuple(dr.get("limit", (1.05, 1.05, 1.05))),
        )

    @classmethod
    def from_file(cls, path) -> "Rendering":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
