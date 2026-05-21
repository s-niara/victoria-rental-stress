"""
Ingest the DFFH historical affordability time series and save to parquet.

Usage:
    python scripts/ingest_dffh_affordability.py

Reads from:
    data/raw/Affordable rental dwellings by Local Government Area - September quarter 2025.xlsx

Writes to:
    data/processed/dffh_lga_affordability.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.parse_dffh import parse_afford_file  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "dffh_lga_affordability.parquet"


def find_latest_affordability_file() -> Path:
    """Find the most recent affordability file in data/raw/."""
    # Try the typical naming pattern; fall back to a looser glob.
    patterns = [
        "Affordable rental dwellings by Local Government Area - September quarter 2025.xlsx",
        "Affordable rental dwellings by Local Government Area - September quarter 2025.xlsx",
    ]
    for pattern in patterns:
        candidates = sorted(RAW_DIR.glob(pattern), reverse=True)
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"No DFFH affordability file found in {RAW_DIR}. "
        "Download from https://www.dffh.vic.gov.au/publications/rental-report "
        "and place in data/raw/."
    )


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    source = find_latest_affordability_file()
    logger.info(f"Source file: {source.name}")

    df = parse_afford_file(source)

    df.to_parquet(OUTPUT_PATH, index=False)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    logger.success(
        f"Wrote {len(df):,} rows to {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"({size_kb:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
