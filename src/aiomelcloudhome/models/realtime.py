"""Realtime (WebSocket) update models for Melcloud Home."""

from typing import Any, TypeVar

from pydantic import BaseModel, Field

from .ata import ATAUnit, decode_ata_setting
from .atw import ATWUnit, decode_atw_setting

MESSAGE_TYPE_UNIT_STATE_CHANGED = "unitStateChanged"

_UnitT = TypeVar("_UnitT", ATAUnit, ATWUnit)


class UnitStateDelta(BaseModel):
    """A live per-unit state change pushed over the WebSocket."""

    unit_id: str
    unit_type: str
    changes: dict[str, Any] = Field(default_factory=dict)
    raw_settings: list[dict[str, Any]] = Field(default_factory=list, repr=False)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> "UnitStateDelta | None":
        """Build a delta from a single ``unitStateChanged`` message, or None if not applicable."""
        if message.get("messageType") != MESSAGE_TYPE_UNIT_STATE_CHANGED:
            return None
        data = message.get("Data") or {}
        unit_id = data.get("id")
        if not unit_id:
            return None
        unit_type = str(data.get("unitType", "")).lower()
        raw_settings = [s for s in data.get("settings", []) if isinstance(s, dict) and "name" in s]

        changes: dict[str, Any] = {}
        for setting in raw_settings:
            name = str(setting["name"])
            value = setting.get("value")
            if unit_type == "ata":
                changes[name] = decode_ata_setting(name, value)
            elif unit_type == "atw":
                changes[name] = decode_atw_setting(name, value)
            else:
                changes[name] = value

        return cls(unit_id=str(unit_id), unit_type=unit_type, changes=changes, raw_settings=raw_settings)

    def apply_to(self, unit: _UnitT) -> _UnitT:
        """Return a copy of ``unit`` with this delta's changes applied.

        ``None`` change values (undecodable codes) are skipped so they never wipe
        known state; unknown setting names are only merged into ``settings``.
        Returns the unit itself when nothing applies.
        """
        return unit.apply_delta(self.changes)


def parse_frame(payload: Any) -> list[UnitStateDelta]:
    """Parse a decoded WebSocket text frame (a JSON array of messages) into deltas."""
    if not isinstance(payload, list):
        return []
    deltas: list[UnitStateDelta] = []
    for message in payload:
        if isinstance(message, dict):
            delta = UnitStateDelta.from_message(message)
            if delta is not None:
                deltas.append(delta)
    return deltas
