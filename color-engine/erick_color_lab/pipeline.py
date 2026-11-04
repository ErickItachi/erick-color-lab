"""Pipeline assembly: (input profile, look, rendering) -> callable transform.

Exactly one technical path per profile kind — no technical step is ever
applied twice:

camera_log      signal --decode--> camera gamut --> AP1 --RGC--> scene AP1 --look--> rendering --> Rec.709
display_rec709  Rec.709 --rendering⁻¹--> scene AP1 --look--> rendering --> Rec.709
working_space   ACEScct --decode--> scene AP1 --look--> encode --> ACEScct (LMT)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .creative.look import Look
from .creative.operators import apply_look
from .transforms.profiles import Profile
from .transforms.rendering import Rendering
from .transforms.transfer import acescct_decode, acescct_encode


@dataclass
class Transform:
    look: Look
    profile: Profile
    rendering: Rendering

    @property
    def input_label(self) -> str:
        return self.profile.label

    @property
    def output_label(self) -> str:
        if self.profile.kind == "working_space":
            return "ACEScct (AP1), scene-referred — creative only, no output transform"
        return "Rec.709 primaries, ITU-R BT.1886 (gamma 2.4), D65, display-referred"

    @property
    def output_token(self) -> str:
        return "ACESCCT" if self.profile.kind == "working_space" else "REC709"

    def to_scene(self, signal: np.ndarray) -> np.ndarray:
        if self.profile.kind == "display_rec709":
            return self.rendering.inverse(signal)
        return self.profile.to_scene_ap1(signal)

    def __call__(self, signal: np.ndarray) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float64)
        scene = self.to_scene(signal)
        graded = apply_look(scene, self.look)
        if self.profile.kind == "working_space":
            return acescct_encode(graded)
        return self.rendering.forward(graded, source=self.render_source)

    @property
    def render_source(self) -> str:
        return "rec709" if self.profile.kind == "display_rec709" else "scene"

    def stats(self, signal: np.ndarray) -> dict:
        scene = self.to_scene(np.asarray(signal, dtype=np.float64))
        graded = apply_look(scene, self.look)
        if self.profile.kind == "working_space":
            return {"pre_clip_min": float(graded.min()), "pre_clip_max": float(graded.max()), "out_of_range_fraction": 0.0}
        return self.rendering.forward(graded, return_stats=True, source=self.render_source)[1]


def preview_display(acescct_values: np.ndarray, rendering: Rendering) -> np.ndarray:
    """Display a Creative-Only (ACEScct) result through the CINÉRA rendering."""
    return rendering.forward(acescct_decode(acescct_values))
