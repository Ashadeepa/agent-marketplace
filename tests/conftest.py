import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.registry import registry


@pytest.fixture(autouse=True)
def _loaded_registry():
    registry.load_from_disk()
    yield registry
