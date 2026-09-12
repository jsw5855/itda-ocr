from date_parser.parser import parse_expiration_date
from date_parser.types import TextBox


def test_parses_dict_input_matching_common_ocr_interface():
    ocr_results = [
        {"text": "소비기한", "confidence": 0.95, "bbox": [[0, 100], [10, 100], [10, 105], [0, 105]]},
        {"text": "2026.07.15", "confidence": 0.9, "bbox": [[0, 105], [40, 105], [40, 110], [0, 110]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result == {"year": "2026", "month": "07", "day": "15", "final_date": "2026-07-15"}


def test_parses_text_box_input():
    boxes = [TextBox(text="2026년 01월 15일", confidence=0.9, bbox=[[0, 0], [40, 0], [40, 5], [0, 5]])]
    result = parse_expiration_date(boxes)
    assert result["final_date"] == "2026-01-15"


def test_partial_none_when_day_unreadable():
    ocr_results = [{"text": "2026년 01월 소비기한", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]}]
    result = parse_expiration_date(ocr_results)
    assert result == {"year": "2026", "month": "01", "day": "NONE", "final_date": "2026-01-NONE"}


def test_partial_none_when_day_is_calendar_invalid():
    ocr_results = [{"text": "소비기한 2026.02.30", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]}]
    result = parse_expiration_date(ocr_results)
    assert result == {"year": "2026", "month": "02", "day": "NONE", "final_date": "2026-02-NONE"}


def test_all_none_when_no_date_found():
    # Contest output format: individual year/month/day fields stay "NONE" each,
    # but final_date collapses to the single string "NONE" only when every
    # field is unknown - a partial result (e.g. "2026-01-NONE") must NOT
    # collapse, since that still carries real year/month information.
    ocr_results = [{"text": "영양성분표", "confidence": 0.9, "bbox": [[0, 0], [10, 0], [10, 5], [0, 5]]}]
    result = parse_expiration_date(ocr_results)
    assert result == {"year": "NONE", "month": "NONE", "day": "NONE", "final_date": "NONE"}


def test_manufacture_date_resolves_ymd_dmy_ambiguity_end_to_end():
    ocr_results = [
        {"text": "제조일자 2024년 01월 01일", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]},
        {"text": "소비기한 20.06.26", "confidence": 0.9, "bbox": [[0, 50], [40, 50], [40, 55], [0, 55]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2026-06-20"


def test_no_anchor_keyword_picks_latest_of_two_dates_end_to_end():
    ocr_results = [
        {"text": "2020.11.27", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]},
        {"text": "2021.08.26", "confidence": 0.9, "bbox": [[0, 50], [40, 50], [40, 55], [0, 55]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2021-08-26"


def test_picks_expiration_over_manufacture_date():
    ocr_results = [
        {"text": "제조일자 2026.01.01", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]},
        {"text": "소비기한 2026.07.01", "confidence": 0.9, "bbox": [[0, 50], [40, 50], [40, 55], [0, 55]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2026-07-01"


def test_prod_and_exp_date_in_separate_boxes_end_to_end():
    # Real case from labels_300.csv (id=879)
    ocr_results = [
        {"text": "PROD. DATE:15/07/2020", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]},
        {"text": "EXP. DATE:11/05/2021", "confidence": 0.9, "bbox": [[0, 20], [40, 20], [40, 25], [0, 25]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2021-05-11"


def test_year_month_day_glued_with_no_internal_separator_end_to_end():
    # Real case from labels_300.csv (id=2981)
    ocr_results = [{"text": "2021.1217", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]}]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2021-12-17"


def test_day_glued_to_month_name_end_to_end():
    # Real case from labels_300.csv (id=2728)
    ocr_results = [
        {"text": "BEST BEFORE", "confidence": 0.9, "bbox": [[0, 0], [40, 0], [40, 5], [0, 5]]},
        {"text": "04NOV 2021", "confidence": 0.9, "bbox": [[0, 20], [40, 20], [40, 25], [0, 25]]},
    ]
    result = parse_expiration_date(ocr_results)
    assert result["final_date"] == "2021-11-04"
