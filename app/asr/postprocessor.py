"""ASR text post-processing pipeline."""

from __future__ import annotations

import re

_FILLER_WORDS = ("嗯", "啊", "呃", "那个", "就是", "请帮我", "麻烦")

_TRADITIONAL_PHRASE_MAP = {
    "放大倍數": "放大倍数",
    "曝光時間": "曝光时间",
    "幀數": "帧数",
    "樣品": "样品",
    "儲存": "保存",
    "張圖": "张图",
}

_TERM_NORMALIZATION = {
    "放大倍数": "倍率",
    "曝光时间": "曝光",
    "毫秒钟": "毫秒",
    "张图": "张",
    "帧数": "张数",
}

_CHINESE_NUMS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

_CHINESE_UNITS = {
    "十": 10,
    "百": 100,
    "千": 1000,
    "万": 10000,
}

_TRADITIONAL_CHAR_TABLE = str.maketrans(
    {
        "樣": "样",
        "儲": "储",
        "張": "张",
        "幀": "帧",
        "數": "数",
        "間": "间",
        "號": "号",
        "為": "为",
        "與": "与",
        "體": "体",
        "臺": "台",
        "兩": "两",
    }
)

try:
    from opencc import OpenCC

    _OPENCC_T2S = OpenCC("t2s")
except Exception:
    _OPENCC_T2S = None


def _to_simplified_chinese(text: str) -> str:
    normalized = text
    for source, target in _TRADITIONAL_PHRASE_MAP.items():
        normalized = normalized.replace(source, target)
    normalized = normalized.translate(_TRADITIONAL_CHAR_TABLE)
    if _OPENCC_T2S is not None:
        normalized = _OPENCC_T2S.convert(normalized)
    return normalized


def _chinese_to_int(token: str) -> int | None:
    if not token:
        return None
    if token.isdigit():
        return int(token)

    total = 0
    section = 0
    number = 0
    for char in token:
        if char in _CHINESE_NUMS:
            number = _CHINESE_NUMS[char]
            continue
        unit = _CHINESE_UNITS.get(char)
        if unit is None:
            return None
        if number == 0 and unit == 10:
            number = 1
        section += number * unit
        number = 0
        if unit == 10000:
            total += section
            section = 0

    return total + section + number


def _normalize_chinese_numbers(text: str) -> str:
    pattern = re.compile(r"[零一二两三四五六七八九十百千万]+")

    def _replace(match: re.Match) -> str:
        maybe_int = _chinese_to_int(match.group(0))
        return str(maybe_int) if maybe_int is not None else match.group(0)

    return pattern.sub(_replace, text)


def postprocess_text(text: str) -> str:
    normalized = text.strip()
    normalized = _to_simplified_chinese(normalized)
    for filler in _FILLER_WORDS:
        normalized = normalized.replace(filler, "")

    for source, target in _TERM_NORMALIZATION.items():
        normalized = normalized.replace(source, target)

    normalized = _normalize_chinese_numbers(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
