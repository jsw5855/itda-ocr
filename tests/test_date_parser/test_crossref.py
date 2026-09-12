from date_parser.crossref import apply_manufacture_constraint
from date_parser.interpret import ScoredCandidate
from date_parser.types import DateResult


def test_promotes_reading_that_is_after_reference():
    # Default top pick (higher score) is chronologically impossible given
    # the manufacture date; the other valid reading isn't.
    candidates = [
        ScoredCandidate(DateResult(2020, 6, 26), score=3, perm=("year", "month", "day")),
        ScoredCandidate(DateResult(2026, 6, 20), score=2, perm=("day", "month", "year")),
    ]
    reference = DateResult(2024, 1, 1)
    reranked = apply_manufacture_constraint(candidates, reference)
    assert reranked[0].date == DateResult(2026, 6, 20)


def test_keeps_default_order_when_reference_is_missing():
    candidates = [
        ScoredCandidate(DateResult(2020, 6, 26), score=3, perm=("year", "month", "day")),
        ScoredCandidate(DateResult(2026, 6, 20), score=2, perm=("day", "month", "year")),
    ]
    reranked = apply_manufacture_constraint(candidates, None)
    assert reranked[0].date == DateResult(2020, 6, 26)


def test_keeps_default_order_when_reference_is_partial():
    candidates = [
        ScoredCandidate(DateResult(2020, 6, 26), score=3, perm=("year", "month", "day")),
        ScoredCandidate(DateResult(2026, 6, 20), score=2, perm=("day", "month", "year")),
    ]
    reranked = apply_manufacture_constraint(candidates, DateResult(2024, 1, None))
    assert reranked[0].date == DateResult(2020, 6, 26)


def test_keeps_default_order_when_every_candidate_fails_the_check():
    # Reference is after both readings -> neither passes, so the check adds
    # no information and the original (score-based) order is left alone.
    candidates = [
        ScoredCandidate(DateResult(2020, 6, 26), score=3, perm=("year", "month", "day")),
        ScoredCandidate(DateResult(2026, 6, 20), score=2, perm=("day", "month", "year")),
    ]
    reference = DateResult(2030, 1, 1)
    reranked = apply_manufacture_constraint(candidates, reference)
    assert reranked[0].date == DateResult(2020, 6, 26)


def test_does_not_override_a_partial_candidate_with_a_worse_complete_one():
    candidates = [
        ScoredCandidate(DateResult(2026, 7, None), score=3, perm=("year", "month")),
    ]
    reranked = apply_manufacture_constraint(candidates, DateResult(2024, 1, 1))
    assert reranked[0].date == DateResult(2026, 7, None)
