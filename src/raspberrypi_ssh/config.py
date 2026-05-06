"""Load and validate configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path.home() / ".raspberrypi_ssh" / "config.yaml",
]

_DEFAULTS: dict[str, Any] = {
    "pi": {
        "host": "raspberrypi.local",
        "user": "pi",
        "port": 22,
        "ssh_key": "~/.ssh/id_ed25519",
        "target_dir": "/home/pi/Videos",
    },
    "local": {
        "source_dir": "./videos_to_send",
    },
    "rename": {
        "enabled": True,
        "video_extensions": [".mp4", ".mkv", ".mov", ".avi", ".webm"],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load config from *config_path*, falling back to default search paths."""
    search = [config_path] if config_path else _DEFAULT_CONFIG_PATHS

    raw: dict[str, Any] = {}
    for path in search:
        if path and path.exists():
            with path.open() as fh:
                raw = yaml.safe_load(fh) or {}
            break

    config = _deep_merge(_DEFAULTS, raw)

    # Expand ~ in paths
    config["pi"]["ssh_key"] = os.path.expanduser(config["pi"]["ssh_key"])
    config["local"]["source_dir"] = os.path.expanduser(config["local"]["source_dir"])

    return config
