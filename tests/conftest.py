"""Shared fixtures."""
from __future__ import annotations

import pytest

from ziptag.fonts import available_fonts, load_font


@pytest.fixture(scope="session")
def fonts():
    return available_fonts()


@pytest.fixture(scope="session")
def roboto(fonts):
    return load_font(fonts["Roboto"])
