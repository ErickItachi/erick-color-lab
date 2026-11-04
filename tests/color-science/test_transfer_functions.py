"""Log curves and display encodings vs published values and OpenColorIO."""

import numpy as np
import pytest
from ocio_helpers import ocio_builtin, requires_ocio

from erick_color_lab.transforms import transfer as tf


def test_slog3_published_code_values():
    # Sony technical summary: 0 % -> 95, 18 % -> 420, 90 % -> 598 (10-bit CV)
    cv = tf.TRANSFER_FUNCTIONS["sony_slog3"]["encode"](np.array([0.0, 0.18, 0.90])) * 1023
    np.testing.assert_allclose(cv, [95, 420, 598], atol=0.5)


def test_slog3_video_range_mapping():
    # The host presents CV 420 as (420 - 64) / 876 in video range.
    v = (420 - 64) / 876
    assert tf.decode(np.array([v]), "sony_slog3", "video")[0] == pytest.approx(0.18, rel=1e-6)
    assert tf.decode(np.array([420 / 1023]), "sony_slog3", "full")[0] == pytest.approx(0.18, rel=1e-6)


@pytest.mark.parametrize("tf_id", ["sony_slog3", "canon_log3", "apple_log", "acescct", "bt1886"])
def test_encode_decode_roundtrip(tf_id):
    x = np.concatenate([np.linspace(0.0, 1.0, 101), [2.0, 8.0, 16.0]])
    if tf_id == "bt1886":
        x = np.linspace(0, 1, 101)
    y = tf.TRANSFER_FUNCTIONS[tf_id]["encode"](x)
    np.testing.assert_allclose(tf.TRANSFER_FUNCTIONS[tf_id]["decode"](y), x, rtol=1e-6, atol=1e-7)


@requires_ocio
@pytest.mark.parametrize("tf_id", ["canon_log3", "apple_log", "acescct"])
def test_log_curves_match_ocio(tf_id):
    name = tf.TRANSFER_FUNCTIONS[tf_id]["ocio_curve"]
    code = np.linspace(0.1, 0.95, 512)
    ref = ocio_builtin(name, np.repeat(code[:, None], 3, 1))[:, 0]
    ours = tf.TRANSFER_FUNCTIONS[tf_id]["decode"](code)
    np.testing.assert_allclose(ours, ref, rtol=2e-5, atol=2e-6)


def test_canon_log3_grey():
    # Canon Log 3 v1.2: 18 % reflection -> 0.3434 (CV/1023, legal-range constants)
    assert tf.TRANSFER_FUNCTIONS["canon_log3"]["encode"](np.array([0.18]))[0] == pytest.approx(0.343389, abs=1e-5)


def test_apple_log_grey():
    assert tf.TRANSFER_FUNCTIONS["apple_log"]["encode"](np.array([0.18]))[0] == pytest.approx(0.488272, abs=1e-5)


def test_acescct_grey_and_black():
    enc = tf.TRANSFER_FUNCTIONS["acescct"]["encode"](np.array([0.0, 0.18]))
    np.testing.assert_allclose(enc, [0.0729055341958355, 0.4135884], atol=1e-6)


@requires_ocio
def test_bt1886_rec709_display_matches_ocio():
    import colour

    rng = np.random.default_rng(3)
    lin = rng.uniform(0, 1, (2000, 3))
    xyz = colour.RGB_to_XYZ(lin, colour.RGB_COLOURSPACES["ITU-R BT.709"], apply_cctf_decoding=False)
    ref = ocio_builtin("DISPLAY - CIE-XYZ-D65_to_REC.1886-REC.709", xyz)
    np.testing.assert_allclose(tf.bt1886_inverse_eotf(lin), ref, atol=2e-5)
