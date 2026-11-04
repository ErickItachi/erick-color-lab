"""ERICK COLOR LAB — color science engine.

ERICK COLOR LAB is the *tool* (engine, LUT baker, validators).
CINÉRA is the *product line* (cinematic LUT collections) built with it.

The engine separates two kinds of operations:

* **Technical transforms** (``transforms``, ``gamut``): camera log decoding,
  gamut conversion, display rendering and encoding. These only use published,
  verifiable definitions (manufacturer white papers implemented by
  colour-science, cross-checked against OpenColorIO builtins in the tests).
* **Creative transforms** (``creative``): the look itself — contrast, curves,
  balance, hue/saturation shaping, skin protection. These are artistic
  parameters stored per look/variant in JSON files under ``looks/``.
"""

from .brand import BRAND, ENGINE_NAME, ENGINE_VERSION

__all__ = ["BRAND", "ENGINE_NAME", "ENGINE_VERSION"]
__version__ = ENGINE_VERSION
