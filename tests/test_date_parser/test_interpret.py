from date_parser.extract import RawDateToken, RawField
from date_parser.interpret import generate_candidates
from date_parser.types import DateResult


def _token(fields, role_universe, fixed_roles=None):
    parsed = tuple(RawField(raw=raw, kind=kind) for raw, kind in fields)
    return RawDateToken(span=(0, 0), fields=parsed, role_universe=role_universe, fixed_roles=fixed_roles)


def test_fixed_roles_full_ymd():
    token = _token([("2026", "num"), ("01", "num"), ("15", "num")], ("year", "month", "day"), fixed_roles=("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2026, 1, 15)


def test_default_window_covers_real_observed_label_range():
    # From 150-image label sample: observed years span 2018-2028.
    token_2018 = _token([("2018", "num"), ("01", "num"), ("15", "num")], ("year", "month", "day"), fixed_roles=("year", "month", "day"))
    assert generate_candidates(token_2018)[0].date == DateResult(2018, 1, 15)

    token_2028 = _token([("2028", "num"), ("01", "num"), ("15", "num")], ("year", "month", "day"), fixed_roles=("year", "month", "day"))
    assert generate_candidates(token_2028)[0].date == DateResult(2028, 1, 15)


def test_fixed_roles_partial_year_month_gives_none_day():
    token = _token([("2026", "num"), ("01", "num")], ("year", "month"), fixed_roles=("year", "month"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2026, 1, None)


def test_fixed_roles_partial_month_day_gives_none_year():
    token = _token([("01", "num"), ("15", "num")], ("month", "day"), fixed_roles=("month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(None, 1, 15)


def test_ambiguous_triple_prefers_four_digit_year_regardless_of_position():
    # day.month.year, with the 4-digit field unambiguously the year
    token = _token([("15", "num"), ("01", "num"), ("2026", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2026, 1, 15)


def test_ambiguous_two_digit_year_prefers_ymd_by_default():
    # Real, untagged cases from the label sample confirm the untagged
    # majority format is YMD (year-first), not DMY - e.g. "26.09.24" is
    # labeled 2026-09-24, and "21.02.22" is labeled 2021-02-22.
    token = _token([("26", "num"), ("09", "num"), ("24", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2026, 9, 24)

    token2 = _token([("21", "num"), ("02", "num"), ("22", "num")], ("year", "month", "day"))
    candidates2 = generate_candidates(token2)
    assert candidates2[0].date == DateResult(2021, 2, 22)


def test_ambiguous_two_digit_year_prefers_dmy_over_mdy_when_ymd_is_invalid():
    # "05.07.21": YMD reading needs "05" to be a year (2005, outside the
    # configured window) so it's eliminated outright, leaving only the
    # genuine DMY (2021-07-05) vs MDY (2021-05-07) choice - DMY should win
    # (21:2 in the label sample's explicit format tags).
    token = _token([("05", "num"), ("07", "num"), ("21", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2021, 7, 5)


def test_ambiguous_triple_eliminates_invalid_month():
    # 26 can't be a month or day-of-month for a Feb-shaped guess; only
    # (year=2026, month=06, day=20)-style readings survive validation.
    token = _token([("26", "num"), ("06", "num"), ("20", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert all(1 <= c.date.month <= 12 for c in candidates)
    assert all(1 <= c.date.day <= 31 for c in candidates)
    top = candidates[0].date
    assert top.year is not None and top.month == 6


def test_calendar_invalid_day_degrades_to_partial_none_ambiguous():
    # Feb 30 never exists, but year=2026/month=02 are each independently
    # readable and every other permutation is invalid outright (30 can't be
    # a month or day-of-month elsewhere) -> keep year/month, NONE just the day.
    token = _token([("2026", "num"), ("02", "num"), ("30", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates
    assert candidates[0].date == DateResult(2026, 2, None)


def test_calendar_invalid_day_degrades_to_partial_none_fixed_roles():
    token = _token([("2026", "num"), ("02", "num"), ("30", "num")], ("year", "month", "day"), fixed_roles=("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2026, 2, None)


def test_strict_candidates_always_preferred_over_degraded():
    # Both readings validate fully as real calendar dates, so neither should
    # ever be degraded/dropped in favor of the other.
    token = _token([("15", "num"), ("06", "num"), ("2026", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert all(c.date.day is not None for c in candidates)


def test_no_field_can_serve_as_day_still_returns_empty():
    # None of these values can ever resolve to a valid year under the
    # configured window, so there is nothing to degrade either.
    token = _token([("00", "num"), ("13", "num"), ("40", "num")], ("year", "month", "day"))
    assert generate_candidates(token) == []


def test_two_digit_year_expands_within_configured_window():
    token = _token([("26", "num"), ("01", "num"), ("15", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token, year_min=2020, year_max=2035)
    assert any(c.date.year == 2026 for c in candidates)


def test_two_digit_year_out_of_window_is_rejected():
    token = _token([("99", "num"), ("01", "num"), ("15", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token, year_min=2020, year_max=2035)
    assert all(c.date.year != 1999 and c.date.year != 2099 for c in candidates)


def test_month_name_with_two_digit_year_prefers_dmy():
    # Real cases from the label sample: "23-Jul-21" -> 2021-07-23,
    # "19-Mar-22" -> 2022-03-19. An English month name is itself evidence
    # the format isn't the numeric-only YMD majority, so day-month-year
    # wins here even though year-month-day wins for plain numeric triples.
    token = _token([("23", "num"), ("JUL", "month_name"), ("21", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates[0].date == DateResult(2021, 7, 23)

    token2 = _token([("19", "num"), ("MAR", "month_name"), ("22", "num")], ("year", "month", "day"))
    candidates2 = generate_candidates(token2)
    assert candidates2[0].date == DateResult(2022, 3, 19)


def test_month_name_field_must_play_month_role():
    token = _token([("15", "num"), ("JUN", "month_name"), ("2026", "num")], ("year", "month", "day"))
    candidates = generate_candidates(token)
    assert candidates
    assert all(c.date.month == 6 for c in candidates)
