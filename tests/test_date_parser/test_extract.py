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


def test_finds_multiple_non_overlapping_dates():
    tokens = extract_date_tokens("제조일자 2026.01.01 소비기한 2026.07.01")
    assert len(tokens) == 2


def test_confusable_digits_extracted():
    tokens = extract_date_tokens("2O26.O1.15")
    assert len(tokens) == 1
    assert _fields(tokens[0]) == (("2O26", "num"), ("O1", "num"), ("15", "num"))


def test_no_date_in_plain_text():
    assert extract_date_tokens("제품명: 오리지널 감자칩 120g") == []
