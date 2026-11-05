"""Diagnostics for the ISDT charger integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import IsdtConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IsdtConfigEntry
) -> dict[str, Any]:
    """Everything the integration knows. Nothing in here is secret."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
            "unique_id": entry.unique_id,
        },
        "charger": asdict(coordinator.info),
        "last_update_success": coordinator.last_update_success,
        "slots": [
            {
                "number": slot.number,
                "status": slot.status,
                "verdict": slot.verdict,
                "termination": slot.termination,
                "resistance": slot.resistance,
                "charged_normally": slot.charged_normally,
                "charge_start": slot.charge_start,
                "metrics": slot.metrics,
            }
            for slot in coordinator.slots
        ],
    }
