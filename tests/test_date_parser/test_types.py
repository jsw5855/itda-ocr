from date_parser.types import DateResult


def test_final_date_string_collapses_to_none_only_when_fully_empty():
    # Contest output format: final_date is the single string "NONE" only when
    # year/month/day are all unknown.
    assert DateResult().final_date_string() == "NONE"


def test_final_date_string_keeps_partial_none_hyphenated():
    # A partial result still carries real information (year/month here), so
    # it must not collapse to the bare "NONE" string.
    assert DateResult(year=2026, month=1, day=None).final_date_string() == "2026-01-NONE"
    assert DateResult(year=2026, month=None, day=None).final_date_string() == "2026-NONE-NONE"


def test_final_date_string_formats_complete_date():
    assert DateResult(year=2026, month=7, day=15).final_date_string() == "2026-07-15"
