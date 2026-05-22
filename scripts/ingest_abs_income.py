"""
Ingest the ABS Census 2021 G33 household income data and save to parquet.

Usage:
    python scripts/ingest_abs_income.py

Reads from:
    data/raw/ABS_2021_Census_G33_LGA*.csv

Writes to:
    data/processed/abs_lga_income.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.parse_abs_income import parse_g33  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "abs_lga_income.parquet"


def find_latest_g33_file() -> Path:
    """Find the most recent G33 CSV in data/raw/."""
    candidates = sorted(RAW_DIR.glob("ABS_2021_Census_G33_LGA*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No ABS G33 file found in {RAW_DIR}. "
            "Download from "
            "https://digital.atlas.gov.au/datasets/"
            "abs-2021-census-g33-total-household-income-weekly-by-household-composition-by-2021-lga "
            "and place in data/raw/."
        )
    return candidates[0]


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    source = find_latest_g33_file()
    logger.info(f"Source file: {source.name}")

    df = parse_g33(source)

    df.to_parquet(OUTPUT_PATH, index=False)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    logger.success(
        f"Wrote {len(df):,} rows to {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"({size_kb:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
