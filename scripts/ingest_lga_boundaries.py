"""
Ingest the ABS LGA 2021 boundaries and save a Vic-only simplified GeoJSON.

Usage:
    python scripts/ingest_lga_boundaries.py

Reads from:
    data/raw/ABS_ASGS_Edition_3*Local_Government_Areas*.geojson

Writes to:
    data/reference/vic_lga_boundaries.geojson    (committed to git)

The reference file is small (~1.85 MB) and committed because:
  - The simplification + filtering is non-trivial to reproduce
  - It is the canonical map asset the dashboard depends on
  - Anyone cloning the repo should be able to render the dashboard immediately
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.parse_lga_boundaries import parse_lga_boundaries  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
OUTPUT_PATH = REFERENCE_DIR / "vic_lga_boundaries.geojson"


def find_latest_boundary_file() -> Path:
    """Find the most recent ABS LGA boundary GeoJSON in data/raw/."""
    patterns = [
        "ABS_ASGS_Edition_3*Local_Government_Areas*.geojson",
        "ABS_ASGS*LGA*.geojson",
    ]
    for pattern in patterns:
        candidates = sorted(RAW_DIR.glob(pattern), reverse=True)
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"No ABS LGA boundaries file found in {RAW_DIR}. "
        "Download from "
        "https://digital.atlas.gov.au/datasets/"
        "digitalatlas::abs-asgs-edition-3-2021-local-government-areas/about "
        "as GeoJSON and place in data/raw/."
    )


def main() -> int:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    source = find_latest_boundary_file()
    source_kb = source.stat().st_size / 1024
    logger.info(f"Source file: {source.name} ({source_kb:.1f} KB)")

    gdf = parse_lga_boundaries(source)

    gdf.to_file(OUTPUT_PATH, driver="GeoJSON")
    out_kb = OUTPUT_PATH.stat().st_size / 1024
    logger.success(
        f"Wrote {len(gdf)} LGAs to {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"({out_kb:.1f} KB - {(1 - out_kb/source_kb) * 100:.1f}% reduction)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
