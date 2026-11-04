"""Shared OpenColorIO helpers for the test-suite."""

import numpy as np
import pytest

try:
    import PyOpenColorIO as ocio  # noqa: F401

    HAVE_OCIO = True
except Exception:  # pragma: no cover
    HAVE_OCIO = False

requires_ocio = pytest.mark.skipif(not HAVE_OCIO, reason="OpenColorIO not installed")


def ocio_builtin(name, rgb, inverse=False):
    import PyOpenColorIO as ocio

    cfg = ocio.Config.CreateRaw()
    t = ocio.BuiltinTransform(name)
    if inverse:
        t.setDirection(ocio.TRANSFORM_DIR_INVERSE)
    proc = cfg.getProcessor(t).getDefaultCPUProcessor()
    a = np.ascontiguousarray(np.asarray(rgb, dtype=np.float32).reshape(-1, 3)).copy()
    proc.applyRGB(a)
    return a.astype(np.float64).reshape(np.shape(rgb))
