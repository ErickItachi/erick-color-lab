"""Creative operators, curves, Oklab and look files."""

import copy
import json

import colour
import numpy as np
import pytest

from erick_color_lab.creative.look import NEUTRAL_PARAMETERS, Look
from erick_color_lab.creative.operators import apply_look
from erick_color_lab.curves.spline import MonotoneCurve, PeriodicCurve
from erick_color_lab.transforms import colorspaces as cs


def test_oklab_matches_colour_science():
    rng = np.random.default_rng(0)
    rgb = rng.uniform(0, 1, (1000, 3))
    xyz = colour.RGB_to_XYZ(rgb, colour.RGB_COLOURSPACES["ITU-R BT.709"], apply_cctf_decoding=False)
    np.testing.assert_allclose(cs.rec709_linear_to_oklab(rgb), colour.XYZ_to_Oklab(xyz), atol=2e-4)
    np.testing.assert_allclose(cs.oklab_to_rec709_linear(cs.rec709_linear_to_oklab(rgb)), rgb, atol=1e-9)


def test_neutral_look_is_identity():
    x = np.random.default_rng(1).uniform(-0.01, 4.0, (20000, 3))
    np.testing.assert_allclose(apply_look(x, Look.neutral()), x, atol=1e-10)


def test_monotone_curve_has_no_overshoot():
    c = MonotoneCurve([[0, 0], [0.3, 0.29], [0.31, 0.6], [1, 1]])
    x = np.linspace(-0.2, 1.2, 10001)
    y = c(x)
    assert np.all(np.diff(y) >= -1e-12)
    np.testing.assert_allclose(c(np.array([0, 0.3, 0.31, 1.0])), [0, 0.29, 0.6, 1.0])
    np.testing.assert_allclose(c(np.array([1.1])), [1.1])  # identity slope outside


def test_monotone_curve_rejects_decreasing():
    with pytest.raises(ValueError):
        MonotoneCurve([[0, 0], [0.5, 0.6], [1, 0.4]])


def test_periodic_curve_wraps_continuously():
    c = PeriodicCurve([[30, 5], [140, -8], [250, 3]], 0.0)
    a = c(np.array([359.999, 0.0, 0.001]))
    assert np.ptp(a) < 1e-2
    np.testing.assert_allclose(c(np.array([30.0, 140.0, 250.0])), [5, -8, 3], atol=1e-9)


def test_unknown_parameter_rejected():
    d = {"schema": "erick-color-lab/look@1", "look_id": "x", "number": "99", "name": "X",
         "variant": "standard", "version": "1.0.0", "parameters": {"contrastt": 1.1}}
    with pytest.raises(KeyError):
        Look.from_dict(d)


def test_matrix_rows_must_preserve_neutral():
    d = {"schema": "erick-color-lab/look@1", "look_id": "x", "number": "99", "name": "X", "variant": "standard",
         "version": "1.0.0", "parameters": {"color_matrix": [[1.1, 0, 0], [0, 1, 0], [0, 0, 1]]}}
    with pytest.raises(ValueError):
        Look.from_dict(d)


def test_every_operator_changes_output():
    """Each documented parameter has a real effect (no dead parameters)."""
    x = np.random.default_rng(2).uniform(0.001, 2.0, (4000, 3))
    edits = {
        "exposure": 0.5,
        "white_balance": {"warmth": 0.2, "tint": 0.1},
        "black_offset": -0.003,
        "color_matrix": [[0.9, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.1, 0.9]],
        "contrast": {"amount": 1.2, "pivot": 0.4136, "hue_preservation": 0.5},
        "lift_gamma_gain": {"master_lift": 0.02, "gamma": [1.1, 1.0, 0.9]},
        "tonal_balance": {"shadows": [0.01, 0, -0.01]},
        "curves": {"master": [[0.0729, 0.0729], [0.4, 0.38], [1.0, 1.0]]},
        "highlight_compression": {"threshold": 0.5, "strength": 3.0},
        "color_separation": {"amount": 10.0},
        "hue_vs_hue": [[140, -10]],
        "hue_vs_sat": [[140, 0.5]],
        "hue_vs_lum": [[250, 0.8]],
        "saturation": {"global": 0.8},
        "skin": {"pull": 0.5},
    }
    for k, v in edits.items():
        p = copy.deepcopy(NEUTRAL_PARAMETERS)
        p[k] = v if not isinstance(v, dict) else {**p[k], **v}
        look = Look("t", "99", "T", "standard", "1", "", p, {})
        assert np.abs(apply_look(x, look) - x).max() > 1e-4, k


def test_skin_protection_reduces_skin_change():
    from erick_color_lab.imaging.synthetic import skin_patches

    skin = skin_patches()
    base = copy.deepcopy(NEUTRAL_PARAMETERS)
    base["hue_vs_hue"] = [[45, 15]]
    base["hue_vs_sat"] = [[45, 0.5]]
    loose = Look("t", "99", "T", "standard", "1", "", copy.deepcopy(base), {})
    base["skin"]["protect"] = 1.0
    tight = Look("t", "99", "T", "standard", "1", "", base, {})

    def dhue(look):
        _, _, h0 = cs.oklab_to_lch(cs.rec709_linear_to_oklab(cs.convert(skin, "ap1", "rec709")))
        _, _, h1 = cs.oklab_to_lch(cs.rec709_linear_to_oklab(cs.convert(apply_look(skin, look), "ap1", "rec709")))
        return np.abs((h1 - h0 + 180) % 360 - 180).mean()

    assert dhue(tight) < 0.35 * dhue(loose)


def test_all_look_files_load(repo):
    files = sorted((repo / "looks").glob("*/*.json"))
    assert files
    for f in files:
        Look.from_file(f)
        assert json.loads(f.read_text())["schema"] == "erick-color-lab/look@1"
