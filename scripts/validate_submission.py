"""Validate a submission.csv against the official ITDA output schema.

DRAFT — not wired into predict.ipynb or any pipeline. Written for review
only; not committed/pushed without approval.

Usage:
    python scripts/validate_submission.py path/to/submission.csv

Checks performed (see report for the source of each rule):
    - exactly the 5 required columns, in order: image_id, year, month, day, final_date
    - no duplicate image_id
    - no empty/blank image_id
    - year is "NONE" or a 4-digit string
    - month is "NONE" or "01".."12"
    - day is "NONE" or "01".."31"
    - if year/month/day are all "NONE", final_date is exactly "NONE"
    - otherwise final_date is exactly "{year}-{month}-{day}"
    - the CSV has no pandas index column (first column must be "image_id",
      not an unnamed integer index column)

RESOLVED (was a BLOCKER): image_id is the literal filename with its
extension stripped, e.g. "000018" for 000018.jpg - NOT the bare "18" that
labels_300.csv's own image_id column uses. This is now enforced by
default. Note this means anything that builds submission.csv from
labels_300.csv's image_id column directly (rather than from the real
input filename) will produce the WRONG id and fail this check - the
actual submission code must derive image_id from the test image's
filename itself (e.g. Path(file).stem), not from any labels file.
Pass --no-image-id-check to skip this if you specifically need to.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["image_id", "year", "month", "day", "final_date"]


def validate(csv_path: Path, check_image_id_format: bool = True, image_dir: Path | None = None) -> list[str]:
    errors: list[str] = []

    raw_columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
    if raw_columns and raw_columns[0].lower().startswith("unnamed"):
        errors.append(
            f"첫 번째 컬럼이 '{raw_columns[0]}'입니다 - CSV 저장 시 index=False가 "
            "빠진 것으로 보입니다 (pandas 기본 index가 컬럼으로 저장됨)."
        )

    if raw_columns != REQUIRED_COLUMNS:
        errors.append(
            f"컬럼이 공식 스키마와 다릅니다. 기대: {REQUIRED_COLUMNS}, 실제: {raw_columns}"
        )
        # Column mismatch makes the rest of the checks unreliable; stop here.
        return errors

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

    image_ids = df["image_id"]
    if (image_ids.str.strip() == "").any():
        blank_rows = df.index[image_ids.str.strip() == ""].tolist()
        errors.append(f"image_id가 빈 값인 행이 있습니다: {blank_rows[:10]}")

    duplicated = image_ids[image_ids.duplicated()].unique().tolist()
    if duplicated:
        errors.append(f"중복된 image_id가 있습니다: {duplicated[:10]}")

    if check_image_id_format:
        # Confirmed reading of "확장자를 제외한 이미지 파일명": e.g. "000018"
        # for 000018.jpg, NOT the bare "18" labels_300.csv uses internally.
        # A bare alphanumeric-shape check can't tell "18" from "000018" -
        # both look like valid ids - so this only catches structurally
        # wrong ids (spaces, extensions left in, etc). Pass --image-dir for
        # the check that actually matters: does a file with exactly this
        # stem exist.
        bad = df.loc[~image_ids.str.fullmatch(r"[0-9A-Za-z_-]+")]
        if not bad.empty:
            errors.append(f"image_id가 파일명 형식이 아닌 행이 있습니다: {bad['image_id'].tolist()[:10]}")

    if image_dir is not None:
        existing_stems = {p.stem for p in image_dir.iterdir() if p.is_file()}
        missing = [i for i in image_ids if i not in existing_stems]
        if missing:
            errors.append(
                f"{image_dir}에서 파일명(확장자 제외)이 정확히 일치하는 이미지를 못 찾은 image_id "
                f"{len(missing)}건 (예: {missing[:10]}) - 앞자리 0이 빠졌거나 다른 값일 가능성이 있습니다."
            )

    year_ok = image_ids.index[df["year"].apply(lambda v: v == "NONE" or bool(re.fullmatch(r"\d{4}", v)))]
    bad_year = df.index.difference(year_ok)
    if len(bad_year):
        errors.append(f"year가 NONE도 4자리 숫자도 아닌 행: {df.loc[bad_year, ['image_id', 'year']].to_dict('records')[:10]}")

    def month_ok(v: str) -> bool:
        return v == "NONE" or (re.fullmatch(r"\d{2}", v) is not None and 1 <= int(v) <= 12)

    bad_month = df.index[~df["month"].apply(month_ok)]
    if len(bad_month):
        errors.append(f"month가 NONE도 01~12도 아닌 행: {df.loc[bad_month, ['image_id', 'month']].to_dict('records')[:10]}")

    def day_ok(v: str) -> bool:
        return v == "NONE" or (re.fullmatch(r"\d{2}", v) is not None and 1 <= int(v) <= 31)

    bad_day = df.index[~df["day"].apply(day_ok)]
    if len(bad_day):
        errors.append(f"day가 NONE도 01~31도 아닌 행: {df.loc[bad_day, ['image_id', 'day']].to_dict('records')[:10]}")

    def expected_final_date(row: pd.Series) -> str:
        if row["year"] == "NONE" and row["month"] == "NONE" and row["day"] == "NONE":
            return "NONE"
        return f"{row['year']}-{row['month']}-{row['day']}"

    expected = df.apply(expected_final_date, axis=1)
    mismatched = df.index[df["final_date"] != expected]
    if len(mismatched):
        sample = df.loc[mismatched, ["image_id", "year", "month", "day", "final_date"]].head(10)
        errors.append(f"final_date가 year/month/day 조합과 일치하지 않는 행:\n{sample.to_string(index=False)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--no-image-id-check",
        action="store_true",
        help="Skip the image_id filename-format check (on by default now that the format is confirmed).",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=None,
        help="Directory of the actual input images. If given, checks that each image_id matches a real file's stem exactly (catches '18' vs '000018').",
    )
    args = parser.parse_args()

    if not args.csv_path.is_file():
        print(f"파일을 찾을 수 없습니다: {args.csv_path}")
        return 2

    errors = validate(args.csv_path, check_image_id_format=not args.no_image_id_check, image_dir=args.image_dir)
    if errors:
        print(f"검증 실패: {len(errors)}건")
        for e in errors:
            print(f"- {e}")
        return 1

    print("검증 통과: 공식 스키마를 만족합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
