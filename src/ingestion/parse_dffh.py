"""
Parsers for DFFH Victorian Rental Report data files.

Three file types are supported:

1. 'Quarterly median rents by Local Government Area' (rent time series)
   - 7 sheets (one per property type + 'All Properties')
   - Wide format: each row is one LGA, each pair of columns is one quarter
   - Covers June 1999 to present (~26 years, ~106 quarters)
   - This is the spine of the project.

2. 'Affordable rental dwellings by Local Government Area' (affordability time series)
   - 5 sheets (one per bedroom category + 'all bedrooms')
   - Wide format: each row is one LGA, each pair of columns is one quarter
     (Affordable lettings count + Percent affordable)
   - Covers March 2000 to present (~25.5 years, ~101 quarters)
   - Uses DFFH's official affordability methodology.

3. 'Tables from Rental Report' (current-quarter analytical report)
   - 33 sheets including affordability tables, regional rollups, etc.
   - Each file contains only ONE quarter of data
   - Useful for current-quarter detail not in the time series files.
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

# Rows to skip (totals and rollups).
SKIP_LGA_VALUES = {"Group Total", "Victoria", "Metro", "Non-Metro", ""}

# Region labels that mark non-LGA sections to skip.
SKIP_REGION_SECTIONS = {"Table Total", "METRO NON-METRO"}

# Mapping from rents time-series sheet names to canonical property types.
TIMESERIES_SHEET_TO_PROPERTY: dict[str, str] = {
    "1br flat": "1 Bed Flat",
    "2br Flat": "2 Bed Flat",
    "3br Flat": "3 Bed Flat",
    "2br House": "2 Bed House",
    "3br House": "3 Bed House",
    "4br House": "4 Bed House",
}

# Mapping from affordability time-series sheet names to bedroom categories.
AFFORD_SHEET_TO_BEDROOM: dict[str, str] = {
    "lga aff 1br": "1 Bedroom",
    "lga aff 2br": "2 Bedroom",
    "lga aff 3br": "3 Bedroom",
    "lga aff 4br": "4 Bedroom",
    "lga aff total": "All Bedrooms",
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
    """Convert a DFFH cell value to numeric. '-' (suppressed) and blanks become NaN."""
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
# Rents time-series file parser
# ---------------------------------------------------------------------------


def parse_timeseries_sheet(
    xlsx_path: Path, sheet_name: str, property_type: str
) -> pd.DataFrame:
    """
    Parse one property-type sheet of the rents time-series file into long format.

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

        if pd.notna(col0) and str(col0).strip():
            current_region = str(col0).strip()

        if current_region in SKIP_REGION_SECTIONS:
            continue

        if pd.isna(col1):
            continue

        lga_raw = str(col1).strip()
        # NOTE: do NOT also filter against KNOWN_REGIONS here. The City of Hume
        # (an LGA) shares its name with the Hume region; in the time-series
        # file regions only appear in col 0 as group headers, never in col 1.
        if lga_raw in SKIP_LGA_VALUES:
            continue

        lga = _normalise_lga_name(lga_raw)
        if not lga:
            continue

        quarter_data: dict[str, dict[str, float]] = {}
        for c, (q, metric) in col_info.items():
            quarter_data.setdefault(q, {})[metric] = _coerce_numeric(raw.iloc[i, c])

        for q, metrics in quarter_data.items():
            count = metrics.get("count", pd.NA)
            median = metrics.get("median", pd.NA)
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
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"DFFH rents time-series file not found: {xlsx_path}")

    logger.info(f"Parsing DFFH rents time-series file: {xlsx_path.name}")

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
        f"Combined rents: {len(combined):,} rows, "
        f"{combined['lga'].nunique()} LGAs, "
        f"{combined['quarter'].nunique()} quarters "
        f"({combined['quarter'].min()} to {combined['quarter'].max()})"
    )
    return combined


# ---------------------------------------------------------------------------
# Affordability time-series file parser
# ---------------------------------------------------------------------------


def parse_afford_sheet(
    xlsx_path: Path, sheet_name: str, bedroom_category: str
) -> pd.DataFrame:
    """
    Parse one bedroom-category sheet of the affordability time-series file
    into long format.

    Note: the affordability file's header structure differs from the rents file.
    - Quarter labels are on row 2 (rents file: row 1)
    - Metric labels are on row 3 (rents file: row 2)
    - Data starts at row 4 (rents file: row 3)
    - There is NO region column - only an LGA column at col 0 (rents: col 0 region, col 1 lga)
    - Metric labels are 'Affordable' / 'Percent' (rents: 'Count' / 'Median')

    Args:
        xlsx_path: Path to the 'Affordable rental dwellings by LGA' file.
        sheet_name: Sheet name (e.g. 'lga aff 1br').
        bedroom_category: Canonical bedroom label (e.g. '1 Bedroom').

    Returns:
        Long-format DataFrame with one row per (lga x quarter):
            quarter, lga, bedroom_category, affordable_lettings, affordable_pct
    """
    raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
    n_cols = raw.shape[1]

    # Build column index: c -> (quarter, metric)
    # Row 2 has quarter labels, row 3 has 'Affordable'/'Percent'.
    col_info: dict[int, tuple[str, str]] = {}
    for c in range(1, n_cols):
        q_label = raw.iloc[2, c]
        metric = raw.iloc[3, c]
        if pd.notna(q_label) and pd.notna(metric):
            q = _parse_quarter_label(q_label)
            if q:
                col_info[c] = (q, str(metric).strip().lower())

    rows: list[dict] = []

    # Data starts at row 4
    for i in range(4, len(raw)):
        col0 = raw.iloc[i, 0]

        if pd.isna(col0):
            continue

        col0_s = str(col0).strip()

        # Filter out rollup section markers and totals.
        # NOTE: do NOT filter against KNOWN_REGIONS here - in the affordability
        # file col 0 contains ONLY LGA names (e.g. 'Hume' is the LGA, not the
        # region). The affordability file has no region group headers at all.
        if col0_s in SKIP_REGION_SECTIONS:
            continue
        if col0_s in SKIP_LGA_VALUES:
            continue

        lga = _normalise_lga_name(col0_s)
        if not lga:
            continue

        quarter_data: dict[str, dict[str, float]] = {}
        for c, (q, metric) in col_info.items():
            quarter_data.setdefault(q, {})[metric] = _coerce_numeric(raw.iloc[i, c])

        for q, metrics in quarter_data.items():
            affordable = metrics.get("affordable", pd.NA)
            percent = metrics.get("percent", pd.NA)
            if pd.isna(affordable) and pd.isna(percent):
                continue
            rows.append(
                {
                    "quarter": q,
                    "lga": lga,
                    "bedroom_category": bedroom_category,
                    "affordable_lettings": affordable,
                    "affordable_pct": percent,
                }
            )

    return pd.DataFrame(rows)


def parse_afford_file(xlsx_path: Path) -> pd.DataFrame:
    """
    Parse the full 'Affordable rental dwellings by LGA' file across all
    5 bedroom-category sheets, returning a single long-format DataFrame.

    Args:
        xlsx_path: Path to the affordability xlsx file.

    Returns:
        Long-format DataFrame with columns:
            quarter, lga, bedroom_category, affordable_lettings, affordable_pct
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"DFFH affordability time-series file not found: {xlsx_path}"
        )

    logger.info(f"Parsing DFFH affordability file: {xlsx_path.name}")

    frames: list[pd.DataFrame] = []
    for sheet_name, bedroom in AFFORD_SHEET_TO_BEDROOM.items():
        df = parse_afford_sheet(xlsx_path, sheet_name, bedroom)
        logger.info(
            f"  {sheet_name:18s} -> {bedroom:13s}: "
            f"{len(df):6,d} rows, {df['lga'].nunique()} LGAs, "
            f"{df['quarter'].nunique()} quarters"
        )
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        f"Combined affordability: {len(combined):,} rows, "
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

    Table 13 contains LGA-level data including the annual percentage change
    column. Useful when we want the official DFFH annual % change rather
    than computing our own from the time series.
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
