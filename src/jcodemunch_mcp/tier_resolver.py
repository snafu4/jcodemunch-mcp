"""Pure helpers for tier bundle validation and model-id → tier resolution.

Kept free of server/config imports so it's trivially unit-testable.
"""

from __future__ import annotations

import re

_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")
_BRACKET_SUFFIX_RE = re.compile(r"\[[^\]]*\]$")


def normalize_model_id(model_id: object) -> str:
    """Canonicalize a model id for matching.

    Strips provider prefixes (anything up to and including the last '/'),
    bracketed suffixes like '[1m]' / '[beta]', and trailing '-YYYYMMDD'
    date stamps. Lowercases. Non-string input returns ''.
    """
    if not isinstance(model_id, str):
        return ""
    s = model_id.strip().lower()
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    s = _BRACKET_SUFFIX_RE.sub("", s)
    s = _DATE_SUFFIX_RE.sub("", s)
    return s
