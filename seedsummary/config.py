"""Loading of YAML config files (profile, sources, watchlist)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class Config:
    profile: dict[str, Any]
    sources: dict[str, Any]
    watchlist: dict[str, Any]
    root: Path

    @property
    def data_dir(self) -> Path:
        d = self.root / "data"
        d.mkdir(exist_ok=True)
        return d

    @property
    def site_dir(self) -> Path:
        d = self.root / "site"
        d.mkdir(exist_ok=True)
        (d / "data").mkdir(exist_ok=True)
        return d

    @property
    def watchlist_path(self) -> Path:
        return CONFIG_DIR / "watchlist.yml"


def load_config(root: Path = ROOT) -> Config:
    cfg_dir = root / "config"
    return Config(
        profile=_load_yaml(cfg_dir / "profile.yml"),
        sources=_load_yaml(cfg_dir / "sources.yml"),
        watchlist=_load_yaml(cfg_dir / "watchlist.yml"),
        root=root,
    )


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
