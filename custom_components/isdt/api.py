"""Blocking access to a charger through an isdttool bridge.

isdttool is synchronous, so everything here runs in the executor. Each call opens its own
connection and closes it again. A bridge serves one client at a time and a new client replaces
the current one, so holding the connection open would kick out anyone else using the charger,
for example the isdttool command line with --host, for as long as Home Assistant runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import isdttool
from isdttool.charger.representation import parse_packet


class CannotConnect(Exception):
    """The bridge could not be reached, or the charger did not answer."""


@dataclass
class ChargerInfo:
    """What a charger tells about itself."""

    model: str
    hw_version: str | None
    app_version: str | None
    serial: str | None
    channels: int
    # The version reply ends with a timestamp, which the N24 also shows on its screen as part
    # of its PN: year, month, day, hour, and two more numbers. The date is certain, the rest
    # is not, so the build number keeps all six as they are, two digits each.
    build_number: str | None = None
    build_date: str | None = None


def _open(host: str, port: int) -> isdttool.Charger:
    try:
        return isdttool.get_device(host=host, port=port, model_name="auto", mode="auto")
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise CannotConnect(str(err)) from err


def _request(charger: isdttool.Charger, model: str) -> dict[str, Any]:
    packet = charger.read_packet()
    if packet is None:
        raise CannotConnect("The charger did not answer")
    return parse_packet(packet, model)


def _count_channels(charger: isdttool.Charger, model: str) -> int:
    for channel in range(256):
        charger.metrics(channel)
        if not _request(charger, model).get("_channel exists"):
            return channel
    return 256


def _build_stamp(packet: bytearray) -> tuple[str | None, str | None]:
    """The build number, and date, from a version reply. (None, None) if it has none."""
    stamp = packet[0x21:0x27]
    if len(stamp) < 6 or not 1 <= stamp[1] <= 12 or not 1 <= stamp[2] <= 31:
        return None, None
    return "".join(f"{b:02d}" for b in stamp), f"20{stamp[0]:02d}-{stamp[1]:02d}-{stamp[2]:02d}"


def get_info(host: str, port: int) -> ChargerInfo:
    """Identify the charger. Raises CannotConnect."""
    charger = _open(host, port)
    try:
        model = charger.model
        charger.version()
        version_packet = charger.read_packet()
        if version_packet is None:
            raise CannotConnect("The charger did not answer")
        version = parse_packet(version_packet, model)
        build_number, build_date = _build_stamp(version_packet)

        serial: str | None = None
        charger.get_mcu_serial_number()
        packet = charger.read_packet()
        if packet is not None:
            serial = parse_packet(packet, model).get("serial number")

        return ChargerInfo(
            model=model,
            hw_version=version.get("hw version"),
            app_version=version.get("app version"),
            serial=serial,
            channels=_count_channels(charger, model),
            build_number=build_number,
            build_date=build_date,
        )
    except OSError as err:
        raise CannotConnect(str(err)) from err
    finally:
        charger.close()


def read_metrics(host: str, port: int, model: str, channels: int) -> list[dict[str, Any]]:
    """Read the metrics of every channel. Raises CannotConnect."""
    charger = _open(host, port)
    try:
        result = []
        for channel in range(channels):
            charger.metrics(channel)
            metrics = _request(charger, model)
            if metrics.get("_malformed") or not metrics.get("_channel exists"):
                raise CannotConnect(f"Bad reply for channel {channel}: {metrics}")
            result.append(metrics)
        return result
    except OSError as err:
        raise CannotConnect(str(err)) from err
    finally:
        charger.close()
