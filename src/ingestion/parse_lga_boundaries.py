"""
Parser for the ABS ASGS Edition 3 (2021) Local Government Areas GeoJSON.

This module takes the all-Australia LGA boundary file (~22 MB after extraction
to Victoria only, ~151 MB national source) and produces a simplified
Victoria-only GeoDataFrame suitable for use in the dashboard.

Three transformations are applied:
  1. Filter to Victorian LGAs only.
  2. Filter out administrative placeholders ('No usual address',
     'Migratory - Offshore - Shipping', 'Unincorporated Vic') so the
     boundary set matches the rents/income datasets exactly.
  3. Normalise LGA names to match DFFH canonical naming (same mapping used in
     parse_abs_income).
  4. Simplify polygons with Douglas-Peucker (default tol=0.0005) to reduce
     file size by ~12x with no visible loss at state-level zoom.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from loguru import logger

# Reuse the same LGA name mappings and exclusions as the income parser so the
# three datasets join cleanly. Single source of truth.
from src.ingestion.parse_abs_income import EXCLUDED_LGAS, LGA_NAME_MAPPING

# Douglas-Peucker simplification tolerance in degrees. 0.0005 produces a file
# roughly 1.85 MB with no perceptible loss of detail at state-level zoom.
# Decision documented in methodology.md.
DEFAULT_SIMPLIFY_TOLERANCE = 0.0005

# Columns to keep in the cleaned output. We drop the lengthy `asgs_loci_uri`
# and the various ObjectID / state code fields that aren't needed downstream.
OUTPUT_COLUMNS = [
    "lga_code_2021",
    "lga",  # renamed from lga_name_2021
    "area_albers_sqkm",
    "geometry",
]


def _normalise_lga_name(name: str) -> str:
    """Apply the name mapping (shared with parse_abs_income)."""
    if name is None:
        return ""
    s = str(name).strip()
    return LGA_NAME_MAPPING.get(s, s)


def parse_lga_boundaries(
    geojson_path: Path, simplify_tolerance: float | None = DEFAULT_SIMPLIFY_TOLERANCE
) -> gpd.GeoDataFrame:
    """
    Parse the ABS ASGS LGA boundaries GeoJSON into a clean Vic-only GeoDataFrame.

    Args:
        geojson_path: Path to the all-Australia ABS LGA boundary GeoJSON.
        simplify_tolerance: Douglas-Peucker tolerance in degrees. Use None to
            skip simplification (produces a ~22 MB Victoria file). Default
            0.0005 produces a ~1.85 MB file ideal for web dashboards.

    Returns:
        GeoDataFrame with one row per Victorian LGA:
            lga_code_2021, lga, area_albers_sqkm, geometry
    """
    if not geojson_path.exists():
        raise FileNotFoundError(f"LGA boundaries GeoJSON not found: {geojson_path}")

    logger.info(f"Reading LGA boundaries: {geojson_path.name}")
    gdf = gpd.read_file(geojson_path)
    logger.info(f"  Total LGAs (all Australia): {len(gdf)}")

    # Filter to Victoria
    vic = gdf[gdf["state_name_2021"] == "Victoria"].copy()
    logger.info(f"  Victorian LGAs: {len(vic)}")

    # Filter out administrative placeholders
    before = len(vic)
    vic = vic[~vic["lga_name_2021"].isin(EXCLUDED_LGAS)].copy()
    logger.info(f"  After excluding placeholders: {len(vic)} (-{before - len(vic)})")

    # Normalise names to match DFFH
    vic["lga"] = vic["lga_name_2021"].apply(_normalise_lga_name)

    # Simplify polygons
    if simplify_tolerance is not None:
        logger.info(f"  Simplifying polygons with tolerance={simplify_tolerance}")
        vic["geometry"] = vic.geometry.simplify(
            tolerance=simplify_tolerance, preserve_topology=True
        )

    # Keep only the columns we care about
    result = vic[OUTPUT_COLUMNS].copy()
    result = result.reset_index(drop=True)

    logger.info(f"  Output: {len(result)} Victorian LGAs ready for dashboard")
    return result
