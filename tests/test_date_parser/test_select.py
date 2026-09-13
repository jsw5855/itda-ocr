from date_parser.select import find_all_candidates, select_final_date
from date_parser.types import DateResult, TextBox


def _box(text, x, y):
    return TextBox(text=text, confidence=0.9, bbox=[[x, y], [x + 10, y], [x + 10, y + 5], [x, y + 5]])


def test_find_all_candidates_across_multiple_boxes():
    boxes = [
        _box("제조일자", 0, 0),
        _box("2026.01.01", 0, 5),
        _box("소비기한", 0, 100),
        _box("2026.07.01", 0, 105),
    ]
    positioned = find_all_candidates(boxes)
    assert len(positioned) == 2


def test_select_prefers_date_near_anchor_keyword_over_exclude():
    boxes = [
        _box("제조일자", 0, 0),
        _box("2026.01.01", 0, 5),
        _box("소비기한", 0, 100),
        _box("2026.07.01", 0, 105),
    ]
    best = select_final_date(boxes)
    assert best is not None
    assert best.result.month == 7


def test_select_with_no_keywords_falls_back_to_only_candidate():
    boxes = [_box("2026.03.10", 0, 0)]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 3, 10)


def test_select_with_no_dates_returns_none():
    boxes = [_box("영양성분표", 0, 0)]
    assert select_final_date(boxes) is None


def test_select_uses_manufacture_date_to_resolve_ymd_dmy_ambiguity():
    # "20.06.26" is genuinely ambiguous: YMD reading 2020-06-26 (default,
    # higher score) vs DMY reading 2026-06-20. A manufacture date of
    # 2024-01-01 rules out 2020-06-26 (expiration can't be before
    # manufacture), so the pick should flip to the DMY reading.
    boxes = [
        _box("제조일자 2024년 01월 01일", 0, 0),
        _box("소비기한 20.06.26", 0, 100),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 6, 20)


def test_select_prefers_latest_date_when_no_anchor_keyword_anywhere():
    # Real case from label2.xlsx (id=1104): two dates, neither box has any
    # anchor/exclude keyword text at all, so there's no positional signal.
    # Expiration should virtually always be the later of the two.
    boxes = [
        _box("2020.11.27", 0, 0),
        _box("2021.08.26", 0, 100),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2021, 8, 26)


def test_select_no_fallback_reorder_when_only_one_candidate():
    boxes = [_box("2021.08.26", 0, 0)]
    best = select_final_date(boxes)
    assert best.result == DateResult(2021, 8, 26)


def test_select_does_not_crash_on_box_with_empty_bbox():
    # A malformed/degenerate OCR entry (no polygon points at all) must be
    # skipped, not crash the whole batch on one bad image. Real OCR always
    # returns a polygon, but this defends against a rare upstream glitch.
    boxes = [
        TextBox(text="소비기한", confidence=0.9, bbox=[]),
        TextBox(text="2026.07.15", confidence=0.9, bbox=[]),
        _box("2026.01.01", 0, 0),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 1, 1)


def test_select_never_picks_a_self_excluded_box_over_a_neutral_one():
    # Real case from final_cascade_ocr_boxes.csv (id=879): the anchor
    # keyword ("EXP.") sits in its own box, far from both date boxes, while
    # the manufacture-date box (which names itself "PROD") happens to sit
    # closer to that anchor than the real expiration-date box does (which
    # carries no keyword of its own) - a pure bbox-distance tie-break picks
    # the manufacture box. A box that names itself as an exclude-kind date
    # must never win, regardless of incidental distance.
    boxes = [
        _box("EXP.", 0, 0),
        _box("PROD. DATE:2020.07.15", 100, 100),
        _box("DATE:2021.05.11", 105, 105),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2021, 5, 11)


def test_select_prefers_sobigihan_over_yutonggihan_when_both_present():
    # Official rule 9: 소비기한 wins even when its date is spatially farther
    # than a 유통기한-associated date.
    boxes = [
        _box("유통기한", 0, 0),
        _box("2026.01.01", 0, 1),
        _box("소비기한", 0, 100),
        _box("2026.07.01", 0, 110),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 7, 1)


def test_select_prefers_later_date_over_coincidental_proximity_to_anchor():
    # Real-world pattern (confirmed against final_cascade_ocr_boxes.csv
    # id=245/1747/1780): a wrong, earlier date can sit closer to "소비기한"
    # by a few pixels than the real, later expiration date does. An
    # expiration date is virtually always the later one, so that should win
    # over raw pixel distance among otherwise-tied candidates.
    boxes = [
        _box("소비기한", 0, 0),
        _box("2026.01.01", 0, 1),
        _box("2026.07.01", 0, 50),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 7, 1)


def test_select_ignores_exclude_keyword_when_no_anchor_present():
    boxes = [
        _box("제조일자", 0, 0),
        _box("2026.01.01", 0, 5),
    ]
    best = select_final_date(boxes)
    assert best.result == DateResult(2026, 1, 1)
