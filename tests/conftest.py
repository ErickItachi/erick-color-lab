import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "color-engine"))

@pytest.fixture(scope="session")
def repo():
    return REPO


@pytest.fixture(scope="session")
def collection():
    from erick_color_lab.collection import load_collection

    return load_collection()


@pytest.fixture(scope="session")
def rendering(collection):
    return collection[1]


@pytest.fixture(scope="session")
def profiles(collection):
    return collection[2]


@pytest.fixture(scope="session")
def looks(collection):
    return collection[3]
