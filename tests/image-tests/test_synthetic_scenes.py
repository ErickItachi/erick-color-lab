"""Synthetic test scenes and end-to-end LUT application on them."""

import numpy as np
import pytest

from erick_color_lab.imaging.synthetic import SCENES, colorchecker_ap1, skin_patches
from erick_color_lab.lut_baking.cube import bake
from erick_color_lab.interpolation.lut3d import tetrahedral
from erick_color_lab.pipeline import Transform
from erick_color_lab.transforms import colorspaces as cs


@pytest.mark.parametrize("name", list(SCENES))
def test_scenes_are_finite(name):
    img = SCENES[name]()
    assert img.ndim == 3 and img.shape[-1] == 3 and np.all(np.isfinite(img))


def test_colorchecker_reference_values():
    names, ap1 = colorchecker_ap1()
    y = ap1 @ cs.luminance_weights("ap1")
    # neutral 5 (.70 D) has Y ~ 0.19 (X-Rite 2014 reference data via colour-science)
    assert 0.17 < y[names.index("neutral 5 (.70 D)")] < 0.21
    g = ap1[names.index("neutral 5 (.70 D)")]
    assert np.ptp(g) / g.mean() < 0.02  # near-neutral after D50 -> D65 adaptation


def test_skin_proxies_have_skin_hue():
    lab = cs.rec709_linear_to_oklab(cs.convert(skin_patches(), "ap1", "rec709"))
    _, _, h = cs.oklab_to_lch(lab)
    assert np.all((h > 25) & (h < 60))


def test_lut_on_scene_matches_pipeline(rendering, profiles, looks):
    """Encode a scene as S-Log3, apply a baked 65^3 LUT, compare to the exact pipeline."""
    look = [lk for lk in looks if lk.look_id == "01-signature" and lk.variant == "standard"][0]
    T = Transform(look, profiles["slog3_sgamut3cine"], rendering)
    table = bake(T, 65)
    scene = SCENES["colorchecker"]()
    sig = np.clip(T.profile.from_scene_ap1(scene.reshape(-1, 3)), 0, 1)
    np.testing.assert_allclose(tetrahedral(table, sig), np.clip(T(sig), 0, 1), atol=4e-3)
