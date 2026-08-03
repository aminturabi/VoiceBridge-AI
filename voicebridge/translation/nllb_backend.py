"""Meta NLLB-200 (No Language Left Behind) offline translation backend."""

from __future__ import annotations

import threading

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.translation.base import TranslationBackend, TranslationError

logger = get_logger(__name__)

# Default mapping for supported languages to NLLB-200 FLORES codes
_NLLB_LANG_CODES = {
    "en": "eng_Latn",
    "ar": "arb_Arab",
    "ur": "urd_Arab",
    "hi": "hin_Deva",
    "fr": "fra_Latn",
    "es": "spa_Latn",
}


class NllbBackend(TranslationBackend):
    """Meta NLLB-200 translation provider backend."""

    name = "nllb"

    def __init__(self, config: Config | None = None):
        self._config = config
        self._lock = threading.Lock()
        self._pipeline = None
        self._model_name = "facebook/nllb-200-distilled-600M"
        self._device = -1  # CPU by default
        self._loaded = False

        if config is not None:
            nllb_cfg = config.get("translation.nllb", {})
            self._model_name = nllb_cfg.get("model_name", self._model_name)
            dev_str = nllb_cfg.get("device", "cpu")
            self._device = 0 if dev_str == "cuda" else -1

        self._init_backend()

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def _init_backend(self) -> None:
        if not self.is_available():
            logger.info("transformers or torch not installed; NLLB backend disabled.")
            return

        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

            model_path = self._model_name
            if self._config is not None:
                local_dir = self._config.path("models.nllb_dir", "models/nllb")
                if (local_dir / "config.json").exists():
                    model_path = str(local_dir)

            logger.info("Loading NLLB model %r...", model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_path)

            self._pipeline = pipeline(
                "translation",
                model=model,
                tokenizer=tokenizer,
                device=self._device,
            )
            self._loaded = True
            logger.info("NLLB translation backend loaded successfully")
        except Exception as error:  # noqa: BLE001
            logger.warning("Could not initialize NLLB backend: %s", error)

    def _get_nllb_code(self, lang: str) -> str:
        if self._config is not None:
            try:
                rec = self._config.language(lang)
                if "nllb_code" in rec:
                    return rec["nllb_code"]
            except Exception:  # noqa: BLE001
                pass
        return _NLLB_LANG_CODES.get(lang, f"{lang}_Latn")

    def translate(self, text: str, source: str, target: str) -> str:
        if not self.is_available() or not self._loaded or self._pipeline is None:
            raise TranslationError("NLLB backend is not initialized or dependencies missing")

        src_code = self._get_nllb_code(source)
        tgt_code = self._get_nllb_code(target)

        with self._lock:
            try:
                res = self._pipeline(
                    text,
                    src_lang=src_code,
                    tgt_lang=tgt_code,
                    max_length=512,
                )
                if res and isinstance(res, list) and len(res) > 0:
                    out = res[0].get("translation_text", "").strip()
                    if out:
                        return out
                raise TranslationError("NLLB returned empty output")
            except Exception as error:  # noqa: BLE001
                raise TranslationError(f"NLLB backend error: {error}") from error
