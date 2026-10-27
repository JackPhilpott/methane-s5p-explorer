"""Tests for the pure logic in explore_xch4. None of these call Earth Engine."""

import numpy as np
import pandas as pd
import pytest

from explore_xch4 import anomaly, build_dataframe, month_starts, plot_anomaly, plot_monthly


def feature(month, xch4=None, obs=None):
    """A feature shaped like Earth Engine's getInfo() output. Null properties are omitted."""
    props = {"month": month}
    if xch4 is not None:
        props["xch4_ppb"] = xch4
    if obs is not None:
        props["obs_per_pixel"] = obs
    return {"type": "Feature", "geometry": None, "id": month, "properties": props}


# --- month_starts -----------------------------------------------------------------------


def test_month_starts_covers_three_years():
    months = month_starts("2023-01-01", "2026-01-01")
    assert len(months) == 36
    assert months[0] == "2023-01-01"
    assert months[-1] == "2025-12-01"


def test_month_starts_rolls_over_the_year():
    assert month_starts("2023-11-01", "2024-03-01") == [
        "2023-11-01",
        "2023-12-01",
        "2024-01-01",
        "2024-02-01",
    ]


def test_month_starts_skips_a_partial_first_month():
    assert month_starts("2023-01-15", "2023-04-01") == ["2023-02-01", "2023-03-01"]


@pytest.mark.parametrize("start, end", [("2023-01-01", "2023-01-01"), ("2024-01-01", "2023-01-01")])
def test_month_starts_is_empty_when_end_is_not_after_start(start, end):
    assert month_starts(start, end) == []


# --- anomaly ----------------------------------------------------------------------------


def test_anomaly_is_relative_to_the_median():
    np.testing.assert_allclose(anomaly([1890, 1900, 1910, 1950]), [-15, -5, 5, 45])


def test_anomaly_ignores_gaps():
    result = anomaly([1900, np.nan, 1910])
    np.testing.assert_allclose(result, [-5, np.nan, 5])


def test_anomaly_works_on_a_2d_grid():
    grid = np.array([[1880.0, 1900.0], [np.nan, 1920.0]])
    expected = np.array([[-20.0, 0.0], [np.nan, 20.0]])
    np.testing.assert_allclose(anomaly(grid), expected)


def test_anomaly_median_is_robust_to_one_extreme_pixel():
    # A single plume-like outlier should not shift the reference value
    values = [1900, 1901, 1899, 1900, 2400]
    assert anomaly(values)[0] == 0


# --- build_dataframe --------------------------------------------------------------------


def test_build_dataframe_sorts_by_month():
    df = build_dataframe(
        [
            feature("2023-03-01", 1925.0, 12),
            feature("2023-01-01", 1920.0, 10),
            feature("2023-02-01", 1922.5, 11),
        ]
    )
    assert list(df.columns) == ["month", "xch4_ppb", "obs_per_pixel"]
    assert df["month"].tolist() == ["2023-01", "2023-02", "2023-03"]
    assert df["xch4_ppb"].tolist() == [1920.0, 1922.5, 1925.0]


def test_build_dataframe_keeps_months_without_data_as_gaps():
    df = build_dataframe(
        [
            feature("2023-01-01", 1920.0, 10),
            feature("2023-02-01", obs=0),  # fully cloudy month: Earth Engine returns no mean
        ]
    )
    assert len(df) == 2
    assert pd.isna(df.loc[1, "xch4_ppb"])
    assert df.loc[1, "obs_per_pixel"] == 0


def test_build_dataframe_rounds_values():
    df = build_dataframe([feature("2023-01-01", 1920.123456, 10.987654)])
    assert df.loc[0, "xch4_ppb"] == 1920.12
    assert df.loc[0, "obs_per_pixel"] == 10.99


# --- plots ------------------------------------------------------------------------------


def test_plot_monthly_writes_a_png(tmp_path):
    df = build_dataframe(
        [
            feature("2023-01-01", 1920.0, 10),
            feature("2023-02-01", obs=0),
            feature("2023-03-01", 1925.0, 12),
        ]
    )
    path = tmp_path / "monthly.png"
    plot_monthly(df, path)
    assert path.read_bytes().startswith(b"\x89PNG")


def test_plot_anomaly_writes_a_png(tmp_path):
    grid = anomaly(np.array([[1900.0, 1910.0], [np.nan, 1930.0]]))
    path = tmp_path / "anomaly.png"
    plot_anomaly(grid, (52.5, 37.5, 55.5, 40.5), path, {"A town": (53.0, 39.0)})
    assert path.read_bytes().startswith(b"\x89PNG")
