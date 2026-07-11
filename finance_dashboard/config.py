"""Central YAML configuration for the finance dashboard."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "data": {
        "base_dir": "data/sample",
        "mapping_file": "mapping.csv",
        "essentiality_file": "category_essentiality.csv",
        "raw_exports_dir": "data/raw_bank_exports",
        "ledger_dir": "data/working_ledger",
    },
    "analysis": {
        "avg_window": 3,
        "rolling_window_months": 3,
        "reorder_last": ["Savings", "Income"],
    },
    "scenarios": None,
    "app": {
        "theme": "DARKLY",
        "external_stylesheets": [
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
        ],
        "graphs": {
            "display_mode_bar": False,
            "timeseries_y_range": [-1500, 100],
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8050,
            "debug": True,
        },
    },
    "n8n": None,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_path(value: str | Path, root: Path) -> Path:
    raw_path = Path(value)
    return raw_path if raw_path.is_absolute() else root / raw_path


def _resolve_data_paths(config: dict[str, Any]) -> dict[str, Path]:
    data_cfg = config["data"]
    data_dir = _resolve_path(data_cfg["base_dir"], ROOT_DIR)
    paths = {
        "data_dir": data_dir,
        "mapping_file": _resolve_path(data_cfg["mapping_file"], data_dir),
        "essentiality_file": _resolve_path(data_cfg["essentiality_file"], data_dir),
        "raw_exports_dir": _resolve_path(data_cfg["raw_exports_dir"], ROOT_DIR),
        "ledger_dir": _resolve_path(data_cfg["ledger_dir"], ROOT_DIR),
    }
    if isinstance(config.get("n8n"), dict):
        paths["unknowns_for_n8n"] = _resolve_path(config["n8n"]["unknowns_output"], ROOT_DIR)
    else:
        paths["unknowns_for_n8n"] = None
    return paths


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or CONFIG_FILE
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    raw_config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = _deep_merge(DEFAULT_CONFIG, raw_config)
    config["paths"] = _resolve_data_paths(config)
    return config


CONFIG = load_config()
