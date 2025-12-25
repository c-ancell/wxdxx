"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def spc_md_html(fixtures_dir: Path) -> str:
    """Return sample MD HTML for testing."""
    return (fixtures_dir / "md_sample.html").read_text()


@pytest.fixture
def spc_outlook_html(fixtures_dir: Path) -> str:
    """Return sample outlook HTML for testing."""
    return (fixtures_dir / "outlook_day1_sample.html").read_text()
