"""Smoke tests for the DFFH parsers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.parse_dffh import (
    KNOWN_REGIONS,
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


# ---------------------------------------------------------------------------
# Time-series file (main parser)
# ---------------------------------------------------------------------------


@pytest.fixture
def timeseries_file() -> Path:
    if not SAMPLE_TIMESERIES_FILE.exists():
        pytest.skip(f"Time-series file not present at {SAMPLE_TIMESERIES_FILE}")
    return SAMPLE_TIMESERIES_FILE


def test_timeseries_sheet_parses_2br_flat(timeseries_file: Path) -> None:
    df = parse_timeseries_sheet(timeseries_file, "2br Flat", "2 Bed Flat")
    assert len(df) > 5000, "expected thousands of rows across 26+ years"
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

    # We expect tens of thousands of rows across the full time series
    assert len(df) > 30_000

    # All 6 property types
    assert df["property_type"].nunique() == 6

    # All 8 regions
    assert set(df["region"].dropna().unique()) == KNOWN_REGIONS

    # No rollup rows leaked through
    bad = {"Victoria", "Metro", "Non-Metro", "Group Total"}
    assert not df["lga"].isin(bad).any()

    # Quarters cover at least 25 years
    assert df["quarter"].nunique() >= 100


def test_timeseries_quarter_format(timeseries_file: Path) -> None:
    df = parse_timeseries_file(timeseries_file)
    sample = df["quarter"].iloc[0]
    # 'YYYY-QN' format
    assert len(sample) == 7
    assert sample[4] == "-"
    assert sample[5] == "Q"
    assert sample[6] in "1234"


def test_timeseries_normalises_mornington(timeseries_file: Path) -> None:
    df = parse_timeseries_file(timeseries_file)
    assert "Mornington Peninsula" in df["lga"].values
    assert "Mornington Penin'a" not in df["lga"].values


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
