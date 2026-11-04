"""Transfer functions (log curves, display encodings) and signal ranges.

Every log curve is delegated to colour-science, whose implementations follow
the manufacturer documents (see ``TRANSFER_FUNCTIONS[...]['reference']``).
The tests cross-check each curve against the corresponding OpenColorIO 2.x
builtin and against published code values (e.g. S-Log3 18% grey = 420 CV).

Signal range
------------
Host applications (DaVinci Resolve with clip data levels "Auto/Video",
Premiere Pro) present video-range camera files to a LUT as normalised values
where code value 64 -> 0.0 and 940 -> 1.0 ("video" range). The log formulas,
however, are defined on full-scale code values (CV / 1023). ``signal_to_cv``
performs that explicit, documented mapping. Profiles declare which range they
expect; "full" is available for clips interpreted as full data levels.
"""

from __future__ import annotations

import warnings

import colour
import numpy as np

_BLACK_10 = 64.0
_WHITE_10 = 940.0
_MAX_10 = 1023.0


def video_to_full(v: np.ndarray) -> np.ndarray:
    """Video-range normalised value (64->0, 940->1) to full-scale CV/1023."""
    return (_BLACK_10 + (_WHITE_10 - _BLACK_10) * np.asarray(v, dtype=np.float64)) / _MAX_10


def full_to_video(cv: np.ndarray) -> np.ndarray:
    return (np.asarray(cv, dtype=np.float64) * _MAX_10 - _BLACK_10) / (_WHITE_10 - _BLACK_10)


def _quiet(fn):
    def wrapper(x, *a, **k):
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            return np.asarray(fn(np.asarray(x, dtype=np.float64), *a, **k), dtype=np.float64)

    wrapper.__name__ = getattr(fn, "__name__", "tf")
    return wrapper


# --- Display encodings ------------------------------------------------------
BT1886_GAMMA = 2.4  # ITU-R BT.1886 reference EOTF with Lb = 0 (Lw normalised to 1)


def bt1886_eotf(v: np.ndarray) -> np.ndarray:
    """ITU-R BT.1886 EOTF (Lb = 0): display-linear = V ** 2.4."""
    v = np.asarray(v, dtype=np.float64)
    return np.sign(v) * np.abs(v) ** BT1886_GAMMA


def bt1886_inverse_eotf(lin: np.ndarray) -> np.ndarray:
    lin = np.asarray(lin, dtype=np.float64)
    return np.sign(lin) * np.abs(lin) ** (1.0 / BT1886_GAMMA)


# --- Registry -----------------------------------------------------------------
# "cv_domain": True  -> the formula is defined on full-scale code values CV/1023
#              False -> the formula is defined on the nominal 0..1 signal
TRANSFER_FUNCTIONS = {
    "sony_slog3": {
        "label": "Sony S-Log3",
        "decode": _quiet(lambda y: colour.models.log_decoding_SLog3(y, in_normalised_code_value=True, out_reflection=True)),
        "encode": _quiet(lambda x: colour.models.log_encoding_SLog3(x, out_normalised_code_value=True, in_reflection=True)),
        "cv_domain": True,
        "reference": "Sony, Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3 (2014)",
        "ocio_curve": None,
    },
    "canon_log3": {
        "label": "Canon Log 3 (v1.2)",
        "decode": _quiet(lambda y: colour.models.log_decoding_CanonLog3(y, in_normalised_code_value=True, out_reflection=True, method="v1.2")),
        "encode": _quiet(lambda x: colour.models.log_encoding_CanonLog3(x, out_normalised_code_value=True, in_reflection=True, method="v1.2")),
        "cv_domain": True,
        "reference": "Canon, Canon Log Gamma Curves — Description of the Canon Log, Canon Log 2 and Canon Log 3 (2020, v1.2 constants)",
        "ocio_curve": "CURVE - CANON_CLOG3_to_LINEAR",
    },
    "apple_log": {
        "label": "Apple Log",
        "decode": _quiet(colour.models.log_decoding_AppleLogProfile),
        "encode": _quiet(colour.models.log_encoding_AppleLogProfile),
        "cv_domain": True,
        "reference": "Apple Inc., Apple Log Profile White Paper (2023)",
        "ocio_curve": "CURVE - APPLE_LOG_to_LINEAR",
    },
    "acescct": {
        "label": "ACEScct",
        "decode": _quiet(colour.models.log_decoding_ACEScct),
        "encode": _quiet(colour.models.log_encoding_ACEScct),
        "cv_domain": False,
        "reference": "Academy S-2016-001 ACEScct",
        "ocio_curve": "CURVE - ACEScct-LOG_to_LINEAR",
    },
    "bt1886": {
        "label": "ITU-R BT.1886 (gamma 2.4)",
        "decode": bt1886_eotf,
        "encode": bt1886_inverse_eotf,
        "cv_domain": False,
        "reference": "ITU-R BT.1886 (2011), Lb = 0",
        "ocio_curve": None,
    },
}


def get_transfer(tf_id: str) -> dict:
    try:
        return TRANSFER_FUNCTIONS[tf_id]
    except KeyError as exc:
        raise KeyError(f"Unknown transfer function '{tf_id}'. Known: {sorted(TRANSFER_FUNCTIONS)}") from exc


def signal_to_formula_domain(v: np.ndarray, tf_id: str, signal_range: str) -> np.ndarray:
    """Map the value a host feeds the LUT to the domain the formula expects."""
    tf = get_transfer(tf_id)
    v = np.asarray(v, dtype=np.float64)
    if signal_range == "float":
        return v
    if signal_range not in ("video", "full"):
        raise ValueError(f"signal_range must be 'video', 'full' or 'float', got {signal_range!r}")
    if tf["cv_domain"]:
        return video_to_full(v) if signal_range == "video" else v
    return v if signal_range == "video" else full_to_video(v)


def formula_domain_to_signal(y: np.ndarray, tf_id: str, signal_range: str) -> np.ndarray:
    tf = get_transfer(tf_id)
    y = np.asarray(y, dtype=np.float64)
    if signal_range == "float":
        return y
    if tf["cv_domain"]:
        return full_to_video(y) if signal_range == "video" else y
    return y if signal_range == "video" else video_to_full(y)


def decode(v: np.ndarray, tf_id: str, signal_range: str = "video") -> np.ndarray:
    """Host signal -> linear (scene reflectance, 0.18 = 18 % grey)."""
    return get_transfer(tf_id)["decode"](signal_to_formula_domain(v, tf_id, signal_range))


def encode(lin: np.ndarray, tf_id: str, signal_range: str = "video") -> np.ndarray:
    return formula_domain_to_signal(get_transfer(tf_id)["encode"](lin), tf_id, signal_range)


# Convenience for the creative module (ACEScct is the creative grading space).
def acescct_encode(lin: np.ndarray) -> np.ndarray:
    return TRANSFER_FUNCTIONS["acescct"]["encode"](lin)


def acescct_decode(cct: np.ndarray) -> np.ndarray:
    return TRANSFER_FUNCTIONS["acescct"]["decode"](cct)
