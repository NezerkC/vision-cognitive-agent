"""Startup switches from config/arranque.yaml.

Services run for real unless config/arranque.yaml sets their `modos_mock` flag to true (or --mock forces every
service). A missing file or key means real mode: mock behavior must be an explicit choice, never a silent default.
"""

import logging
import os

import yaml

logger = logging.getLogger("Arranque")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_modos_mock(project_root: str = PROJECT_ROOT) -> dict[str, bool]:
    """The `modos_mock` mapping from config/arranque.yaml, or {} when the file or key is missing."""
    path = os.path.join(project_root, "config", "arranque.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return dict(cfg.get("modos_mock") or {})


def is_mock(modos_mock: dict[str, bool], service_key: str, force: bool = False) -> bool:
    """True only when mock mode is forced or the service is explicitly flagged."""
    return force or bool(modos_mock.get(service_key, False))


def read_mock_flag(service_key: str, project_root: str = PROJECT_ROOT) -> bool:
    """Current mock flag for one service, re-read from disk (used when a daemon reloads its settings)."""
    return is_mock(load_modos_mock(project_root), service_key)
