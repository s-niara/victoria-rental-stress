"""Smoke tests for the ABS LGA boundary parser."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest

from src.ingestion.parse_lga_boundaries import (
    DEFAULT_SIMPLIFY_TOLERANCE,
    parse_lga_boundaries,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Find any ABS boundaries file in data/raw/
SAMPLE_FILES = sorted(
    (REPO_ROOT / "data" / "raw").glob("ABS_ASGS*Local_Government_Areas*.geojson")
)
SAMPLE_FILE = SAMPLE_FILES[0] if SAMPLE_FILES else None

# Cross-dataset reference
DFFH_RENTS = REPO_ROOT / "data" / "processed" / "dffh_lga_rents.parquet"
ABS_INCOME = REPO_ROOT / "data" / "processed" / "abs_lga_income.parquet"


@pytest.fixture
def boundary_file() -> Path:
    if SAMPLE_FILE is None or not SAMPLE_FILE.exists():
        pytest.skip("ABS LGA boundary file not present in data/raw/")
    return SAMPLE_FILE


# ---------------------------------------------------------------------------
# Basic parse correctness
# ---------------------------------------------------------------------------


def test_parse_returns_geodataframe(boundary_file: Path) -> None:
    gdf = parse_lga_boundaries(boundary_file)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.geometry.notna().all()


def test_parse_filters_to_victoria(boundary_file: Path) -> None:
    """After filtering, we should have exactly 79 Victorian LGAs."""
    gdf = parse_lga_boundaries(boundary_file)
    # Same count as DFFH and income datasets after exclusions
    assert len(gdf) == 79


def test_parse_expected_columns(boundary_file: Path) -> None:
    gdf = parse_lga_boundaries(boundary_file)
    must_have = {"lga_code_2021", "lga", "area_albers_sqkm", "geometry"}
    assert must_have.issubset(set(gdf.columns))


def test_parse_excludes_administrative_lgas(boundary_file: Path) -> None:
    gdf = parse_lga_boundaries(boundary_file)
    bad = {
        "No usual address (Vic.)",
        "Migratory - Offshore - Shipping (Vic.)",
        "Unincorporated Vic",
    }
    assert not gdf["lga"].isin(bad).any()


def test_parse_normalises_lga_names(boundary_file: Path) -> None:
    """Names should match DFFH canonical form, not raw ABS form."""
    gdf = parse_lga_boundaries(boundary_file)
    assert "Bayside" in gdf["lga"].values
    assert "Bayside (Vic.)" not in gdf["lga"].values
    assert "Kingston" in gdf["lga"].values
    assert "Kingston (Vic.)" not in gdf["lga"].values
    assert "Merri-bek" in gdf["lga"].values
    assert "Moreland" not in gdf["lga"].values
    assert "Colac-Otway" in gdf["lga"].values
    assert "Colac Otway" not in gdf["lga"].values


# ---------------------------------------------------------------------------
# Simplification behaviour
# ---------------------------------------------------------------------------


def test_simplify_reduces_polygon_complexity(boundary_file: Path) -> None:
    """Simplified polygons should have fewer vertices than the originals."""
    full = parse_lga_boundaries(boundary_file, simplify_tolerance=None)
    simplified = parse_lga_boundaries(
        boundary_file, simplify_tolerance=DEFAULT_SIMPLIFY_TOLERANCE
    )

    # Count coordinates in one large LGA (East Gippsland is detailed coastline)
    eg_full = full[full["lga"] == "East Gippsland"].iloc[0]
    eg_simp = simplified[simplified["lga"] == "East Gippsland"].iloc[0]

    # The simplified geometry should have meaningfully fewer points
    full_pts = len(eg_full.geometry.exterior.coords) if eg_full.geometry.geom_type == "Polygon" else sum(
        len(p.exterior.coords) for p in eg_full.geometry.geoms
    )
    simp_pts = len(eg_simp.geometry.exterior.coords) if eg_simp.geometry.geom_type == "Polygon" else sum(
        len(p.exterior.coords) for p in eg_simp.geometry.geoms
    )
    assert simp_pts < full_pts / 2, (
        f"Expected at least 2x reduction; got {full_pts} -> {simp_pts}"
    )


def test_simplify_preserves_lga_count(boundary_file: Path) -> None:
    """Simplification must not drop LGAs (the topology-preserving flag)."""
    full = parse_lga_boundaries(boundary_file, simplify_tolerance=None)
    simplified = parse_lga_boundaries(boundary_file)
    assert len(full) == len(simplified)


# ---------------------------------------------------------------------------
# Cross-dataset join compatibility
# ---------------------------------------------------------------------------


def test_boundaries_match_dffh_lgas(boundary_file: Path) -> None:
    """Boundary LGAs must match DFFH rent LGAs exactly."""
    if not DFFH_RENTS.exists():
        pytest.skip("DFFH rents file not built; run scripts/ingest_dffh_history.py")

    import pandas as pd

    gdf = parse_lga_boundaries(boundary_file)
    dffh = pd.read_parquet(DFFH_RENTS)

    boundary_set = set(gdf["lga"].unique())
    dffh_set = set(dffh["lga"].unique())

    only_b = boundary_set - dffh_set
    only_d = dffh_set - boundary_set
    assert not only_b and not only_d, (
        f"LGA mismatch:\n  In boundaries but not DFFH: {sorted(only_b)}\n"
        f"  In DFFH but not boundaries: {sorted(only_d)}"
    )


def test_boundaries_match_income_lgas(boundary_file: Path) -> None:
    """Boundary LGAs must match income LGAs exactly."""
    if not ABS_INCOME.exists():
        pytest.skip("ABS income file not built; run scripts/ingest_abs_income.py")

    import pandas as pd

    gdf = parse_lga_boundaries(boundary_file)
    income = pd.read_parquet(ABS_INCOME)

    boundary_set = set(gdf["lga"].unique())
    income_set = set(income["lga"].unique())

    only_b = boundary_set - income_set
    only_i = income_set - boundary_set
    assert not only_b and not only_i, (
        f"LGA mismatch:\n  In boundaries but not income: {sorted(only_b)}\n"
        f"  In income but not boundaries: {sorted(only_i)}"
    )
