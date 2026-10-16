from __future__ import annotations

import json
from pathlib import Path

from engine_environment import EngineEnvironment
from engine_guard import GuardedEngineModels, RequestFailures

MODE_TEXT_LAYER = "text-layer"
MODE_FORCED_OCR = "forced-ocr"
OUTPUT_FORMAT = "json"
OCR_ERROR_MODEL = "ocr_error_model"
INFERENCE_MANAGER = "inference_manager"
_EXCLUDED_OUTPUT_FIELDS = ["metadata"]


class EngineModels:
    def __init__(self) -> None:
        EngineEnvironment().apply()
        self._models: dict | None = None

    def loaded(self) -> dict:
        if self._models is None:
            self._models = self._created()
        return self._models

    def ocr_error_model(self):
        return self.loaded()[OCR_ERROR_MODEL]

    def inference_manager(self):
        return self.loaded()[INFERENCE_MANAGER]

    @staticmethod
    def _created() -> dict:
        return GuardedEngineModels().created()


class MarkerEngine:
    def __init__(self, models: EngineModels | None = None, mode: str = MODE_TEXT_LAYER) -> None:
        self._models = models or EngineModels()
        self._reads_pixels = mode == MODE_FORCED_OCR

    def convert(self, pdf_path: Path, file_pages: list[int] | None = None) -> dict:
        converter = self._converter(file_pages)
        with RequestFailures(self._models.inference_manager()):
            return json.loads(converter(str(pdf_path)).model_dump_json(exclude=_EXCLUDED_OUTPUT_FIELDS))

    def _converter(self, file_pages: list[int] | None):
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        options = self._options(file_pages)
        parser = ConfigParser(options)
        return PdfConverter(config=self._configured(parser, options), artifact_dict=self._models.loaded(),
                            processor_list=parser.get_processors(), renderer=parser.get_renderer(),
                            llm_service=parser.get_llm_service())

    @staticmethod
    def _configured(parser, options: dict) -> dict:
        config = parser.generate_config_dict()
        config.update({name: value for name, value in options.items() if name not in config})
        return config

    def _options(self, file_pages: list[int] | None) -> dict:
        options = {"output_format": OUTPUT_FORMAT, "keep_pageheader_in_output": True,
                   "keep_pagefooter_in_output": True, "ocr_inline_math": self._reads_pixels,
                   "force_ocr": self._reads_pixels, "disable_ocr": not self._reads_pixels,
                   "ocr_equations": self._reads_pixels}
        if file_pages is not None:
            options["page_range"] = ",".join(str(page - 1) for page in file_pages)
        return options
