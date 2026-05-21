"""Smoke tests for the DFFH parsers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.parse_dffh import (
    AFFORD_SHEET_TO_BEDROOM,
    KNOWN_REGIONS,
    parse_afford_file,
    parse_afford_sheet,
    parse_dffh_quarterly_file,
    parse_table_13,
    parse_timeseries_file,
    parse_timeseries_sheet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_TABLES_FILE = (
    REPO_ROOT
    / "data"
    / "raw"
    / "Tables_from_Rental_Report_-_September_Quarter_2025.xlsx"
)
SAMPLE_TIMESERIES_FILE = (
    REPO_ROOT
    / "data"
    / "raw"
    / "quarterly-median-rents-local-government-area-september-quarter-2025-excel.xlsx"
)
SAMPLE_AFFORD_FILE = (
    REPO_ROOT
    / "data"
    / "raw"
    / "Affordable_rental_dwellings_by_Local_Government_Area_-_September_quarter_2025.xlsx"
)


# ---------------------------------------------------------------------------
# Rents time-series file
# ---------------------------------------------------------------------------


@pytest.fixture
def timeseries_file() -> Path:
    if not SAMPLE_TIMESERIES_FILE.exists():
        pytest.skip(f"Time-series file not present at {SAMPLE_TIMESERIES_FILE}")
    return SAMPLE_TIMESERIES_FILE


def test_timeseries_sheet_parses_2br_flat(timeseries_file: Path) -> None:
    df = parse_timeseries_sheet(timeseries_file, "2br Flat", "2 Bed Flat")
    assert len(df) > 5000
    assert df["property_type"].unique().tolist() == ["2 Bed Flat"]
    assert df["quarter"].nunique() >= 100


def test_timeseries_file_full_parse(timeseries_file: Path) -> None:
    df = parse_timeseries_file(timeseries_file)

    expected_cols = {
        "quarter",
        "region",
        "lga",
        "property_type",
        "bond_count",
        "median_weekly_rent",
    }
    assert set(df.columns) == expected_cols
    assert len(df) > 30_000
    assert df["property_type"].nunique() == 6
    assert set(df["region"].dropna().unique()) == KNOWN_REGIONS

    bad = {"Victoria", "Metro", "Non-Metro", "Group Total"}
    assert not df["lga"].isin(bad).any()
    assert df["quarter"].nunique() >= 100


def test_timeseries_quarter_format(timeseries_file: Path) -> None:
    df = parse_timeseries_file(timeseries_file)
    sample = df["quarter"].iloc[0]
    assert len(sample) == 7
    assert sample[4] == "-"
    assert sample[5] == "Q"
    assert sample[6] in "1234"


def test_timeseries_normalises_mornington(timeseries_file: Path) -> None:
    df = parse_timeseries_file(timeseries_file)
    assert "Mornington Peninsula" in df["lga"].values
    assert "Mornington Penin'a" not in df["lga"].values


# ---------------------------------------------------------------------------
# Affordability time-series file
# ---------------------------------------------------------------------------


@pytest.fixture
def afford_file() -> Path:
    if not SAMPLE_AFFORD_FILE.exists():
        pytest.skip(f"Affordability file not present at {SAMPLE_AFFORD_FILE}")
    return SAMPLE_AFFORD_FILE


def test_afford_sheet_parses_1br(afford_file: Path) -> None:
    df = parse_afford_sheet(afford_file, "lga aff 1br", "1 Bedroom")
    assert len(df) > 5000
    assert df["bedroom_category"].unique().tolist() == ["1 Bedroom"]
    assert df["quarter"].nunique() >= 100


def test_afford_file_full_parse(afford_file: Path) -> None:
    df = parse_afford_file(afford_file)

    expected_cols = {
        "quarter",
        "lga",
        "bedroom_category",
        "affordable_lettings",
        "affordable_pct",
    }
    assert set(df.columns) == expected_cols
    assert len(df) > 30_000
    assert df["bedroom_category"].nunique() == 5
    assert set(df["bedroom_category"].unique()) == set(AFFORD_SHEET_TO_BEDROOM.values())

    bad = {"Victoria", "Metro", "Non-Metro", "Table Total", "Group Total"}
    assert not df["lga"].isin(bad).any()
    assert df["quarter"].nunique() >= 100


def test_afford_no_numeric_strings_as_lga(afford_file: Path) -> None:
    """Rollup row totals must not leak as LGAs."""
    df = parse_afford_file(afford_file)
    has_digit = df["lga"].apply(lambda s: any(c.isdigit() for c in s))
    assert not has_digit.any(), "LGA names should never contain digits"


def test_afford_percent_in_valid_range(afford_file: Path) -> None:
    df = parse_afford_file(afford_file)
    pct = df["affordable_pct"].dropna()
    assert pct.min() >= 0.0
    assert pct.max() <= 1.0


def test_afford_normalises_mornington(afford_file: Path) -> None:
    df = parse_afford_file(afford_file)
    assert "Mornington Peninsula" in df["lga"].values
    assert "Mornington Penin'a" not in df["lga"].values


def test_afford_and_rents_have_same_lgas(
    afford_file: Path, timeseries_file: Path
) -> None:
    """Sanity check: the two files should reference the same set of LGAs."""
    rents = parse_timeseries_file(timeseries_file)
    afford = parse_afford_file(afford_file)
    assert set(rents["lga"].unique()) == set(afford["lga"].unique())


# ---------------------------------------------------------------------------
# Tables file (current-quarter parser)
# ---------------------------------------------------------------------------


@pytest.fixture
def tables_file() -> Path:
    if not SAMPLE_TABLES_FILE.exists():
        pytest.skip(f"Tables file not present at {SAMPLE_TABLES_FILE}")
    return SAMPLE_TABLES_FILE


def test_parse_table_13(tables_file: Path) -> None:
    df = parse_table_13(tables_file, "2025-Q3")
    assert len(df) > 200
    assert "annual_pct_change" in df.columns


def test_parse_table_13_filters_rollups(tables_file: Path) -> None:
    df = parse_table_13(tables_file, "2025-Q3")
    assert not df["lga"].isin(KNOWN_REGIONS).any()


def test_parse_dffh_quarterly_file(tables_file: Path) -> None:
    result = parse_dffh_quarterly_file(tables_file, "2025-Q3")
    assert result.quarter == "2025-Q3"
    assert isinstance(result.median_rents, pd.DataFrame)
