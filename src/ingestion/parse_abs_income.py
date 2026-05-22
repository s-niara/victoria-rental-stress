"""
Parser for ABS Census 2021 G33: Total household income (weekly) by household
composition, by Local Government Area (LGA), 2021.

Source: Digital Atlas of Australia, ABS Census 2021 G33 table.

The raw file is wide-format: each row is one LGA across all of Australia, with
51 income-band columns (17 income bands x 3 household types: Family, Non-family,
Total).

This parser:
  1. Filters to Victorian LGAs only (LGA codes starting with '2').
  2. Drops non-real LGAs ('No usual address', 'Migratory - Offshore - Shipping',
     'Unincorporated Vic').
  3. Strips '(Vic.)' suffix from LGA names to match DFFH naming.
  4. Computes weighted median weekly household income per LGA from the
     income-band distribution.
  5. Computes the 25th percentile weekly household income (for sensitivity work
     on lower-income rental stress).
  6. Returns a tidy DataFrame with one row per LGA.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

# Income bands as published in G33, with low/high bounds in $/week.
# The open-ended top band ($4000+) uses a conservative midpoint cap.
# This is a documented analytical decision (see methodology.md).
INCOME_BANDS: list[tuple[str, float, float]] = [
    ("Negative Nil income", 0.0, 0.0),
    ("$1-$149", 1.0, 149.0),
    ("$150-$299", 150.0, 299.0),
    ("$300-$399", 300.0, 399.0),
    ("$400-$499", 400.0, 499.0),
    ("$500-$649", 500.0, 649.0),
    ("$650-$799", 650.0, 799.0),
    ("$800-$999", 800.0, 999.0),
    ("$1000-$1249", 1000.0, 1249.0),
    ("$1250-$1449", 1250.0, 1449.0),
    ("$1500-$1749", 1500.0, 1749.0),
    ("$1750-$1999", 1750.0, 1999.0),
    ("$2000-$2499", 2000.0, 2499.0),
    ("$2500-$2999", 2500.0, 2999.0),
    ("$3000-$3499", 3000.0, 3499.0),
    ("$3500-$3999", 3500.0, 3999.0),
    ("$4000 or more", 4000.0, 5000.0),
]

# LGA names to exclude (administrative placeholders, not real councils).
EXCLUDED_LGAS = {
    "No usual address (Vic.)",
    "Migratory - Offshore - Shipping (Vic.)",
    "Unincorporated Vic",
    "Unincorporated Vic.",
}

# Map G33 LGA names to canonical names matching DFFH.
# - '(Vic.)' suffix is stripped from LGAs that share names with councils in
#   other states (Bayside, Kingston, Latrobe).
# - DFFH uses 'Colac-Otway' (hyphen); Census uses 'Colac Otway' (space).
# - 'Moreland' was renamed 'Merri-bek' in 2022. Census 2021 has the old name;
#   DFFH uses the new name. Map to current name.
# - 'Mornington Penin'a' is the DFFH abbreviation; included for symmetry.
LGA_NAME_MAPPING = {
    "Bayside (Vic.)": "Bayside",
    "Kingston (Vic.)": "Kingston",
    "Latrobe (Vic.)": "Latrobe",
    "Colac Otway": "Colac-Otway",
    "Moreland": "Merri-bek",
    "Mornington Penin'a": "Mornington Peninsula",
}


def _strip_vic_suffix(name: str) -> str:
    """Apply name mapping and tidy whitespace."""
    s = name.strip() if isinstance(name, str) else name
    return LGA_NAME_MAPPING.get(s, s)


def _weighted_quantile_from_bands(
    band_counts: list[tuple[float, float, float]], quantile: float
) -> float | None:
    """
    Compute an interpolated quantile from binned counts.

    Args:
        band_counts: List of (low, high, count) tuples in ascending order.
        quantile: Target quantile in [0, 1], e.g. 0.5 for median.

    Returns:
        Estimated quantile value, or None if total count is zero or all NaN.

    Methodology:
        Identifies the band containing the target rank, then linearly
        interpolates within that band assuming uniform distribution.
        This is the standard 'histogram quantile' approach used for binned data.
    """
    valid = [(lo, hi, c) for lo, hi, c in band_counts if not pd.isna(c) and c > 0]
    if not valid:
        return None

    total = sum(c for _, _, c in valid)
    if total == 0:
        return None

    target = total * quantile
    cumulative = 0.0
    for lo, hi, c in valid:
        cumulative += c
        if cumulative >= target:
            prev_cum = cumulative - c
            frac = (target - prev_cum) / c if c > 0 else 0.0
            return lo + (hi - lo) * frac

    # Fallback (shouldn't reach here): return top band's upper bound
    return valid[-1][1]


def parse_g33(csv_path: Path) -> pd.DataFrame:
    """
    Parse the ABS Census 2021 G33 CSV into a tidy per-LGA DataFrame.

    Args:
        csv_path: Path to the G33 CSV downloaded from Digital Atlas Australia.

    Returns:
        Long-format DataFrame with one row per Victorian LGA:
            lga_code, lga, total_households,
            median_weekly_household_income, p25_weekly_household_income,
            count_<band_name>... (17 band-count columns)
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"G33 CSV not found: {csv_path}")

    logger.info(f"Parsing ABS Census G33 file: {csv_path.name}")

    raw = pd.read_csv(csv_path)

    code_col = "Local Government Areas 2021 code"
    name_col = "Local Government Areas 2021 name"
    total_col = "Household Income: Total: Total"

    # Filter to Victoria (LGA codes starting with '2')
    raw["_code_str"] = raw[code_col].astype(str)
    vic = raw[raw["_code_str"].str.startswith("2")].copy()
    logger.info(f"  Victorian LGAs in source: {len(vic)}")

    rows: list[dict] = []
    for _, row in vic.iterrows():
        raw_name = row[name_col]
        if raw_name in EXCLUDED_LGAS:
            continue

        lga_name = _strip_vic_suffix(raw_name)
        lga_code = str(row[code_col])
        total_hh = row[total_col]

        # Gather band counts in order
        band_data: list[tuple[float, float, float]] = []
        rec: dict = {
            "lga_code": lga_code,
            "lga": lga_name,
            "total_households": total_hh,
        }
        for band_name, lo, hi in INCOME_BANDS:
            col = f"Household Income: {band_name}: Total"
            count = row[col]
            rec[f"count_{band_name}"] = count
            band_data.append((lo, hi, count))

        rec["median_weekly_household_income"] = _weighted_quantile_from_bands(
            band_data, 0.50
        )
        rec["p25_weekly_household_income"] = _weighted_quantile_from_bands(
            band_data, 0.25
        )
        rows.append(rec)

    df = pd.DataFrame(rows)
    logger.info(
        f"  Output: {len(df)} Victorian LGAs after filtering "
        f"({len(EXCLUDED_LGAS & set(vic[name_col]))} excluded)"
    )
    logger.info(
        f"  Median income range: "
        f"${df['median_weekly_household_income'].min():.0f} - "
        f"${df['median_weekly_household_income'].max():.0f}/week"
    )
    return df
