"""Look definition files (``looks/<id>/<variant>.json``).

Each variant is a complete, self-contained, human-editable parameter set.
``NEUTRAL_PARAMETERS`` documents every key and its neutral (no-op) value;
a file only needs to specify what differs, and unknown keys are rejected so
that a typo never silently does nothing. The future ERICK COLOR LAB app edits
these same files (non-destructive workflow).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "erick-color-lab/look@1"

NEUTRAL_PARAMETERS = {
    # --- scene-linear (AP1) operations ---------------------------------------
    "exposure": 0.0,                         # stops (linear gain 2**exposure)
    "white_balance": {"warmth": 0.0,         # log2 R/B gain ratio (+ = warmer)
                      "tint": 0.0},          # log2 G gain (+ = greener, - = magenta)
    "black_offset": 0.0,                     # <0 smooth luminance density Y^2/(Y+d) (hue-preserving); >0 matte offset
    "color_matrix": [[1.0, 0.0, 0.0],        # linear AP1 3x3, rows must sum to 1 (keeps neutrals)
                     [0.0, 1.0, 0.0],
                     [0.0, 0.0, 1.0]],
    # --- ACEScct (log) operations --------------------------------------------
    "contrast": {"amount": 1.0, "pivot": 0.4136,    # y = pivot + (x - pivot) * amount ; 0.4136 = 18 % grey
                 "hue_preservation": 0.0},          # 0 per-channel .. 1 luminance contrast, constant RGB ratios
    "lift_gamma_gain": {
        "lift": [0.0, 0.0, 0.0], "gamma": [1.0, 1.0, 1.0], "gain": [1.0, 1.0, 1.0],
        "master_lift": 0.0, "master_gamma": 1.0, "master_gain": 1.0,
    },
    "tonal_balance": {                       # colour offsets (ACEScct units) per tonal range
        "shadows": [0.0, 0.0, 0.0],
        "midtones": [0.0, 0.0, 0.0],
        "highlights": [0.0, 0.0, 0.0],
        "shadow_end": -2.5,                  # stops relative to 18 % grey
        "highlight_start": 1.5,              # stops relative to 18 % grey
        "softness": 1.5,                     # transition half-width, stops
        "preserve_luma": True,
    },
    "curves": {"master": [], "red": [], "green": [], "blue": []},  # [[x, y], ...] ACEScct, monotone
    "highlight_compression": {"threshold": 0.70, "strength": 0.0},  # max-channel shoulder, ACEScct
    # --- perceptual (Oklab) operations ---------------------------------------
    "color_separation": {"amount": 0.0, "axis_hue": 55.0},  # degrees; pulls hues to warm/cool axis
    "hue_vs_hue": [],                        # [[hue_deg, shift_deg], ...]
    "hue_vs_sat": [],                        # [[hue_deg, chroma multiplier], ...]
    "hue_vs_lum": [],                        # [[hue_deg, luminance multiplier], ...]
    "saturation": {
        "global": 1.0,
        "shadows": 1.0,                      # multiplier below shadow_end (tonal_balance ranges)
        "highlights": 1.0,                   # multiplier above highlight_start
        "chroma_knee": None,                 # C/L ratio where soft chroma limiting starts (null = off)
        "chroma_limit": None,                # asymptotic maximum C/L ratio (null = off)
    },
    "skin": {
        "protect": 0.0,                      # 0..1 — shields skin from hue/sat/lum shaping
        "hue_center": 42.0,                  # Oklab hue of skin (ColorChecker skin patches: 38–42°)
        "hue_width": 16.0,                   # Gaussian sigma, degrees
        "pull": 0.0,                         # 0..1 — pulls skin hue toward hue_center (consistency)
    },
}


def _merge(base: dict, override: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        key = f"{path}.{k}" if path else k
        if k not in base:
            raise KeyError(f"unknown look parameter '{key}'")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise TypeError(f"parameter '{key}' must be an object")
            out[k] = _merge(base[k], v, key)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class Look:
    look_id: str
    number: str
    name: str
    variant: str
    version: str
    description: str
    parameters: dict
    source: dict
    path: Path | None = None

    @property
    def token(self) -> str:
        """Filename token, e.g. '01_SIGNATURE_STANDARD'."""
        name = self.name.upper().replace(" ", "")
        return f"{self.number}_{name}_{self.variant.upper()}"

    @property
    def display_name(self) -> str:
        return f"{self.number} {self.name.upper()} — {self.variant.upper()}"

    def fingerprint(self) -> str:
        blob = json.dumps(self.parameters, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    @classmethod
    def from_dict(cls, d: dict, path=None) -> "Look":
        if d.get("schema") != SCHEMA:
            raise ValueError(f"{path}: schema must be '{SCHEMA}'")
        for key in ("look_id", "number", "name", "variant", "version", "parameters"):
            if key not in d:
                raise KeyError(f"{path}: missing '{key}'")
        params = _merge(NEUTRAL_PARAMETERS, d["parameters"])
        _validate(params, path)
        return cls(d["look_id"], d["number"], d["name"], d["variant"], d["version"],
                   d.get("description", ""), params, d, Path(path) if path else None)

    @classmethod
    def from_file(cls, path) -> "Look":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), path)

    @classmethod
    def neutral(cls) -> "Look":
        return cls("00-neutral", "00", "Neutral", "standard", "1.0.0", "Identity look", copy.deepcopy(NEUTRAL_PARAMETERS), {})


def _validate(p: dict, path) -> None:
    import numpy as np

    m = np.asarray(p["color_matrix"], dtype=float)
    if m.shape != (3, 3):
        raise ValueError(f"{path}: color_matrix must be 3x3")
    if not np.allclose(m.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError(f"{path}: color_matrix rows must sum to 1 (neutral preserving), got {m.sum(axis=1)}")
    lgg = p["lift_gamma_gain"]
    for k in ("lift", "gamma", "gain"):
        if len(lgg[k]) != 3:
            raise ValueError(f"{path}: lift_gamma_gain.{k} must have 3 values")
    if min(lgg["gamma"]) <= 0 or lgg["master_gamma"] <= 0:
        raise ValueError(f"{path}: gamma must be > 0")
    if p["contrast"]["amount"] <= 0:
        raise ValueError(f"{path}: contrast.amount must be > 0")
    s = p["saturation"]
    if (s["chroma_knee"] is None) != (s["chroma_limit"] is None):
        raise ValueError(f"{path}: chroma_knee and chroma_limit must both be set or both be null")
    if s["chroma_knee"] is not None and not 0 < s["chroma_knee"] < s["chroma_limit"]:
        raise ValueError(f"{path}: need 0 < chroma_knee < chroma_limit")
    for k in ("protect", "pull"):
        if not 0.0 <= p["skin"][k] <= 1.0:
            raise ValueError(f"{path}: skin.{k} must be within [0, 1]")
    if p["highlight_compression"]["strength"] < 0:
        raise ValueError(f"{path}: highlight_compression.strength must be >= 0")


def load_looks(root, collection_looks=None) -> list:
    root = Path(root)
    looks = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or (collection_looks and d.name not in collection_looks):
            continue
        for f in sorted(d.glob("*.json")):
            looks.append(Look.from_file(f))
    return looks
