"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require database)"
    )
