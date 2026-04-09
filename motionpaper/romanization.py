from typing import List, Optional

try:
    import pykakasi

    _kks = pykakasi.kakasi()
except ImportError:
    _kks = None

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None


CHOSUNG = [
    "g",
    "kk",
    "n",
    "d",
    "tt",
    "r",
    "l",
    "m",
    "b",
    "pp",
    "s",
    "ss",
    "",
    "j",
    "jj",
    "ch",
    "k",
    "t",
    "p",
    "h",
]
JUNGSUNG = [
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "wo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
]
JONGSUNG = [
    "",
    "g",
    "kk",
    "gs",
    "n",
    "nj",
    "nh",
    "d",
    "l",
    "lg",
    "lm",
    "lb",
    "ls",
    "lt",
    "lp",
    "lh",
    "m",
    "b",
    "bs",
    "s",
    "ss",
    "ng",
    "j",
    "ch",
    "k",
    "t",
    "p",
    "h",
]


def romanize_korean(text: str) -> str:
    result = []
    for char in text:
        code = ord(char)
        if 44032 <= code <= 55203:
            code -= 44032
            cho = code // 588
            jung = code % 588 // 28
            jong = code % 28
            result.append(CHOSUNG[cho] + JUNGSUNG[jung] + JONGSUNG[jong])
        else:
            result.append(char)
    return "".join(result)


def _romanize_japanese(text: str) -> Optional[str]:
    if not _kks:
        return None
    try:
        converted = _kks.convert(text)
        return "".join(item["hepburn"] for item in converted)
    except Exception:
        return None


def _romanize_chinese(text: str) -> Optional[str]:
    if not lazy_pinyin:
        return None
    try:
        return " ".join(lazy_pinyin(text))
    except Exception:
        return None


def romanize_text(text: str) -> str:
    if not text:
        return text

    variants: List[str] = [text]

    for candidate in (
        _romanize_japanese(text),
        _romanize_chinese(text),
        romanize_korean(text),
    ):
        if candidate and candidate != text:
            variants.append(candidate)

    return " ".join(variants)
