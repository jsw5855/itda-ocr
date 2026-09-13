from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence, Tuple

from .crossref import apply_manufacture_constraint
from .extract import extract_date_tokens
from .interpret import DEFAULT_YEAR_MAX, DEFAULT_YEAR_MIN, ScoredCandidate, generate_candidates
from .keywords import ANCHOR_KEYWORDS, EXCLUDE_KEYWORDS, bbox_center, has_keyword, min_distance
from .types import DateResult, TextBox


@dataclass
class PositionedCandidate:
    result: DateResult
    center: Tuple[float, float]
    source_text: str
    candidates: List[ScoredCandidate]


def find_all_candidates(
    boxes: Sequence[TextBox], year_min: int = DEFAULT_YEAR_MIN, year_max: int = DEFAULT_YEAR_MAX
) -> List[PositionedCandidate]:
    """Every date interpretation found across all OCR boxes, each keeping its position."""
    positioned: List[PositionedCandidate] = []
    for box in boxes:
        for token in extract_date_tokens(box.text):
            scored = generate_candidates(token, year_min, year_max)
            if not scored:
                continue
            positioned.append(
                PositionedCandidate(
                    result=scored[0].date,
                    center=bbox_center(box.bbox),
                    source_text=box.text,
                    candidates=scored,
                )
            )
    return positioned


def _is_closer_to(center: Tuple[float, float], own: List[Tuple[float, float]], other: List[Tuple[float, float]]) -> bool:
    return min_distance(center, own) < min_distance(center, other)


def _pick_manufacture_reference(
    positioned: List[PositionedCandidate],
    anchor_centers: List[Tuple[float, float]],
    exclude_centers: List[Tuple[float, float]],
) -> Optional[DateResult]:
    """The nearest exclude-keyword-associated (e.g. 제조일자) date, if it's
    fully known, to use as a plausibility reference for expiration dates."""
    manufacture_side = [
        pc for pc in positioned
        if pc.result.is_complete() and _is_closer_to(pc.center, exclude_centers, anchor_centers)
    ]
    if not manufacture_side:
        return None
    manufacture_side.sort(key=lambda pc: min_distance(pc.center, exclude_centers))
    return manufacture_side[0].result


def select_final_date(
    boxes: Sequence[TextBox], year_min: int = DEFAULT_YEAR_MIN, year_max: int = DEFAULT_YEAR_MAX
) -> Optional[PositionedCandidate]:
    """Pick the expiration-date candidate: nearest to an anchor keyword and
    not nearer to an exclude keyword (e.g. 제조일자)."""
    positioned = find_all_candidates(boxes, year_min, year_max)
    if not positioned:
        return None

    anchor_centers = [bbox_center(b.bbox) for b in boxes if has_keyword(b.text, ANCHOR_KEYWORDS)]
    exclude_centers = [bbox_center(b.bbox) for b in boxes if has_keyword(b.text, EXCLUDE_KEYWORDS)]

    if anchor_centers and exclude_centers:
        reference = _pick_manufacture_reference(positioned, anchor_centers, exclude_centers)
        if reference is not None:
            for pc in positioned:
                if _is_closer_to(pc.center, anchor_centers, exclude_centers):
                    pc.candidates = apply_manufacture_constraint(pc.candidates, reference)
                    pc.result = pc.candidates[0].date

    if anchor_centers:
        def rank(pc: PositionedCandidate) -> Tuple[int, float]:
            d_anchor = min_distance(pc.center, anchor_centers)
            d_exclude = min_distance(pc.center, exclude_centers)
            penalty = 0 if d_anchor <= d_exclude else 1
            return (penalty, d_anchor)

        positioned.sort(key=rank)
    elif len(positioned) > 1:
        # No anchor keyword (e.g. 소비기한/EXP) was found anywhere in the
        # image, so there's no positional signal to pick among multiple
        # date candidates at all. An expiration date is virtually always
        # later than any other date printed on packaging (manufacture,
        # packaging, etc.), so as a last resort - not a real selection,
        # just a weak guess - prefer the chronologically latest complete
        # date over an arbitrary "whichever OCR box came first" default.
        def latest_first(pc: PositionedCandidate) -> Tuple[int, int]:
            if not pc.result.is_complete():
                return (1, 0)
            ordinal = date(pc.result.year, pc.result.month, pc.result.day).toordinal()
            return (0, -ordinal)

        positioned.sort(key=latest_first)

    return positioned[0]
