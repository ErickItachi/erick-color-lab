"""Camera input transforms vs OpenColorIO builtins (independent implementation).

OCIO's camera builtins go to ACES2065-1 (AP0) using each manufacturer's
published IDT matrices. Sony and Canon matrices correspond to CAT02
adaptation, Apple's to Bradford; we compare with the matching adaptation.
The engine itself uses CAT02 throughout — that adaptation only converts D65 <->
ACES white and cancels out on the way back to Rec.709 (tested below).
"""

import numpy as np
import pytest
from ocio_helpers import ocio_builtin, requires_ocio

from erick_color_lab.transforms import colorspaces as cs
from erick_color_lab.transforms import transfer as tf

CASES = [
    ("slog3_sgamut3cine", "sony_slog3", "sgamut3cine", "SONY_SLOG3-SGAMUT3.CINE_to_ACES2065-1", "CAT02", 2e-3),
    ("slog3_sgamut3", "sony_slog3", "sgamut3", "SONY_SLOG3-SGAMUT3_to_ACES2065-1", "CAT02", 2e-3),
    ("clog3_cinemagamut", "canon_log3", "cinema_gamut", "CANON_CLOG3-CGAMUT_to_ACES2065-1", "CAT02", 5e-4),
    ("applelog_bt2020", "apple_log", "rec2020", "APPLE_LOG_to_ACES2065-1", "Bradford", 1e-4),
]


@requires_ocio
@pytest.mark.parametrize("pid,tf_id,gamut,builtin,cat,rtol", CASES)
def test_camera_to_aces_matches_ocio(pid, tf_id, gamut, builtin, cat, rtol):
    rng = np.random.default_rng(0)
    code = rng.uniform(0.15, 0.85, (4000, 3))  # full-scale CV/1023 (formula domain)
    ref = ocio_builtin(builtin, code)
    lin = tf.TRANSFER_FUNCTIONS[tf_id]["decode"](code)
    ours = cs.convert(lin, gamut, "ap0", cat=cat)
    rel = np.abs(ours - ref) / np.maximum(np.abs(ref), 1e-2)
    assert rel.max() < rtol, rel.max()


@pytest.mark.parametrize("pid", ["slog3_sgamut3cine", "slog3_sgamut3", "clog3_cinemagamut", "applelog_bt2020"])
def test_profile_neutral_grey(profiles, pid):
    """18 % grey recorded by the camera decodes to AP1 (0.18, 0.18, 0.18)."""
    p = profiles[pid]
    cv = tf.TRANSFER_FUNCTIONS[p.transfer]["encode"](np.array([0.18]))[0]
    v = (cv * 1023 - 64) / 876  # as presented by the host in video range
    ap1 = p.to_scene_ap1(np.array([[v, v, v]]))[0]
    np.testing.assert_allclose(ap1, 0.18, rtol=1e-5)


def test_cat_cancels_for_neutrals():
    m = cs.rgb_to_rgb_matrix("ap1", "rec709") @ cs.rgb_to_rgb_matrix("rec709", "ap1")
    np.testing.assert_allclose(m, np.eye(3), atol=1e-12)
    for g in ["sgamut3", "sgamut3cine", "cinema_gamut", "rec2020"]:
        np.testing.assert_allclose(cs.convert(np.ones(3), g, "ap1"), 1.0, atol=1e-9)


@requires_ocio
def test_acescct_curve_matches_ocio():
    code = np.linspace(0.0, 1.0, 256)
    ref = ocio_builtin("CURVE - ACEScct-LOG_to_LINEAR", np.repeat(code[:, None], 3, 1))[:, 0]
    np.testing.assert_allclose(tf.acescct_decode(code), ref, rtol=2e-5, atol=1e-7)


def test_profiles_declare_input_and_output(profiles):
    for p in profiles.values():
        for key in ("label", "kind", "transfer", "gamut", "signal", "references", "verification"):
            assert key in p.raw, (p.id, key)
