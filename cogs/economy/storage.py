"""JSON storage helpers for the economy system."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

DATA_PATH = Path("data/economy.json")
CONFIG_PATH = Path("data/config.json")


def default_data() -> dict[str, Any]:
    return {"guilds": {}}


def load_data() -> dict[str, Any]:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists() or DATA_PATH.stat().st_size == 0:
        save_data(default_data())
        return default_data()

    try:
        with DATA_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        backup = DATA_PATH.with_suffix(".json.bak")
        DATA_PATH.replace(backup)
        data = default_data()
        save_data(data)

    data.setdefault("guilds", {})
    return data


def save_data(data: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DATA_PATH.with_suffix(".json.tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)

    temp_path.replace(DATA_PATH)


def _merge_missing(target: dict[str, Any], defaults: dict[str, Any]) -> bool:
    changed = False
    for key, value in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
            changed = True
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            changed = _merge_missing(target[key], value) or changed
    return changed


def load_config() -> dict[str, Any]:
    """Load config.json and keep missing future keys populated.

    JSON cannot contain real comments, so config.json uses a parallel
    `descriptions` object documenting every configurable value.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    config.setdefault("values", {})
    config.setdefault("descriptions", {})
    return config


def config_values() -> dict[str, Any]:
    return load_config()["values"]
