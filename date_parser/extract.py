from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

DIGIT = r"[0-9OoUu]"

MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_MONTH_RE = "|".join(MONTH_NAMES)

CONFUSABLE_MAP = str.maketrans({"O": "0", "o": "0", "U": "0", "u": "0"})


def normalize_confusable(raw: str) -> str:
    """Digits that OCR commonly confuses with letters (O/o/U/u -> 0)."""
    return raw.translate(CONFUSABLE_MAP)


@dataclass(frozen=True)
class RawField:
    raw: str
    kind: str  # 'num' or 'month_name'


@dataclass(frozen=True)
class RawDateToken:
    span: Tuple[int, int]
    fields: Tuple[RawField, ...]
    role_universe: Tuple[str, ...]
    fixed_roles: Optional[Tuple[str, ...]] = None  # None => ambiguous order


_NUM = RawField
# Real OCR output sometimes has more than one separator character in a row
# (e.g. "2021. 03.20" has a period AND a space between year and month), so
# this allows one or more, not just exactly one.
_SEP = r"[.\-/\s]+"
_OPTIONAL_SEP = r"[.\-/\s]*"

# (regex, field kinds per group, role_universe, fixed_roles)
# fixed_roles is only used where the source text itself names the unit
# (년/월/일), so the order is read directly off the text rather than assumed.
_PATTERN_DEFS = [
    (
        re.compile(rf"(?<!\d)(\d{{4}})년\s*(\d{{1,2}})월\s*(\d{{1,2}})일"),
        ("num", "num", "num"),
        ("year", "month", "day"),
        ("year", "month", "day"),
    ),
    (
        re.compile(rf"(?<!\d)(\d{{4}})년\s*(\d{{1,2}})월(?!\s*\d{{1,2}}일)"),
        ("num", "num"),
        ("year", "month"),
        ("year", "month"),
    ),
    (
        re.compile(rf"(?<!\d)(\d{{1,2}})월\s*(\d{{1,2}})일"),
        ("num", "num"),
        ("month", "day"),
        ("month", "day"),
    ),
    (
        re.compile(rf"(?<!\d)(\d{{1,2}}){_SEP}({_MONTH_RE}){_SEP}(\d{{2,4}})(?!\d)", re.IGNORECASE),
        ("num", "month_name", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        # "04NOV 2021" style: day glued directly to the month name with no
        # separator at all (OCR dropped the space), but a real separator
        # before the year. Safe to allow zero separator here for the same
        # reason as the "AUG292020" pattern above - the month name is a
        # strong, small anchor that can't accidentally swallow an unrelated
        # digit run.
        re.compile(rf"(?<!\d)(\d{{1,2}}){_OPTIONAL_SEP}({_MONTH_RE}){_SEP}(\d{{2,4}})(?!\d)", re.IGNORECASE),
        ("num", "month_name", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        re.compile(rf"(?<!\d)(\d{{2,4}}){_SEP}({_MONTH_RE}){_SEP}(\d{{1,2}})(?!\d)", re.IGNORECASE),
        ("num", "month_name", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        # "JUN 28 2021" style: month name first, then day and year (day/year
        # order between the two numeric fields is still resolved by
        # validation + the existing order-prior, not assumed here).
        re.compile(rf"(?<!\d)({_MONTH_RE}){_SEP}(\d{{1,2}}){_SEP}(\d{{2,4}})(?!\d)", re.IGNORECASE),
        ("month_name", "num", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        # "AUG292020" style: month name immediately butted up against the
        # digits with no separator at all (OCR dropped the space/punctuation).
        # Safe to allow zero separators here because the month name is a
        # strong, small, fixed anchor - it can't accidentally appear inside
        # an unrelated digit run the way a bare number pattern could.
        re.compile(rf"(?<!\d)({_MONTH_RE}){_OPTIONAL_SEP}(\d{{1,2}}){_OPTIONAL_SEP}(\d{{4}})(?!\d)", re.IGNORECASE),
        ("month_name", "num", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        # "JUL2023" / "JUL 2023" style: month name + year only, no day found
        # in the text at all -> partial-NONE day. The month name itself
        # (not an assumed country convention) is what fixes the field order.
        re.compile(rf"(?<!\d)({_MONTH_RE}){_OPTIONAL_SEP}(\d{{4}})(?!\d)", re.IGNORECASE),
        ("month_name", "num"),
        ("month", "year"),
        ("month", "year"),
    ),
    (
        re.compile(rf"(?<!\d)({DIGIT}{{1,4}}){_SEP}({DIGIT}{{1,4}}){_SEP}({DIGIT}{{1,4}})(?!\d)"),
        ("num", "num", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        re.compile(rf"(?<!\d)({DIGIT}{{4}})({DIGIT}{{2}})({DIGIT}{{2}})(?!\d)"),
        ("num", "num", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        # "2021.0326" (month+day glued together with no internal separator)
        # and "2022.11:02" (a single stray punctuation mark, e.g. OCR
        # misreading "." as ":", between month and day). Anchored by an
        # unambiguous 4-digit year up front, so allowing a loose/optional
        # separator for the rest is low-risk - this can't accidentally
        # swallow an unrelated HH:MM:SS timestamp since those never start
        # with a 4-digit number.
        re.compile(rf"(?<!\d)({DIGIT}{{4}}){_SEP}({DIGIT}{{2}})[:.()]?({DIGIT}{{2}})(?!\d)"),
        ("num", "num", "num"),
        ("year", "month", "day"),
        None,
    ),
    (
        re.compile(rf"(?<!\d)({DIGIT}{{4}}){_SEP}({DIGIT}{{1,2}})(?!\d)"),
        ("num", "num"),
        ("year", "month"),
        None,
    ),
]


def _overlaps(span: Tuple[int, int], claimed: List[Tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in claimed)


def extract_date_tokens(text: str) -> List[RawDateToken]:
    """Find date-shaped substrings in ``text`` without assuming field order.

    Patterns are tried most-specific-first; once a span is claimed, later
    (more generic) patterns skip anything overlapping it.
    """
    claimed: List[Tuple[int, int]] = []
    tokens: List[RawDateToken] = []
    for pattern, kinds, role_universe, fixed_roles in _PATTERN_DEFS:
        for match in pattern.finditer(text):
            span = match.span()
            if _overlaps(span, claimed):
                continue
            fields = tuple(RawField(raw=g, kind=k) for g, k in zip(match.groups(), kinds))
            tokens.append(RawDateToken(span=span, fields=fields, role_universe=role_universe, fixed_roles=fixed_roles))
            claimed.append(span)
    tokens.sort(key=lambda t: t.span[0])
    return tokens
