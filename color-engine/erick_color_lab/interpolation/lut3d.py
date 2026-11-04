"""3D LUT application: trilinear and tetrahedral interpolation.

Tetrahedral interpolation is what DaVinci Resolve offers by default and what
most hosts use; trilinear is the simpler reference. Both are used to verify
exported files against the analytic pipeline. Table indexing is [b, g, r]
(the .cube file order).
"""

from __future__ import annotations

import numpy as np


def _prepare(table, rgb):
    n = table.shape[0]
    x = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 1.0) * (n - 1)
    i0 = np.clip(np.floor(x).astype(np.int64), 0, n - 2)
    f = x - i0
    return n, i0, f


def _at(table, r, g, b):
    return table[b, g, r]


def trilinear(table: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    shape = np.shape(rgb)
    rgb = np.reshape(rgb, (-1, 3))
    _, i0, f = _prepare(table, rgb)
    r0, g0, b0 = i0.T
    fr, fg, fb = (f[:, k : k + 1] for k in range(3))
    c000 = _at(table, r0, g0, b0)
    c100 = _at(table, r0 + 1, g0, b0)
    c010 = _at(table, r0, g0 + 1, b0)
    c110 = _at(table, r0 + 1, g0 + 1, b0)
    c001 = _at(table, r0, g0, b0 + 1)
    c101 = _at(table, r0 + 1, g0, b0 + 1)
    c011 = _at(table, r0, g0 + 1, b0 + 1)
    c111 = _at(table, r0 + 1, g0 + 1, b0 + 1)
    c00 = c000 * (1 - fr) + c100 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c11 = c011 * (1 - fr) + c111 * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    return (c0 * (1 - fb) + c1 * fb).reshape(shape)


def tetrahedral(table: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    shape = np.shape(rgb)
    rgb = np.reshape(rgb, (-1, 3))
    _, i0, f = _prepare(table, rgb)
    r0, g0, b0 = i0.T
    fr, fg, fb = f.T
    c000 = _at(table, r0, g0, b0)
    c111 = _at(table, r0 + 1, g0 + 1, b0 + 1)
    out = np.empty_like(rgb)

    def put(mask, a, b, wa, wb, wc):
        # c = c000 + wa*(A-c000) + wb*(B-A) + wc*(c111-B)
        A = _at(table, *a)
        B = _at(table, *b)
        out[mask] = (c000[mask] + wa[mask, None] * (A[mask] - c000[mask])
                     + wb[mask, None] * (B[mask] - A[mask]) + wc[mask, None] * (c111[mask] - B[mask]))

    R1, G1, B1 = r0 + 1, g0 + 1, b0 + 1
    m1 = (fr >= fg) & (fg >= fb)
    m2 = (fr >= fb) & (fb > fg)
    m3 = (fb > fr) & (fr >= fg)
    m4 = (fg > fr) & (fr >= fb)
    m5 = (fg >= fb) & (fb > fr)
    m6 = ~(m1 | m2 | m3 | m4 | m5)  # fb > fg > fr
    put(m1, (R1, g0, b0), (R1, G1, b0), fr, fg, fb)
    put(m2, (R1, g0, b0), (R1, g0, B1), fr, fb, fg)
    put(m3, (r0, g0, B1), (R1, g0, B1), fb, fr, fg)
    put(m4, (r0, G1, b0), (R1, G1, b0), fg, fr, fb)
    put(m5, (r0, G1, b0), (r0, G1, B1), fg, fb, fr)
    put(m6, (r0, g0, B1), (r0, G1, B1), fb, fg, fr)
    return out.reshape(shape)


def apply(table: np.ndarray, rgb: np.ndarray, method: str = "tetrahedral") -> np.ndarray:
    return tetrahedral(table, rgb) if method == "tetrahedral" else trilinear(table, rgb)
