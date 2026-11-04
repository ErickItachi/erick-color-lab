"""Curve primitives used by the creative stage.

* ``MonotoneCurve`` — Fritsch–Carlson monotone cubic Hermite interpolation
  (F. N. Fritsch & R. E. Carlson, SIAM J. Numer. Anal. 17(2), 1980). Used for
  RGB tone curves: guarantees no overshoot / no tonal reversals between
  control points, which prevents banding and solarisation.
* ``PeriodicCurve`` — periodic Catmull-Rom (cardinal) cubic over the hue
  circle, used by Hue-vs-Hue / Hue-vs-Sat / Hue-vs-Lum. C1 continuous,
  wraps at 360°.
* ``smoothstep`` — Hermite step used for soft range masks.
"""

from __future__ import annotations

import numpy as np


def smoothstep(edge0, edge1, x):
    """Cubic Hermite step: 0 below edge0, 1 above edge1 (edges may be reversed)."""
    x = np.asarray(x, dtype=np.float64)
    if edge1 == edge0:
        return (x >= edge0).astype(np.float64)
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class MonotoneCurve:
    """Monotone piecewise-cubic curve through control points (x_i, y_i).

    Outside [x_0, x_n] the curve continues with slope 1 (identity offset), so
    values beyond the edited range are never clipped by a curve.
    """

    def __init__(self, points):
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
            raise ValueError("curve needs at least two [x, y] points")
        order = np.argsort(pts[:, 0])
        x, y = pts[order, 0], pts[order, 1]
        if np.any(np.diff(x) <= 0):
            raise ValueError("curve x coordinates must be strictly increasing")
        if np.any(np.diff(y) < 0):
            raise ValueError("tone curves must be monotone non-decreasing (y)")
        self.x, self.y = x, y
        h = np.diff(x)
        delta = np.diff(y) / h
        m = np.empty_like(x)
        m[0], m[-1] = delta[0], delta[-1]
        m[1:-1] = (delta[:-1] + delta[1:]) / 2.0
        # Fritsch–Carlson limiter
        for i in range(len(delta)):
            if delta[i] == 0.0:
                m[i] = m[i + 1] = 0.0
            else:
                a, b = m[i] / delta[i], m[i + 1] / delta[i]
                s = a * a + b * b
                if s > 9.0:
                    t = 3.0 / np.sqrt(s)
                    m[i], m[i + 1] = t * a * delta[i], t * b * delta[i]
        self.m = m
        self.identity = bool(np.allclose(x, y) and np.allclose(m, 1.0))

    def __call__(self, v):
        v = np.asarray(v, dtype=np.float64)
        if self.identity:
            return v.copy()
        x, y, m = self.x, self.y, self.m
        out = np.empty_like(v)
        lo, hi = v < x[0], v > x[-1]
        out[lo] = y[0] + (v[lo] - x[0])
        out[hi] = y[-1] + (v[hi] - x[-1])
        mid = ~(lo | hi)
        vm = v[mid]
        i = np.clip(np.searchsorted(x, vm, side="right") - 1, 0, len(x) - 2)
        h = x[i + 1] - x[i]
        t = (vm - x[i]) / h
        t2, t3 = t * t, t * t * t
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2
        out[mid] = h00 * y[i] + h10 * h * m[i] + h01 * y[i + 1] + h11 * h * m[i + 1]
        return out


class PeriodicCurve:
    """Periodic cubic (Catmull-Rom) over hue in degrees.

    ``points``: list of [hue_degrees, value]. ``neutral`` is the value meaning
    "no change" (0 for hue shift, 1 for multipliers); an empty list returns it.
    """

    def __init__(self, points, neutral: float):
        self.neutral = float(neutral)
        pts = np.asarray(points if points else [], dtype=np.float64).reshape(-1, 2)
        if len(pts) == 0:
            self.empty = True
            return
        self.empty = False
        pts = pts[np.argsort(pts[:, 0] % 360.0)]
        self.h = pts[:, 0] % 360.0
        if np.any(np.diff(self.h) <= 0):
            raise ValueError("hue curve points must have distinct hues")
        self.v = pts[:, 1]

    def __call__(self, hue):
        hue = np.asarray(hue, dtype=np.float64) % 360.0
        if self.empty:
            return np.full_like(hue, self.neutral)
        n = len(self.h)
        if n == 1:
            return np.full_like(hue, self.v[0])
        # extended knot vector with wrap-around neighbours
        hx = np.concatenate([[self.h[-2] - 360.0, self.h[-1] - 360.0], self.h, [self.h[0] + 360.0, self.h[1] + 360.0]])
        vx = np.concatenate([[self.v[-2], self.v[-1]], self.v, [self.v[0], self.v[1]]])
        # tangents (non-uniform Catmull-Rom / finite differences)
        mt = (vx[2:] - vx[:-2]) / (hx[2:] - hx[:-2])
        hk, vk = hx[1:-1], vx[1:-1]  # knots with tangents mt
        q = np.where(hue < hk[1], hue + 360.0, hue)
        i = np.clip(np.searchsorted(hk, q, side="right") - 1, 0, len(hk) - 2)
        dh = hk[i + 1] - hk[i]
        t = (q - hk[i]) / dh
        t2, t3 = t * t, t * t * t
        return (
            (2 * t3 - 3 * t2 + 1) * vk[i]
            + (t3 - 2 * t2 + t) * dh * mt[i]
            + (-2 * t3 + 3 * t2) * vk[i + 1]
            + (t3 - t2) * dh * mt[i + 1]
        )
