"""3D LUT baking and the .cube file format.

Format: Adobe/IRIDAS ".cube" (Adobe "Cube LUT Specification 1.0", 2013),
the format read by DaVinci Resolve and Adobe Premiere Pro (Lumetri).

* ``LUT_3D_SIZE N`` with N**3 lines of "R G B", **red index varying fastest**.
* ``DOMAIN_MIN`` / ``DOMAIN_MAX`` = 0..1 (the spec defaults, written explicitly).
* Header comments are ASCII only (some hosts reject UTF-8 in .cube files).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DECIMALS = 6


def lattice(size: int) -> np.ndarray:
    """Input lattice in file order: shape (size**3, 3), red fastest."""
    t = np.linspace(0.0, 1.0, size)
    b, g, r = np.meshgrid(t, t, t, indexing="ij")
    return np.stack([r.ravel(), g.ravel(), b.ravel()], axis=-1)


def bake(transform, size: int, clip: bool = True) -> np.ndarray:
    """Evaluate ``transform`` on the lattice. Returns (size, size, size, 3)
    indexed [b, g, r] (file order), output clipped to [0, 1] by default."""
    out = np.asarray(transform(lattice(size)), dtype=np.float64)
    if not np.all(np.isfinite(out)):
        raise ValueError("transform produced NaN/Inf values")
    if clip:
        out = np.clip(out, 0.0, 1.0)
    return out.reshape(size, size, size, 3)


@dataclass
class CubeLUT:
    table: np.ndarray  # (N, N, N, 3) indexed [b, g, r]
    title: str = ""
    comments: list = field(default_factory=list)
    domain_min: tuple = (0.0, 0.0, 0.0)
    domain_max: tuple = (1.0, 1.0, 1.0)

    @property
    def size(self) -> int:
        return self.table.shape[0]


def _ascii(s: str) -> str:
    repl = {"É": "E", "é": "e", "—": "-", "–": "-", "→": "->", "⁻¹": "^-1", "·": "-", "°": " deg"}
    for k, v in repl.items():
        s = s.replace(k, v)
    return s.encode("ascii", "replace").decode("ascii")


def write_cube(path, lut: CubeLUT) -> str:
    """Write a .cube file; returns its SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in lut.comments:
        lines.append("# " + _ascii(c))
    lines.append(f'TITLE "{_ascii(lut.title)}"')
    lines.append(f"LUT_3D_SIZE {lut.size}")
    lines.append("DOMAIN_MIN {:.1f} {:.1f} {:.1f}".format(*lut.domain_min))
    lines.append("DOMAIN_MAX {:.1f} {:.1f} {:.1f}".format(*lut.domain_max))
    data = lut.table.reshape(-1, 3)
    fmt = f"%.{DECIMALS}f %.{DECIMALS}f %.{DECIMALS}f"
    body = "\n".join(fmt % tuple(row) for row in data)
    text = "\n".join(lines) + "\n" + body + "\n"
    path.write_text(text, encoding="ascii", newline="\n")
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class CubeFormatError(ValueError):
    pass


def read_cube(path) -> CubeLUT:
    """Strict .cube reader (used to re-import and validate every export)."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CubeFormatError(f"{path.name}: non-ASCII content") from exc
    size = None
    title = ""
    comments, rows = [], []
    dmin, dmax = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    num = re.compile(r"^[-+0-9.eE]")
    for ln, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            comments.append(s[1:].strip())
            continue
        if num.match(s):
            parts = s.split()
            if len(parts) != 3:
                raise CubeFormatError(f"{path.name}:{ln}: expected 3 values")
            rows.append([float(v) for v in parts])
            continue
        key, _, rest = s.partition(" ")
        if rows:
            raise CubeFormatError(f"{path.name}:{ln}: keyword after data")
        if key == "TITLE":
            title = rest.strip().strip('"')
        elif key == "LUT_3D_SIZE":
            size = int(rest)
        elif key == "DOMAIN_MIN":
            dmin = tuple(float(v) for v in rest.split())
        elif key == "DOMAIN_MAX":
            dmax = tuple(float(v) for v in rest.split())
        elif key == "LUT_1D_SIZE":
            raise CubeFormatError(f"{path.name}: 1D LUTs are not expected here")
        else:
            raise CubeFormatError(f"{path.name}:{ln}: unknown keyword {key}")
    if size is None:
        raise CubeFormatError(f"{path.name}: missing LUT_3D_SIZE")
    if not 2 <= size <= 256:
        raise CubeFormatError(f"{path.name}: LUT_3D_SIZE {size} outside 2..256")
    if len(rows) != size ** 3:
        raise CubeFormatError(f"{path.name}: expected {size**3} rows, found {len(rows)}")
    table = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(table)):
        raise CubeFormatError(f"{path.name}: NaN/Inf in table")
    return CubeLUT(table.reshape(size, size, size, 3), title, comments, dmin, dmax)
