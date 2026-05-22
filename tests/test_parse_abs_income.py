"""Smoke tests for the ABS Census G33 income parser."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.parse_abs_income import (
    EXCLUDED_LGAS,
    INCOME_BANDS,
    _weighted_quantile_from_bands,
    parse_g33,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Find any G33 file in data/raw/ — filename has a random ID suffix
SAMPLE_FILES = sorted((REPO_ROOT / "data" / "raw").glob("ABS_2021_Census_G33_LGA*.csv"))
SAMPLE_FILE = SAMPLE_FILES[0] if SAMPLE_FILES else None


@pytest.fixture
def g33_file() -> Path:
    if SAMPLE_FILE is None or not SAMPLE_FILE.exists():
        pytest.skip("ABS Census G33 file not present in data/raw/")
    return SAMPLE_FILE


# ---------------------------------------------------------------------------
# Quantile interpolation logic
# ---------------------------------------------------------------------------


def test_quantile_simple_median() -> None:
    """Median of a single uniform band should sit at the midpoint."""
    bands = [(0.0, 100.0, 100.0)]
    assert _weighted_quantile_from_bands(bands, 0.5) == pytest.approx(50.0)


def test_quantile_across_two_equal_bands() -> None:
    """Median should sit at the upper edge of the first band."""
    bands = [(0.0, 100.0, 50.0), (100.0, 200.0, 50.0)]
    assert _weighted_quantile_from_bands(bands, 0.5) == pytest.approx(100.0)


def test_quantile_p25() -> None:
    """25th percentile in one uniform band should sit a quarter through."""
    bands = [(0.0, 100.0, 100.0)]
    assert _weighted_quantile_from_bands(bands, 0.25) == pytest.approx(25.0)


def test_quantile_handles_nan_counts() -> None:
    """Bands with NaN counts should be skipped, not crash."""
    bands = [(0.0, 100.0, float("nan")), (100.0, 200.0, 100.0)]
    assert _weighted_quantile_from_bands(bands, 0.5) == pytest.approx(150.0)


def test_quantile_returns_none_on_empty_data() -> None:
    """Empty input should produce None, not error."""
    assert _weighted_quantile_from_bands([], 0.5) is None
    assert _weighted_quantile_from_bands([(0.0, 100.0, 0.0)], 0.5) is None


# ---------------------------------------------------------------------------
# Full G33 parse
# ---------------------------------------------------------------------------


def test_parse_g33_returns_dataframe(g33_file: Path) -> None:
    df = parse_g33(g33_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 70, "expected at least 70 Victorian LGAs"


def test_parse_g33_expected_columns(g33_file: Path) -> None:
    df = parse_g33(g33_file)
    must_have = {
        "lga_code",
        "lga",
        "total_households",
        "median_weekly_household_income",
        "p25_weekly_household_income",
    }
    assert must_have.issubset(set(df.columns))


def test_parse_g33_filters_administrative_lgas(g33_file: Path) -> None:
    df = parse_g33(g33_file)
    for excluded in EXCLUDED_LGAS:
        # The mapping strips '(Vic.)' so check against the cleaned name too
        cleaned = excluded.replace(" (Vic.)", "")
        assert cleaned not in df["lga"].values, (
            f"{excluded} should have been filtered out"
        )


def test_parse_g33_income_sanity(g33_file: Path) -> None:
    """Median household income should be in a sane range for any Victorian LGA."""
    df = parse_g33(g33_file)
    income = df["median_weekly_household_income"].dropna()
    assert income.min() >= 500, "no Victorian LGA should have median < $500/week"
    assert income.max() <= 5000, "no Victorian LGA should have median > $5000/week"


def test_parse_g33_known_lga_check(g33_file: Path) -> None:
    """Boroondara is consistently one of Victoria's highest-income LGAs."""
    df = parse_g33(g33_file)
    boroondara = df[df["lga"] == "Boroondara"]
    assert len(boroondara) == 1
    median = boroondara["median_weekly_household_income"].iloc[0]
    # Boroondara should be in the top 5 - sanity check
    top_5_threshold = df["median_weekly_household_income"].nlargest(5).min()
    assert median >= top_5_threshold


def test_parse_g33_p25_below_median(g33_file: Path) -> None:
    """For every LGA, p25 must be at or below the median."""
    df = parse_g33(g33_file)
    paired = df.dropna(subset=["median_weekly_household_income", "p25_weekly_household_income"])
    assert (
        paired["p25_weekly_household_income"]
        <= paired["median_weekly_household_income"]
    ).all()


def test_parse_g33_band_counts_preserved(g33_file: Path) -> None:
    """Per-band counts should be retained for downstream use."""
    df = parse_g33(g33_file)
    for band_name, _, _ in INCOME_BANDS:
        assert f"count_{band_name}" in df.columns


# ---------------------------------------------------------------------------
# Cross-dataset join compatibility
# ---------------------------------------------------------------------------

DFFH_LGAS_PROCESSED = (
    REPO_ROOT / "data" / "processed" / "dffh_lga_rents.parquet"
)


def test_g33_lgas_match_dffh_lgas(g33_file: Path) -> None:
    """
    The G33 income LGAs must match exactly with the DFFH rental LGAs.

    If this test ever fails, it means a join between income and rents will
    silently drop rows. Add a mapping entry in LGA_NAME_MAPPING to fix.
    """
    if not DFFH_LGAS_PROCESSED.exists():
        pytest.skip(
            "DFFH processed file not present; run scripts/ingest_dffh_history.py first"
        )

    income = parse_g33(g33_file)
    dffh = pd.read_parquet(DFFH_LGAS_PROCESSED)

    income_set = set(income["lga"].unique())
    dffh_set = set(dffh["lga"].unique())

    only_in_income = income_set - dffh_set
    only_in_dffh = dffh_set - income_set

    assert not only_in_income and not only_in_dffh, (
        f"LGA name mismatch:\n"
        f"  In income but not in DFFH: {sorted(only_in_income)}\n"
        f"  In DFFH but not in income: {sorted(only_in_dffh)}"
    )
