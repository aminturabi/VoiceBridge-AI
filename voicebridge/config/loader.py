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

    # -- path helpers -------------------------------------------------------

    @property
    def models_dir(self) -> Path:
        return self.path("models.root_dir", "models")

    @property
    def cache_dir(self) -> Path:
        return self.path("cache.dir", "cache")

    @property
    def avatar_dir(self) -> Path:
        return self.path("avatar.dir", "voicebridge/avatar")

    # -- feature flag helpers -----------------------------------------------

    def is_feature_enabled(self, flag_name: str, default: bool = True) -> bool:
        """Check if a feature flag is enabled via config or env var override."""
        env_var = f"VOICEBRIDGE_{flag_name.upper()}"
        if env_var in os.environ:
            val = os.environ[env_var].strip().lower()
            return val in ("1", "true", "yes", "on")
        return bool(self.get(f"feature_flags.{flag_name.lower()}", default))

    @property
    def enable_pipeline_contracts(self) -> bool:
        return self.is_feature_enabled("ENABLE_PIPELINE_CONTRACTS", True)

    @property
    def enable_new_interfaces(self) -> bool:
        return self.is_feature_enabled("ENABLE_NEW_INTERFACES", True)

    @property
    def enable_tracing(self) -> bool:
        return self.is_feature_enabled("ENABLE_TRACING", True)

    @property
    def enable_streaming(self) -> bool:
        return self.is_feature_enabled("ENABLE_STREAMING", True)

    @property
    def enable_async_pipeline(self) -> bool:
        return self.is_feature_enabled("ENABLE_ASYNC_PIPELINE", True)

    @property
    def enable_backpressure(self) -> bool:
        return self.is_feature_enabled("ENABLE_BACKPRESSURE", True)

    @property
    def enable_model_warmup(self) -> bool:
        return self.is_feature_enabled("ENABLE_MODEL_WARMUP", True)

    def queue_size(self, stage_name: str, default: int = 10) -> int:
        """Return configured max queue size for a pipeline stage."""
        return int(self.get(f"pipeline.queue_sizes.{stage_name.lower()}", default))

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
