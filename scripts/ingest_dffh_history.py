"""
Ingest the DFFH historical rental time series and save to parquet.

Usage:
    python scripts/ingest_dffh_history.py

Reads from:
    data/raw/quarterly-median-rents-local-government-area-*.xlsx

Writes to:
    data/processed/dffh_lga_rents.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.parse_dffh import parse_timeseries_file  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "dffh_lga_rents.parquet"


def find_latest_timeseries_file() -> Path:
    """Find the most recent 'Quarterly median rents by LGA' file in data/raw/."""
    candidates = sorted(
        RAW_DIR.glob("quarterly-median-rents-local-government-area-*.xlsx"),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No DFFH time-series file found in {RAW_DIR}. "
            "Download from https://www.dffh.vic.gov.au/publications/rental-report "
            "and place in data/raw/."
        )
    return candidates[0]


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    source = find_latest_timeseries_file()
    logger.info(f"Source file: {source.name}")

    df = parse_timeseries_file(source)

    df.to_parquet(OUTPUT_PATH, index=False)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    logger.success(
        f"Wrote {len(df):,} rows to {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"({size_kb:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
