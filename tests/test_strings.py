"""The shipped catalog names every sensor and every state the mapper emits."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from custom_components.sp_group import const

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "sp_group"
STRINGS = json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8"))
SENSORS = STRINGS["entity"]["sensor"]
# hassfest rejects anything else as a translation key.
TRANSLATION_KEY = re.compile(r"^[a-z0-9_]+$")


def _sensor_keys() -> set[str]:
    return {
        value for name, value in vars(const).items() if name.startswith("SENSOR_KEY_")
    }


def _sensor_states() -> set[str]:
    return {
        value for name, value in vars(const).items() if name.startswith("SENSOR_STATE_")
    }


def test_every_sensor_key_has_a_translated_name() -> None:
    assert _sensor_keys() <= SENSORS.keys()
    assert all(entry["name"] for entry in SENSORS.values())


def test_every_generated_state_has_a_translation() -> None:
    translated = {
        state for entry in SENSORS.values() for state in entry.get("state", {})
    }
    assert _sensor_states() <= translated


@pytest.mark.parametrize("key", sorted(SENSORS))
def test_keys_are_valid_translation_keys(key: str) -> None:
    assert TRANSLATION_KEY.match(key)
    assert all(TRANSLATION_KEY.match(state) for state in SENSORS[key].get("state", {}))


def test_shipped_english_catalog_matches_source_strings() -> None:
    shipped = (PACKAGE / "translations" / "en.json").read_text(encoding="utf-8")
    assert json.loads(shipped) == STRINGS


def _raised_exception_keys() -> set[str]:
    """Keys the modules hand to translated_error, read without importing them."""
    keys: set[str] = set()
    for name in ("coordinator.py", "__init__.py"):
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "translated_error"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                keys.add(node.args[0].value)
    return keys


def test_every_raised_exception_has_a_translated_message() -> None:
    keys = _raised_exception_keys()
    assert keys
    assert keys <= STRINGS["exceptions"].keys()


def test_exception_messages_only_use_the_error_placeholder() -> None:
    for entry in STRINGS["exceptions"].values():
        assert set(re.findall(r"{(\w+)}", entry["message"])) <= {"error"}
