"""Load and provide typed access to ``config.yaml``.

The loader keeps the raw dict but exposes dotted-path lookups and a few
resolved conveniences (absolute paths, language records) so the rest of the
package never hardcodes constants.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Project root = the directory that contains config.yaml (two levels up from
# this file: voicebridge/config/loader.py -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

# Sentinel so ``get`` can distinguish "missing" from an explicit None default.
_MISSING = object()


class ConfigError(Exception):
    """Raised when the configuration file is missing or malformed."""


class Config:
    """Typed, dotted-path wrapper around the parsed YAML config."""

    def __init__(self, data: dict[str, Any], source_path: Path | None = None):
        self._data = data
        self.source_path = source_path
        self.project_root = PROJECT_ROOT

    def get(self, dotted_key: str, default: Any = _MISSING) -> Any:
        """Look up ``a.b.c`` in the config tree.

        Raises ``ConfigError`` if the key is missing and no default is given.
        """
        node: Any = self._data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                if default is _MISSING:
                    raise ConfigError(f"Missing config key: {dotted_key!r}")
                return default
        return node

    def path(self, dotted_key: str, default: Any = _MISSING) -> Path:
        """Resolve a config value to an absolute path under the project root."""
        raw = self.get(dotted_key, default)
        p = Path(raw)
        return p if p.is_absolute() else (self.project_root / p)

    # -- language helpers ---------------------------------------------------

    @property
    def languages(self) -> dict[str, dict]:
        return self.get("languages")

    def language(self, lang_id: str) -> dict:
        """Return the language record for an id like ``en`` / ``ar``."""
        langs = self.languages
        if lang_id not in langs:
            raise ConfigError(
                f"Unknown language id {lang_id!r}. "
                f"Known: {', '.join(sorted(langs))}"
            )
        return langs[lang_id]

    @property
    def raw(self) -> dict[str, Any]:
        return self._data


def load_config(path: str | os.PathLike | None = None) -> Config:
    """Read ``config.yaml`` (or an override path) and return a :class:`Config`.

    The path may also be supplied via the ``VOICEBRIDGE_CONFIG`` env var.
    """
    if path is None:
        path = os.environ.get("VOICEBRIDGE_CONFIG", DEFAULT_CONFIG_PATH)
    config_path = Path(path)

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        raise ConfigError(f"Could not parse {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}")

    return Config(data, source_path=config_path)
