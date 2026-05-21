"""
Parsers for DFFH Victorian Rental Report data files.

Two file types are supported:

1. 'Quarterly median rents by Local Government Area' (time series)
   - 7 sheets (one per property type + 'All Properties')
   - Wide format: each row is one LGA, each pair of columns is one quarter
   - Covers June 1999 to present (~26 years, ~106 quarters)
   - This is the spine of the project.

2. 'Tables from Rental Report' (current-quarter analytical report)
   - 33 sheets including affordability tables, regional rollups, etc.
   - Each file contains only ONE quarter of data
   - Useful for current-quarter detail not in the time series file
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

# Known region group labels that appear in col 0 of DFFH LGA tables.
KNOWN_REGIONS = {
    "Barwon South West",
    "Grampians",
    "Loddon Mallee",
    "Hume",
    "Gippsland",
    "North and West Metro",
    "Eastern Metro",
    "Southern Metro",
}

# LGA name corrections to standardise against ABS naming.
LGA_NAME_REPLACEMENTS = {
    "Mornington Penin'a": "Mornington Peninsula",
}

# Rows to skip in the time-series file (totals and rollups).
SKIP_LGA_VALUES = {"Group Total", "Victoria", "Metro", "Non-Metro", ""}

# Region labels that mark non-LGA sections to skip in the time-series file.
SKIP_REGION_SECTIONS = {"Table Total", "METRO NON-METRO"}

# Mapping from time-series sheet names to canonical property types.
TIMESERIES_SHEET_TO_PROPERTY: dict[str, str] = {
    "1br flat": "1 Bed Flat",
    "2br Flat": "2 Bed Flat",
    "3br Flat": "3 Bed Flat",
    "2br House": "2 Bed House",
    "3br House": "3 Bed House",
    "4br House": "4 Bed House",
}

# DFFH quarter labels use end-of-quarter months: Mar=Q1, Jun=Q2, Sep=Q3, Dec=Q4.
MONTH_TO_QUARTER = {"Mar": "Q1", "Jun": "Q2", "Sep": "Q3", "Dec": "Q4"}

# Column block structure for Table 13 (current-quarter file).
TABLE_13_PROPERTY_BLOCKS: list[tuple[int, str]] = [
    (2, "1 Bed Flat"),
    (5, "2 Bed Flat"),
    (8, "3 Bed Flat"),
    (11, "2 Bed House"),
    (14, "3 Bed House"),
    (17, "4 Bed House"),
]


@dataclass
class ParseResult:
    """Container for parsed DFFH data."""

    quarter: str
    median_rents: pd.DataFrame


def _coerce_numeric(val) -> float | pd._libs.missing.NAType:
    """
    Convert a DFFH cell value to numeric. '-' (suppressed) and blanks become NaN.
    """
    if pd.isna(val):
        return pd.NA
    if isinstance(val, str):
        s = val.strip()
        if s == "" or s == "-":
            return pd.NA
        try:
            return float(s)
        except ValueError:
            return pd.NA
    if isinstance(val, (int, float)):
        return float(val)
    return pd.NA


def _normalise_lga_name(name: str | float) -> str:
    """Standardise LGA names for downstream joins."""
    if pd.isna(name):
        return ""
    s = str(name).strip()
    return LGA_NAME_REPLACEMENTS.get(s, s)


def _parse_quarter_label(label) -> str | None:
    """
    Convert a DFFH quarter header label to canonical 'YYYY-QN' format.

    Examples:
        'Jun 1999' -> '1999-Q2'
        'Sep 2025' -> '2025-Q3'
    """
    if pd.isna(label):
        return None
    s = str(label).strip()
    m = re.match(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})", s
    )
    if not m:
        return None
    month, year = m.group(1), m.group(2)
    q = MONTH_TO_QUARTER.get(month)
    if not q:
        return None
    return f"{year}-{q}"


# ---------------------------------------------------------------------------
# Time-series file parser (the main entry point)
# ---------------------------------------------------------------------------


def parse_timeseries_sheet(
    xlsx_path: Path, sheet_name: str, property_type: str
) -> pd.DataFrame:
    """
    Parse one property-type sheet of the time-series file into long format.

    Args:
        xlsx_path: Path to the 'Quarterly median rents by LGA' file.
        sheet_name: Sheet name (e.g. '2br Flat').
        property_type: Canonical property type label (e.g. '2 Bed Flat').

    Returns:
        Long-format DataFrame with one row per (lga x quarter):
            quarter, region, lga, property_type, bond_count, median_weekly_rent
    """
    raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
    n_cols = raw.shape[1]

    # Build column index: c -> (quarter, metric)
    # Row 1 holds quarter labels (e.g. 'Jun 1999'); row 2 holds 'Count'/'Median'.
    col_info: dict[int, tuple[str, str]] = {}
    for c in range(2, n_cols):
        q_label = raw.iloc[1, c]
        metric = raw.iloc[2, c]
        if pd.notna(q_label) and pd.notna(metric):
            q = _parse_quarter_label(q_label)
            if q:
                col_info[c] = (q, str(metric).strip().lower())

    rows: list[dict] = []
    current_region: str | None = None

    for i in range(3, len(raw)):
        col0 = raw.iloc[i, 0]
        col1 = raw.iloc[i, 1]

        # Track current region group from col 0
        if pd.notna(col0) and str(col0).strip():
            current_region = str(col0).strip()

        # Skip non-LGA sections (Table Total, METRO NON-METRO)
        if current_region in SKIP_REGION_SECTIONS:
            continue

        if pd.isna(col1):
            continue

        lga_raw = str(col1).strip()
        if lga_raw in SKIP_LGA_VALUES or lga_raw in KNOWN_REGIONS:
            continue

        lga = _normalise_lga_name(lga_raw)
        if not lga:
            continue

        # Collect count/median pairs per quarter for this LGA
        quarter_data: dict[str, dict[str, float]] = {}
        for c, (q, metric) in col_info.items():
            quarter_data.setdefault(q, {})[metric] = _coerce_numeric(raw.iloc[i, c])

        for q, metrics in quarter_data.items():
            count = metrics.get("count", pd.NA)
            median = metrics.get("median", pd.NA)
            # Skip quarters where both values are suppressed
            if pd.isna(count) and pd.isna(median):
                continue
            rows.append(
                {
                    "quarter": q,
                    "region": current_region,
                    "lga": lga,
                    "property_type": property_type,
                    "bond_count": count,
                    "median_weekly_rent": median,
                }
            )

    return pd.DataFrame(rows)


def parse_timeseries_file(xlsx_path: Path) -> pd.DataFrame:
    """
    Parse the full 'Quarterly median rents by LGA' time-series file across
    all 6 property-type sheets, returning a single long-format DataFrame.

    Args:
        xlsx_path: Path to the time-series xlsx file.

    Returns:
        Long-format DataFrame with columns:
            quarter, region, lga, property_type, bond_count, median_weekly_rent
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"DFFH time-series file not found: {xlsx_path}")

    logger.info(f"Parsing DFFH time-series file: {xlsx_path.name}")

    frames: list[pd.DataFrame] = []
    for sheet_name, property_type in TIMESERIES_SHEET_TO_PROPERTY.items():
        df = parse_timeseries_sheet(xlsx_path, sheet_name, property_type)
        logger.info(
            f"  {sheet_name:12s} -> {property_type:12s}: "
            f"{len(df):6,d} rows, {df['lga'].nunique()} LGAs, "
            f"{df['quarter'].nunique()} quarters"
        )
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        f"Combined: {len(combined):,} rows, "
        f"{combined['lga'].nunique()} LGAs, "
        f"{combined['quarter'].nunique()} quarters "
        f"({combined['quarter'].min()} to {combined['quarter'].max()})"
    )
    return combined


# ---------------------------------------------------------------------------
# Current-quarter 'Tables from Rental Report' parser (kept for later use)
# ---------------------------------------------------------------------------


def parse_table_13(xlsx_path: Path, quarter: str) -> pd.DataFrame:
    """
    Parse Table 13 from the current-quarter 'Tables from Rental Report' file.

    Table 13 contains the same data as one quarter of the time-series file,
    but also includes the annual percentage change column. Useful when we
    want the official DFFH annual % change rather than computing our own.

    Args:
        xlsx_path: Path to the 'Tables from Rental Report' xlsx.
        quarter: Quarter string 'YYYY-QN'.

    Returns:
        Long-format DataFrame with columns:
            quarter, region, lga, property_type, bond_count,
            median_weekly_rent, annual_pct_change
    """
    raw = pd.read_excel(xlsx_path, sheet_name="Table 13", header=None)

    rows: list[dict] = []
    current_region: str | None = None

    for i in range(3, len(raw)):
        col0 = raw.iloc[i, 0]
        col1 = raw.iloc[i, 1]

        if pd.notna(col0) and str(col0).strip():
            current_region = str(col0).strip()

        if pd.isna(col1):
            continue
        lga_raw = str(col1).strip()
        if not lga_raw or lga_raw in KNOWN_REGIONS:
            continue

        lga = _normalise_lga_name(lga_raw)

        for start_col, property_type in TABLE_13_PROPERTY_BLOCKS:
            bond_count = _coerce_numeric(raw.iloc[i, start_col + 0])
            median_rent = _coerce_numeric(raw.iloc[i, start_col + 1])
            ann_pct = _coerce_numeric(raw.iloc[i, start_col + 2])

            if pd.isna(bond_count) and pd.isna(median_rent):
                continue

            rows.append(
                {
                    "quarter": quarter,
                    "region": current_region,
                    "lga": lga,
                    "property_type": property_type,
                    "bond_count": bond_count,
                    "median_weekly_rent": median_rent,
                    "annual_pct_change": ann_pct,
                }
            )

    return pd.DataFrame(rows)


def parse_dffh_quarterly_file(xlsx_path: Path, quarter: str) -> ParseResult:
    """High-level wrapper around parse_table_13."""
    median_rents = parse_table_13(xlsx_path, quarter)
    return ParseResult(quarter=quarter, median_rents=median_rents)
