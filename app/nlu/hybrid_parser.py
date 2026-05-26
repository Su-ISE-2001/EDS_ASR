"""Hybrid parser: rule-based first, LLM fallback when needed."""

from __future__ import annotations

from app.config.settings import CaptureDefaultSettings, LlmNluSettings
from app.nlu.llm_parser import LlmParamParser
from app.nlu.parser import IntentParamParser, ParseError, ParseResult


class HybridParamParser:
    def __init__(self, defaults: CaptureDefaultSettings, llm_settings: LlmNluSettings) -> None:
        self._rule = IntentParamParser(defaults)
        self._llm = LlmParamParser(llm_settings, defaults) if llm_settings.enabled else None
        self._parse_mode = llm_settings.parse_mode

    def parse(self, text: str) -> ParseResult:
        if self._llm is not None and self._parse_mode == "llm_first":
            try:
                return self._llm.parse(text)
            except ParseError:
                return self._rule.parse(text)

        try:
            rule_result = self._rule.parse(text)
            if self._llm is None or not rule_result.missing_fields:
                return rule_result
            # Missing fields exist: ask LLM for completion/normalization.
            return self._llm.parse(text)
        except ParseError:
            if self._llm is None:
                raise
            return self._llm.parse(text)
