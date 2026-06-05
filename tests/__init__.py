"""Tests for aiomelcloudhome."""

import json
from pathlib import Path
from typing import Any, cast


def load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file from the fixtures directory."""
    fixture_path = Path(__file__).parent / "fixtures" / filename
    with fixture_path.open() as f:
        return cast("dict[str, Any]", json.load(f))
