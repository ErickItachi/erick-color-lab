"""Gamut compression, tone scale and rendering properties."""

import numpy as np
from ocio_helpers import ocio_builtin, requires_ocio

from erick_color_lab.creative.look import Look
from erick_color_lab.curves.tonescale import ToneScale
from erick_color_lab.gamut.compression import ACES_RGC
from erick_color_lab.pipeline import Transform
from erick_color_lab.transforms import colorspaces as cs


@requires_ocio
def test_rgc_matches_ocio_aces_lmt():
    rng = np.random.default_rng(1)
    ap0 = rng.uniform(-0.3, 2.0, (5000, 3))
    ref = ocio_builtin("ACES-LMT - ACES 1.3 Reference Gamut Compression", ap0)
    ours = cs.convert(ACES_RGC.forward(cs.convert(ap0, "ap0", "ap1")), "ap1", "ap0")
    np.testing.assert_allclose(ours, ref, atol=2e-6)


def test_rgc_inverse():
    rng = np.random.default_rng(2)
    x = rng.uniform(-0.2, 2.0, (5000, 3))
    np.testing.assert_allclose(ACES_RGC.inverse(ACES_RGC.forward(x)), x, atol=1e-9)


def test_display_compression_folds_ap1_into_rec709(rendering):
    t = np.linspace(0, 1, 33)
    a, b = np.meshgrid(t, t)
    surf = []
    for ax in range(3):
        for v in (0.0, 1.0):
            f = np.zeros((a.size, 3))
            o = [i for i in range(3) if i != ax]
            f[:, ax], f[:, o[0]], f[:, o[1]] = v, a.ravel(), b.ravel()
            surf.append(f)
    surf = np.concatenate(surf)
    out = rendering.display_rgc.forward(cs.convert(surf, "ap1", "rec709"))
    assert out.min() > -1e-6


def test_tonescale_anchors_and_monotonic():
    ts = ToneScale()
    assert ts.forward(np.array([0.18]))[0] == np.float64(0.115) or abs(ts.forward(np.array([0.18]))[0] - 0.115) < 1e-9
    assert abs(ts.forward(np.array([ts.W]))[0] - 1.0) < 1e-12
    x = 0.18 * 2.0 ** np.linspace(-12, 6.5, 5000)
    y = ts.forward(x)
    assert np.all(np.diff(y) > 0)
    np.testing.assert_allclose(ts.forward(ts.inverse(y)), y, atol=1e-12)
    np.testing.assert_allclose(ts.forward(-x), -y)  # odd symmetry


def test_rec709_roundtrip_identity(rendering, profiles):
    """Neutral look on the Rec.709 profile is an exact identity."""
    T = Transform(Look.neutral(), profiles["rec709_bt1886"], rendering)
    rng = np.random.default_rng(5)
    x = np.concatenate([rng.uniform(0, 1, (100000, 3)),
                        np.stack(np.meshgrid(*[np.linspace(0, 1, 17)] * 3), -1).reshape(-1, 3)])
    np.testing.assert_allclose(T(x), x, atol=1e-6)


def test_acescct_neutral_is_identity(rendering, profiles):
    T = Transform(Look.neutral(), profiles["acescct_ap1"], rendering)
    x = np.random.default_rng(6).uniform(0, 1, (20000, 3))
    np.testing.assert_allclose(T(x), x, atol=1e-9)


def test_camera_neutral_grey_renders_neutral(rendering, profiles):
    """18 % grey from every camera renders to the same neutral display grey."""
    from erick_color_lab.transforms import transfer as tf

    outs = []
    for pid in ["slog3_sgamut3cine", "slog3_sgamut3", "clog3_cinemagamut", "applelog_bt2020"]:
        p = profiles[pid]
        cv = tf.TRANSFER_FUNCTIONS[p.transfer]["encode"](np.array([0.18]))[0]
        v = (cv * 1023 - 64) / 876
        outs.append(Transform(Look.neutral(), p, rendering)(np.array([[v, v, v]]))[0])
    outs = np.array(outs)
    np.testing.assert_allclose(outs, 0.115 ** (1 / 2.4), atol=1e-5)
