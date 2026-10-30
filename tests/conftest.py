import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import decoy_state  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_decoy_state():
    decoy_state.reset()
    yield
    decoy_state.reset()
