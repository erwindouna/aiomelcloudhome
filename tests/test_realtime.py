"""Tests for WebSocket realtime delta parsing.

Frames and enum codes here were captured live against real ATA hardware
(andrew-blake/melcloudhome#174).
"""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome.models.ata import ATAFanSpeed, ATAOperationMode, ATAVaneHorizontal, ATAVaneVertical
from aiomelcloudhome.models.realtime import UnitStateDelta, parse_frame


def _ata_frame(name: str, value: Any) -> list[dict[str, Any]]:
    """Build a single-setting ATA unitStateChanged frame."""
    return [
        {
            "messageType": "unitStateChanged",
            "Data": {"id": "unit-1", "unitType": "ata", "settings": [{"name": name, "value": value}]},
        },
    ]


def test_set_temperature_number(snapshot: SnapshotAssertion) -> None:
    """SetTemperature arrives as a native number and decodes to float."""
    (delta,) = parse_frame(_ata_frame("SetTemperature", 17))
    assert delta == snapshot


def test_power_bool() -> None:
    """Power arrives as a native JSON bool."""
    assert parse_frame(_ata_frame("Power", value=False))[0].changes == {"Power": False}
    assert parse_frame(_ata_frame("Power", value=True))[0].changes == {"Power": True}


@pytest.mark.parametrize(
    ("code", "expected"),
    [(1, ATAOperationMode.HEAT), (2, ATAOperationMode.DRY), (3, ATAOperationMode.COOL), (4, ATAOperationMode.FAN), (5, ATAOperationMode.AUTOMATIC)],
)
def test_operation_mode_int_codes(code: int, expected: ATAOperationMode) -> None:
    """OperationMode integer codes decode to the shared StrEnum."""
    assert parse_frame(_ata_frame("OperationMode", code))[0].changes == {"OperationMode": expected}


@pytest.mark.parametrize(
    ("code", "expected"),
    [(0, ATAFanSpeed.AUTO), (1, ATAFanSpeed.ONE), (2, ATAFanSpeed.TWO), (4, ATAFanSpeed.FOUR), (5, ATAFanSpeed.FIVE)],
)
def test_fan_speed_int_codes(code: int, expected: ATAFanSpeed) -> None:
    """SetFanSpeed integer codes decode to the shared StrEnum."""
    assert parse_frame(_ata_frame("SetFanSpeed", code))[0].changes == {"SetFanSpeed": expected}


@pytest.mark.parametrize(
    ("code", "expected"),
    [(0, ATAVaneVertical.AUTO), (1, ATAVaneVertical.ONE), (6, ATAVaneVertical.SWING)],
)
def test_vane_vertical_int_codes(code: int, expected: ATAVaneVertical) -> None:
    """VaneVerticalDirection codes decode; Swing is 6."""
    assert parse_frame(_ata_frame("VaneVerticalDirection", code))[0].changes == {"VaneVerticalDirection": expected}


@pytest.mark.parametrize(
    ("code", "expected"),
    [(0, ATAVaneHorizontal.AUTO), (3, ATAVaneHorizontal.CENTRE), (5, ATAVaneHorizontal.RIGHT), (7, ATAVaneHorizontal.SWING)],
)
def test_vane_horizontal_int_codes(code: int, expected: ATAVaneHorizontal) -> None:
    """VaneHorizontalDirection codes decode; Swing is 7 (differs from vertical)."""
    assert parse_frame(_ata_frame("VaneHorizontalDirection", code))[0].changes == {"VaneHorizontalDirection": expected}


def test_actual_fan_speed_numeric_string() -> None:
    """ActualFanSpeed arrives as a numeric string on the socket and still decodes."""
    assert parse_frame(_ata_frame("ActualFanSpeed", "2"))[0].changes == {"ActualFanSpeed": ATAFanSpeed.TWO}


def test_rest_style_string_names_still_decode() -> None:
    """A string enum name (REST shape) decodes through the same path."""
    assert parse_frame(_ata_frame("OperationMode", "Cool"))[0].changes == {"OperationMode": ATAOperationMode.COOL}


def test_unknown_code_is_none() -> None:
    """An unmapped integer code decodes to None rather than raising."""
    assert parse_frame(_ata_frame("OperationMode", 99))[0].changes == {"OperationMode": None}


def test_unknown_setting_passed_through() -> None:
    """Unknown setting names keep their raw value."""
    assert parse_frame(_ata_frame("SomethingNew", "raw"))[0].changes == {"SomethingNew": "raw"}


def test_multi_setting_frame_batched(snapshot: SnapshotAssertion) -> None:
    """A control call touching several settings yields one delta with all of them."""
    frame = [
        {
            "messageType": "unitStateChanged",
            "Data": {
                "id": "unit-1",
                "unitType": "ata",
                "settings": [
                    {"name": "Power", "value": True},
                    {"name": "OperationMode", "value": 3},
                    {"name": "SetFanSpeed", "value": 4},
                    {"name": "VaneVerticalDirection", "value": 6},
                ],
            },
        },
    ]
    (delta,) = parse_frame(frame)
    assert delta == snapshot


def test_atw_delta_decodes_types(snapshot: SnapshotAssertion) -> None:
    """ATW deltas decode bools, floats and string enum names."""
    frame = [
        {
            "messageType": "unitStateChanged",
            "Data": {
                "id": "atw-1",
                "unitType": "atw",
                "settings": [
                    {"name": "Power", "value": True},
                    {"name": "SetTankWaterTemperature", "value": 45},
                    {"name": "OperationMode", "value": "HotWater"},
                ],
            },
        },
    ]
    (delta,) = parse_frame(frame)
    assert delta == snapshot


def test_multi_message_frame(snapshot: SnapshotAssertion) -> None:
    """A frame carrying several unit messages parses to one delta each, in order."""
    frame = [
        {
            "messageType": "unitStateChanged",
            "Data": {"id": "ata-1", "unitType": "ata", "settings": [{"name": "OperationMode", "value": 3}]},
        },
        {
            "messageType": "unitStateChanged",
            "Data": {"id": "atw-1", "unitType": "atw", "settings": [{"name": "Power", "value": False}]},
        },
    ]
    assert parse_frame(frame) == snapshot


def test_non_unit_state_changed_ignored() -> None:
    """Messages that are not unitStateChanged produce no deltas."""
    assert parse_frame([{"messageType": "somethingElse", "Data": {}}]) == []


def test_missing_id_ignored() -> None:
    """A message without a unit id is skipped."""
    assert UnitStateDelta.from_message({"messageType": "unitStateChanged", "Data": {"unitType": "ata"}}) is None


def test_parse_frame_non_list() -> None:
    """A non-list payload parses to an empty list."""
    assert parse_frame({"not": "a list"}) == []
    assert parse_frame("nope") == []
