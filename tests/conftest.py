from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag_leads.config import Settings, load_settings  # noqa: E402


@pytest.fixture
def mock_settings() -> Settings:
    return load_settings(mode="mock")
