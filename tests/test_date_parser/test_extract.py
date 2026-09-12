from date_parser.extract import extract_date_tokens


def _fields(token):
    return tuple((f.raw, f.kind) for f in token.fields)


def test_finds_explicit_korean_ymd():
    tokens = extract_date_tokens("소비기한 2026년 01월 15일까지")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles == ("year", "month", "day")
    assert _fields(token) == (("2026", "num"), ("01", "num"), ("15", "num"))


def test_finds_partial_korean_year_month_only():
    tokens = extract_date_tokens("2026년 01월 소비기한")
    assert len(tokens) == 1
    assert tokens[0].fixed_roles == ("year", "month")


def test_finds_partial_korean_month_day_only():
    tokens = extract_date_tokens("01월 15일까지 섭취")
    assert len(tokens) == 1
    assert tokens[0].fixed_roles == ("month", "day")


def test_full_korean_pattern_wins_over_partial():
    tokens = extract_date_tokens("2026년 01월 15일")
    assert len(tokens) == 1
    assert tokens[0].fixed_roles == ("year", "month", "day")


def test_finds_ambiguous_numeric_triple():
    tokens = extract_date_tokens("EXP 26.06.20")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles is None
    assert _fields(token) == (("26", "num"), ("06", "num"), ("20", "num"))


def test_finds_month_name_token():
    tokens = extract_date_tokens("BEST BEFORE 26-JUN-2020")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("26", "num"), ("JUN", "month_name"), ("2020", "num"))


def test_finds_month_name_with_two_digit_year():
    # Real case from the label sample: "23-Jul-21"
    tokens = extract_date_tokens("23-Jul-21")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("23", "num"), ("Jul", "month_name"), ("21", "num"))


def test_finds_month_name_first_then_day_then_year():
    # Real case from the label sample: "JUN 28 2021"
    tokens = extract_date_tokens("JUN 28 2021")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles is None
    assert _fields(token) == (("JUN", "month_name"), ("28", "num"), ("2021", "num"))


def test_finds_month_name_and_year_only_no_separator():
    # Real case from the label sample: "JUL2023" (day missing -> partial NONE)
    tokens = extract_date_tokens("JUL2023")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles == ("month", "year")
    assert _fields(token) == (("JUL", "month_name"), ("2023", "num"))


def test_finds_month_name_glued_to_digits_no_separator():
    # Real case from label2.xlsx (id=3310): "AUG292020" (AUG + day 29 + year 2020)
    tokens = extract_date_tokens("AUG292020")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles is None
    assert _fields(token) == (("AUG", "month_name"), ("29", "num"), ("2020", "num"))


def test_finds_date_with_multi_character_separator():
    # Real case from label2.xlsx (id=2990): "2021. 03.20" (period AND space between year/month)
    tokens = extract_date_tokens("2021. 03.20x")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2021", "num"), ("03", "num"), ("20", "num"))


def test_finds_day_glued_to_month_name_no_separator():
    # Real case from labels_300.csv (id=2728): "04NOV 2021" (day + AUG glued,
    # space only before the year)
    tokens = extract_date_tokens("04NOV 2021")
    assert len(tokens) == 1
    token = tokens[0]
    assert token.fixed_roles is None
    assert _fields(token) == (("04", "num"), ("NOV", "month_name"), ("2021", "num"))


def test_finds_year_month_day_glued_with_no_internal_separator():
    # Real case from labels_300.csv (id=2981): "2021.1217" (month+day glued
    # together right after the year separator)
    tokens = extract_date_tokens("2021.1217")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2021", "num"), ("12", "num"), ("17", "num"))


def test_finds_year_month_day_with_stray_punctuation_between_month_and_day():
    # Real case from labels_300.csv (id=2134): "2022.11:02" (OCR misread the
    # month/day separator as a colon instead of a period)
    tokens = extract_date_tokens("2022.11:02")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2022", "num"), ("11", "num"), ("02", "num"))


def test_finds_date_with_comma_instead_of_period_separator():
    # Real cases from labels_300.csv (id=268, 287, 327, 1231): OCR sometimes
    # misreads a period as a comma, e.g. "26,07.14" or "27,02,18".
    assert _fields(extract_date_tokens("26,07.14")[0]) == (("26", "num"), ("07", "num"), ("14", "num"))
    assert _fields(extract_date_tokens("27,02,18")[0]) == (("27", "num"), ("02", "num"), ("18", "num"))
    assert _fields(extract_date_tokens("21,05.05 15:43")[0]) == (("21", "num"), ("05", "num"), ("05", "num"))


def test_finds_date_with_comma_as_second_separator():
    # Real case from labels_300.csv (id=2284): "22.01,06"
    tokens = extract_date_tokens("22.01,06")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("22", "num"), ("01", "num"), ("06", "num"))


def test_comma_separator_pattern_does_not_misfire_on_thousands_separated_numbers():
    # A price/weight like "1,350" or "20,000" must never be read as a date -
    # those always have a 3-digit group after the comma, which the
    # comma-tolerant pattern can't match (it's capped at 1-2 digits/group).
    assert extract_date_tokens("1,350kcal") == []
    assert extract_date_tokens("20,000mg") == []


def test_year_anchored_pattern_does_not_hijack_a_trailing_unrelated_number():
    # Real case from final_cascade_ocr_boxes.csv (id=690): "2025.10.11.22시"
    # is a complete date (2025-10-11) followed by an unrelated hour ("22시").
    # The comma/period-tolerant patterns must not skip the leading 4-digit
    # year and instead misread the trailing "10.11.22" as its own date.
    tokens = extract_date_tokens("2025.10.11.22시까지")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2025", "num"), ("10", "num"), ("11", "num"))


def test_finds_year_month_day_with_colon_between_year_and_month():
    # Real case from final_cascade_ocr_boxes.csv (id=384): "2026:07.08"
    # (OCR misread the year/month separator as a colon).
    tokens = extract_date_tokens("2026:07.08까지")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2026", "num"), ("07", "num"), ("08", "num"))


def test_finds_year_month_day_with_comma_between_month_and_day():
    # Real case from final_cascade_ocr_boxes.csv (id=366): "2026.09,05"
    tokens = extract_date_tokens("2026.09,05L2")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2026", "num"), ("09", "num"), ("05", "num"))


def test_finds_multiple_non_overlapping_dates():
    tokens = extract_date_tokens("제조일자 2026.01.01 소비기한 2026.07.01")
    assert len(tokens) == 2


def test_confusable_digits_extracted():
    tokens = extract_date_tokens("2O26.O1.15")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2O26", "num"), ("O1", "num"), ("15", "num"))


def test_no_date_in_plain_text():
    assert extract_date_tokens("제품명: 오리지널 감자칩 120g") == []
