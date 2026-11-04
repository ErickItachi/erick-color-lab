"""CINÉRA display tone scale (scene-linear -> display-linear), invertible.

Form (after the open-source ACES 2.0 tonescale by D. Siragusano; parameters
are our own design choices, not a standard):

    h(x)  = (x / (x + s0)) ** p                 # Michaelis–Menten compression
    t(h)  = h**2 / (h + toe)                    # toe / flare compensation
    f(x)  = min( t(h(x)) / t(h(W)), 1 )         # normalised: f(W) = 1

* ``p``     ("contrast") controls mid-tone slope.
* ``toe``   deepens the darkest tones smoothly (rich blacks without clipping).
* ``W``     scene white: 0.18 * 2**white_stops maps exactly to display 1.0.
* ``s0`` is solved so that f(grey_in) = grey_out.

The curve is applied odd-symmetrically (f(-x) = -f(x)).
Highlight roll-off is intrinsic: the slope tends smoothly to ~0 at W.
The inverse is closed-form, so Rec.709 footage can be mapped back to scene
values (used by the Rec.709 profile), and forward(inverse(v)) == v.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ToneScale:
    grey_in: float = 0.18
    grey_out: float = 0.115
    contrast: float = 1.18
    toe: float = 0.012
    white_stops: float = 6.5

    def __post_init__(self):
        if not (0 < self.grey_out < 1 and self.contrast > 0 and self.toe >= 0 and self.white_stops > 0):
            raise ValueError("invalid tone scale parameters")
        object.__setattr__(self, "W", self.grey_in * 2.0 ** self.white_stops)
        object.__setattr__(self, "s0", self._solve_s0())
        object.__setattr__(self, "norm", self._t(self._h(self.W, self.s0)))

    # -- pieces -----------------------------------------------------------
    def _h(self, x, s0):
        x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
        return (x / (x + s0)) ** self.contrast

    def _t(self, h):
        return h * h / (h + self.toe) if self.toe > 0 else h

    def _solve_s0(self) -> float:
        lo, hi = 1e-6, 1e3  # ratio f(grey)/f(W) is monotone decreasing in s0

        def ratio(s0):
            return self._t(self._h(self.grey_in, s0)) / self._t(self._h(self.W, s0))

        for _ in range(200):
            mid = np.sqrt(lo * hi)
            if ratio(mid) > self.grey_out:
                lo = mid
            else:
                hi = mid
        return float(np.sqrt(lo * hi))

    # -- public -----------------------------------------------------------
    def forward(self, x):
        """Odd-symmetric: f(-x) = -f(x). Negative values (out-of-gamut colour
        components) stay invertible; the display clip removes them at the end."""
        x = np.asarray(x, dtype=np.float64)
        a = np.abs(x)
        y = np.minimum(self._t(self._h(a, self.s0)) / self.norm, 1.0)
        return np.sign(x) * y

    def inverse(self, y):
        y = np.asarray(y, dtype=np.float64)
        sgn = np.sign(y)
        a = np.clip(np.abs(y), 0.0, 1.0) * self.norm
        if self.toe > 0:
            h = (a + np.sqrt(a * a + 4.0 * a * self.toe)) / 2.0
        else:
            h = a
        r = np.clip(h, 0.0, 1.0 - 1e-15) ** (1.0 / self.contrast)
        return sgn * self.s0 * r / (1.0 - r)

    @classmethod
    def from_dict(cls, d: dict) -> "ToneScale":
        return cls(**{k: float(v) for k, v in d.items()})
