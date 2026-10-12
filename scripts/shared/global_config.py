"""Read/write helpers for nWave's global config (``~/.nwave/global-config.json``)."""

import json
from pathlib import Path

from scripts.shared.install_paths import GLOBAL_CONFIG_FILENAME


def read_global_config(config_dir: Path) -> dict:
    """Read global-config.json, returning empty dict on error."""
    config_file = config_dir / GLOBAL_CONFIG_FILENAME
    try:
        with open(config_file, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_global_config(config_dir: Path, config: dict) -> None:
    """Write global-config.json; callers read-modify-write to preserve other keys."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / GLOBAL_CONFIG_FILENAME
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
