import logging
import sqlite3
import numpy as np
import pandas as pd
import pytest

import etl_pipeline

from etl_pipeline import (
    data_quality_summary,
    load_to_csv,
    load_to_db,
    transform,
)

def valid_data():
    return pd.DataFrame({
        "Name": [
            "Bank A", "Bank B", "Bank C", "Bank D", "Bank E",
            "Bank F", "Bank G", "Bank H", "Bank I", "Bank J"
        ],
        "MC_USD_Billion": [
            100, 90, 80, 70, 60,
            50, 40, 30, 20, 10
        ]
    })
def exchange_file(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0.80, 0.93, 82.95]
    }).to_csv(path, index=False)
    return path
def test_transform_calculates_currency_values(tmp_path):
    result = transform(valid_data(), exchange_file(tmp_path))
    assert result.loc[0, ["MC_GBP_Billion", "MC_EUR_Billion", "MC_INR_Billion"]].tolist() == [80.0, 93.0, 8295.0]

def test_load_to_csv_creates_expected_output(tmp_path):
    path = tmp_path / "banks.csv"
    load_to_csv(valid_data(), path)
    result = pd.read_csv(path)
    assert len(result) == 10
    assert list(result.columns) == ["Name", "MC_USD_Billion"]

def test_snapshot_is_created():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(
        df,
        conn,
        "Banks"
    )
    result = pd.read_sql(
        "SELECT * FROM Banks",
        conn
    )
    assert len(result) == 10
    assert "Snapshot_Date" in result.columns
    conn.close()

def test_data_quality_summary():
    df = valid_data()
    summary = data_quality_summary(df)
    assert summary["records"] == 10
    assert summary["missing_values"] == 0
    assert summary["duplicate_names"] == 0
    assert summary["min_market_cap"] == 10
    assert summary["max_market_cap"] == 100

def test_data_quality_summary_detects_missing_values():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = None
    summary = data_quality_summary(df)
    assert summary["missing_values"] == 1

def test_data_quality_summary_detects_duplicates():
    df = valid_data()
    df.loc[1, "Name"] = "Bank A"
    summary = data_quality_summary(df)
    assert summary["duplicate_names"] == 1

def test_missing_exchange_rate_column(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"]
    }).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Currency and Rate"):
        transform(valid_data(), path)

def test_missing_required_exchange_rate(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR"],
        "Rate": [0.80, 0.93]
    }).to_csv(path, index=False)
    with pytest.raises(
        ValueError,
        match="Required exchange rates are missing"
    ):
        transform(valid_data(), path)

def test_non_numeric_exchange_rate(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0.80, "abc", 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(
        ValueError,
        match="numeric and non-empty"
    ):
        transform(valid_data(), path)

def test_negative_exchange_rate(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0.80, -0.93, 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(
        ValueError,
        match="Exchange rates must be positive"
    ):
        transform(valid_data(), path)

def test_duplicate_exchange_currency(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "GBP", "EUR", "INR"],
        "Rate": [0.80, 0.81, 0.93, 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(
        ValueError,
        match="Duplicate currencies"
    ):
        transform(valid_data(), path)

def test_zero_exchange_rate(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0, 0.93, 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(ValueError, match="positive"):
        transform(valid_data(), str(path))

def test_nan_exchange_rate(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [np.nan, 0.93, 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(ValueError):
        transform(valid_data(), str(path))

def test_empty_exchange_rate_file(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame(columns=["Currency", "Rate"]).to_csv(
        path,
        index=False
    )
    with pytest.raises(ValueError):
        transform(valid_data(), str(path))

def test_same_day_snapshot_preserves_latest_data():
    connection = sqlite3.connect(":memory:")
    first = valid_data()
    load_to_db(first, connection, "Banks")
    second = valid_data()
    second.loc[0, "MC_USD_Billion"] = 999
    load_to_db(second, connection, "Banks")
    result = pd.read_sql(
        """
        SELECT *
        FROM Banks
        WHERE Name = 'Bank A'
        """,
        connection
    )
    assert len(result) == 1
    assert result.iloc[0]["MC_USD_Billion"] == 999



def test_run_etl_reports_extraction_stage_failure(monkeypatch, caplog):
    def fail_extraction(*args, **kwargs):
        raise ConnectionError("source unavailable")

    monkeypatch.setattr(
        etl_pipeline,
        "extract_multi_source",
        fail_extraction
    )

    with caplog.at_level(logging.ERROR):
        etl_pipeline.run_etl()

    assert any(
        "ETL extraction stage failed" in record.message
        for record in caplog.records
    )


def test_run_etl_reports_transformation_stage_failure(monkeypatch, caplog):
    monkeypatch.setattr(
        etl_pipeline,
        "extract_multi_source",
        lambda *args, **kwargs: (valid_data(), pd.DataFrame())
    )
    monkeypatch.setattr(
        etl_pipeline,
        "transform",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("invalid exchange rates")
        )
    )

    with caplog.at_level(logging.ERROR):
        etl_pipeline.run_etl()

    assert any(
        "ETL transformation stage failed" in record.message
        for record in caplog.records
    )


def test_run_etl_reports_load_stage_failure(monkeypatch, caplog):
    monkeypatch.setattr(
        etl_pipeline,
        "extract_multi_source",
        lambda *args, **kwargs: (valid_data(), pd.DataFrame())
    )
    monkeypatch.setattr(etl_pipeline, "transform", lambda df, path: df)
    monkeypatch.setattr(
        etl_pipeline,
        "load_to_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("output file unavailable")
        )
    )

    with caplog.at_level(logging.ERROR):
        etl_pipeline.run_etl()

    assert any(
        "ETL load stage failed" in record.message
        for record in caplog.records
    )


def test_run_etl_reports_analysis_stage_failure(
    monkeypatch, tmp_path, caplog
):
    monkeypatch.setattr(
        etl_pipeline,
        "extract_multi_source",
        lambda *args, **kwargs: (valid_data(), pd.DataFrame())
    )
    monkeypatch.setattr(etl_pipeline, "transform", lambda df, path: df)
    monkeypatch.setattr(
        etl_pipeline,
        "load_to_csv",
        lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        etl_pipeline,
        "load_to_db",
        lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        etl_pipeline,
        "run_query",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("analysis query failed")
        )
    )
    monkeypatch.setattr(
        etl_pipeline,
        "db_name",
        str(tmp_path / "Banks.db")
    )

    with caplog.at_level(logging.ERROR):
        etl_pipeline.run_etl()

    assert any(
        "ETL analysis stage failed" in record.message
        for record in caplog.records
    )
