from date_parser.keywords import ANCHOR_KEYWORDS, EXCLUDE_KEYWORDS, PRIMARY_ANCHOR_KEYWORDS, has_keyword


def test_sobigihan_and_sayonggihan_are_primary_anchor_keywords():
    # Official rule 9: 소비기한/사용기한 outrank 유통기한/etc when both are
    # present - 유통기한 must NOT be in PRIMARY_ANCHOR_KEYWORDS.
    assert PRIMARY_ANCHOR_KEYWORDS == ["소비기한", "사용기한"]
    assert has_keyword("소비기한 2026.07.15까지", PRIMARY_ANCHOR_KEYWORDS)
    assert has_keyword("사용기한 2026.07.15까지", PRIMARY_ANCHOR_KEYWORDS)
    assert not has_keyword("유통기한 2026.07.15까지", PRIMARY_ANCHOR_KEYWORDS)


def test_short_ascii_keyword_matches_as_standalone_token():
    assert has_keyword("PRO.DATE 2026.01.01", EXCLUDE_KEYWORDS)
    assert has_keyword("PACK DATE 2026.01.01", EXCLUDE_KEYWORDS)


def test_short_ascii_keyword_does_not_false_positive_inside_longer_word():
    assert not has_keyword("PROTEIN 20g", EXCLUDE_KEYWORDS)
    assert not has_keyword("ABBA 2026.06.20", ANCHOR_KEYWORDS)


def test_bb_matches_as_standalone_expiration_marker():
    assert has_keyword("BB 26.06.20", ANCHOR_KEYWORDS)


def test_prd_and_mfd_match_as_manufacture_keywords():
    assert has_keyword("EXP, PRD 같이 있음", EXCLUDE_KEYWORDS)
    assert has_keyword("MFD 2026.01.01", EXCLUDE_KEYWORDS)


def test_korean_keyword_still_matches_as_substring():
    assert has_keyword("소비기한 2026.07.15까지", ANCHOR_KEYWORDS)
    assert has_keyword("제조일자 2026.01.01", EXCLUDE_KEYWORDS)


def test_prod_and_exd_match_as_abbreviated_keywords():
    # Real case from labels_300.csv (id=879): "PROD. DATE" / "EXP. DATE"
    assert has_keyword("PROD. DATE:15/07/2020", EXCLUDE_KEYWORDS)
    # Real case from labels_300.csv (id=3238): "EXD" as a short form of "EXP"
    assert has_keyword("EXD: 16.10.2021", ANCHOR_KEYWORDS)


def test_no_match_on_unrelated_text():
    assert not has_keyword("영양성분표 100g당", ANCHOR_KEYWORDS)
    assert not has_keyword("영양성분표 100g당", EXCLUDE_KEYWORDS)
