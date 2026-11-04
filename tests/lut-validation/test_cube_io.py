""".cube format, interpolation and baked-file validation."""

import json

import numpy as np
import pytest

from erick_color_lab.interpolation.lut3d import tetrahedral, trilinear
from erick_color_lab.lut_baking.cube import CubeFormatError, CubeLUT, bake, lattice, read_cube, write_cube


def test_lattice_red_fastest():
    lat = lattice(3)
    np.testing.assert_allclose(lat[:4], [[0, 0, 0], [0.5, 0, 0], [1, 0, 0], [0, 0.5, 0]])


def test_write_read_roundtrip(tmp_path):
    table = bake(lambda x: x ** 0.8, 17)
    p = tmp_path / "t.cube"
    write_cube(p, CubeLUT(table, "TEST", ["comment é"]))
    lut = read_cube(p)
    assert lut.size == 17 and lut.title == "TEST"
    np.testing.assert_allclose(lut.table, table, atol=5e-7)
    p.read_text(encoding="ascii")  # ASCII only


@pytest.mark.parametrize("fn", [tetrahedral, trilinear])
def test_identity_lut_is_exact(fn):
    table = bake(lambda x: x, 9)
    x = np.random.default_rng(0).uniform(0, 1, (5000, 3))
    np.testing.assert_allclose(fn(table, x), x, atol=1e-12)


def test_tetrahedral_reproduces_linear_maps():
    m = np.array([[0.8, 0.1, 0.1], [0.2, 0.7, 0.1], [0.0, 0.3, 0.7]])
    table = bake(lambda x: x @ m.T, 5, clip=False)
    x = np.random.default_rng(1).uniform(0, 1, (5000, 3))
    np.testing.assert_allclose(tetrahedral(table, x), x @ m.T, atol=1e-12)


def test_reader_rejects_bad_files(tmp_path):
    p = tmp_path / "bad.cube"
    p.write_text("LUT_3D_SIZE 2\n0 0 0\n1 1 1\n")
    with pytest.raises(CubeFormatError):
        read_cube(p)
    p.write_text("LUT_3D_SIZE 2\n" + "0 0 nan\n" * 8)
    with pytest.raises((CubeFormatError, ValueError)):
        read_cube(p)


def test_manifest_matches_files(repo):
    """If the collection has been built locally, every file must match the manifest."""
    import hashlib

    man = repo / "exports/cinera-vol-01/MANIFEST.json"
    if not man.exists():
        pytest.skip("manifest not present")
    files = json.loads(man.read_text())["files"]
    present = [k for k in files if (repo / k).exists()]
    if not present:
        pytest.skip("collection not built locally (run scripts/build_luts.py)")
    for k in present:
        assert hashlib.sha256((repo / k).read_bytes()).hexdigest() == files[k]["sha256"], k
