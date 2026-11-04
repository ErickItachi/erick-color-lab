"""Input / working-space profiles (loaded from ``profiles/**.json``).

A profile states *precisely* what a LUT expects at its input:
transfer function, primaries, signal range. Kinds:

* ``camera_log``      camera log signal  -> scene-linear AP1 (+ ACES 1.3 RGC)
* ``display_rec709``  Rec.709 / BT.1886 display signal (inverse rendering)
* ``working_space``   a float grading space (ACEScct) for Creative-Only LUTs
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..gamut.compression import ACES_RGC
from . import colorspaces as cs
from . import transfer as tf

INPUT_GAMUT_COMPRESSION = {None: None, "aces_rgc_1.3": ACES_RGC}

KINDS = ("camera_log", "display_rec709", "working_space")


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    kind: str
    transfer: str
    gamut: str
    signal_range: str
    file_token: str
    export_folder: str
    output: str  # "rec709" or "acescct"
    raw: dict
    gamut_compression: str | None = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"profile {self.id}: unknown kind {self.kind}")
        tf.get_transfer(self.transfer)
        cs.colourspace(self.gamut)
        if self.gamut_compression not in INPUT_GAMUT_COMPRESSION:
            raise ValueError(f"profile {self.id}: unknown gamut_compression {self.gamut_compression}")

    # -- technical input transform: host signal -> scene-linear AP1 -------------
    def to_scene_ap1(self, signal: np.ndarray) -> np.ndarray:
        if self.kind == "display_rec709":
            raise RuntimeError("display profiles are mapped through the rendering inverse")
        lin = tf.decode(signal, self.transfer, self.signal_range)
        ap1 = cs.convert(lin, self.gamut, "ap1")
        rgc = INPUT_GAMUT_COMPRESSION[self.gamut_compression]
        return rgc.forward(ap1) if rgc else ap1

    def from_scene_ap1(self, ap1: np.ndarray) -> np.ndarray:
        """Encode scene AP1 as this profile's signal (used to synthesise camera
        test signals). Gamut compression is not inverted: test scenes are
        generated inside AP1."""
        lin = cs.convert(ap1, "ap1", self.gamut)
        return tf.encode(lin, self.transfer, self.signal_range)

    @classmethod
    def from_file(cls, path) -> "Profile":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            id=d["id"],
            label=d["label"],
            kind=d["kind"],
            transfer=d["transfer"],
            gamut=d["gamut"],
            signal_range=d["signal"]["range"],
            file_token=d["file_token"],
            export_folder=d["export_folder"],
            output=d.get("output", "rec709"),
            raw=d,
            gamut_compression=d.get("gamut_compression"),
        )


def load_profiles(root) -> dict:
    root = Path(root)
    out = {}
    for p in sorted(root.glob("*/*.json")):
        if p.parent.name == "output":
            continue
        prof = Profile.from_file(p)
        if prof.raw.get("enabled", True):
            out[prof.id] = prof
    return out
