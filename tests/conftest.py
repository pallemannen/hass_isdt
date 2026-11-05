"""Fixtures for the ISDT charger tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.isdt.api import ChargerInfo
from custom_components.isdt.const import DOMAIN

from .replay import load_polls

pytest_plugins = "pytest_homeassistant_custom_component"

INFO = ChargerInfo(
    model="N24",
    hw_version="1.0.0.1",
    app_version="1.0.0.9",
    serial="00000000000000000000011c",
    channels=24,
    build_number="260731091001",
    build_date="2026-07-31",
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A charger, set up the way the config flow does it."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="N24",
        data={"host": "bridge.example", "port": 24000},
        unique_id=INFO.serial,
    )


@pytest.fixture
def mock_charger() -> Generator[None]:
    """A charger that answers with a poll from the first logged batch, while charging."""
    _, metrics = load_polls("batch1.log.gz")[894]
    with (
        patch("custom_components.isdt.get_info", return_value=INFO),
        patch("custom_components.isdt.config_flow.get_info", return_value=INFO),
        patch("custom_components.isdt.coordinator.read_metrics", return_value=metrics),
    ):
        yield
