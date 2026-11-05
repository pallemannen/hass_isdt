"""Replays logged N24 traffic.

The fixtures are the raw replies of an N24, logged while it charged real cells: one line per
reply, with the time it arrived and the 64-byte report in hex. They are decoded by isdttool,
just like live traffic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
import gzip
from pathlib import Path
from typing import Any

from isdttool.charger.charger import Charger
from isdttool.charger.representation import parse_packet

FIXTURES = Path(__file__).parent / "fixtures"
CHANNELS = 24


@cache
def load_polls(name: str) -> list[tuple[datetime, list[dict[str, Any]]]]:
    """The polls in a log: when, and the metrics of every slot."""
    decoder = Charger(None, model="N24", mode="app")
    replies: dict[int, dict[int, dict[str, Any]]] = {}
    with gzip.open(FIXTURES / name, "rt") as log:
        for line in log:
            parts = line.split()
            if len(parts) != 2:
                continue
            packet = decoder.read_packet([bytearray.fromhex(parts[1])])
            metrics = parse_packet(packet, "N24")
            if not metrics.get("_channel exists") or metrics.get("_malformed"):
                continue
            replies.setdefault(int(parts[0]), {})[metrics["channel"]] = metrics

    # A reply that was missed is taken from the poll before.
    polls = []
    latest: dict[int, dict[str, Any]] = {}
    for timestamp in sorted(replies):
        latest.update(replies[timestamp])
        if len(latest) == CHANNELS:
            polls.append(
                (
                    datetime.fromtimestamp(timestamp, UTC),
                    [latest[channel] for channel in range(CHANNELS)],
                )
            )
    return polls
