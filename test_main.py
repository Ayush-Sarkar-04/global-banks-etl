import sqlite3
import pandas as pd
import pytest
from etl_pipeline import (
    extract,
    validate_data,
    data_quality_summary,
    transform,
    load_to_db,
    historical_comparison,
    advanced_sql_analysis
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
def test_valid_data():
    validate_data(valid_data())
def test_wrong_record_count():
    df = valid_data().iloc[:9]
    with pytest.raises(ValueError):
        validate_data(df)
def test_duplicate_bank():
    df = valid_data()
    df.loc[1, "Name"] = "Bank A"
    with pytest.raises(ValueError):
        validate_data(df)
def test_empty_bank_name():
    df = valid_data()
    df.loc[0, "Name"] = ""
    with pytest.raises(ValueError):
        validate_data(df)
def test_negative_market_cap():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = -10
    with pytest.raises(ValueError):
        validate_data(df)
def test_missing_column():
    df = valid_data().drop(columns=["Name"])
    with pytest.raises(ValueError):
        validate_data(df)
def test_extractor_finds_correct_table(monkeypatch):
    html = """
    <table class="wikitable">
        <tr><th>Wrong</th></tr>
        <tr><td>Ignore</td></tr>
    </table>
    <table class="wikitable">
        <tr><th>Bank</th><th>Name</th><th>Market Cap</th></tr>
        <tr><td>1</td><td>Bank A</td><td>100</td></tr>
        <tr><td>2</td><td>Bank B</td><td>90</td></tr>
        <tr><td>3</td><td>Bank C</td><td>80</td></tr>
        <tr><td>4</td><td>Bank D</td><td>70</td></tr>
        <tr><td>5</td><td>Bank E</td><td>60</td></tr>
        <tr><td>6</td><td>Bank F</td><td>50</td></tr>
        <tr><td>7</td><td>Bank G</td><td>40</td></tr>
        <tr><td>8</td><td>Bank H</td><td>30</td></tr>
        <tr><td>9</td><td>Bank I</td><td>20</td></tr>
        <tr><td>10</td><td>Bank J</td><td>10</td></tr>
    </table>
    """
    class Response:
        text = html
        def raise_for_status(self):
            pass
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )
    df = extract(
        "http://test",
        ["Name", "MC_USD_Billion"]
    )
    assert len(df) == 10
    assert df.iloc[0]["Name"] == "Bank A"
def test_http_error(monkeypatch):
    def fail(*args, **kwargs):
        import requests
        raise requests.RequestException("Connection failed")
    monkeypatch.setattr("requests.get", fail)
    with pytest.raises(ConnectionError):
        extract(
            "http://test",
            ["Name", "MC_USD_Billion"]
        )
def test_transform_creates_currency_columns(tmp_path):
    df = valid_data()
    path = exchange_file(tmp_path)
    result = transform(df, path)
    assert "MC_GBP_Billion" in result.columns
    assert "MC_EUR_Billion" in result.columns
    assert "MC_INR_Billion" in result.columns
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
def test_same_day_snapshot_is_not_duplicated():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    load_to_db(df.copy(), conn, "Banks")
    result = pd.read_sql(
        "SELECT * FROM Banks",
        conn
    )
    assert len(result) == 10
    conn.close()
def test_historical_comparison_requires_two_snapshots():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df, conn, "Banks")
    result = historical_comparison(
        conn,
        "Banks"
    )
    assert result.empty
    conn.close()
def test_historical_comparison_returns_data():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    df2 = valid_data()
    df2.loc[0, "MC_USD_Billion"] = 110
    df2["Snapshot_Date"] = "2026-09-23"
    df2.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    result = historical_comparison(
        conn,
        "Banks"
    )
    assert len(result) == 10
    conn.close()
def test_historical_comparison_calculates_changes():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    df2 = valid_data()
    df2.loc[0, "MC_USD_Billion"] = 110
    df2["Snapshot_Date"] = "2026-09-23"
    df2.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    result = historical_comparison(
        conn,
        "Banks"
    )
    bank_a = result[
        result["Name"] == "Bank A"
    ].iloc[0]
    assert bank_a["Previous_Rank"] == 1
    assert bank_a["Current_Rank"] == 1
    assert bank_a["Rank_Change"] == 0
    assert bank_a["Previous_MC"] == 100
    assert bank_a["Current_MC"] == 110
    assert bank_a["MC_Change_Percent"] == 10.0
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
# Stage 3 tests
def test_advanced_sql_analysis_rankings():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df, conn, "Banks")
    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )
    assert len(rankings) == 10
    assert rankings.iloc[0]["Name"] == "Bank A"
    assert rankings.iloc[0]["Current_Rank"] == 1
    assert rankings.iloc[-1]["Current_Rank"] == 10
    conn.close()
def test_top_five_market_cap_concentration():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df, conn, "Banks")
    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )
    expected = round(
        sum([100, 90, 80, 70, 60])
        / sum(df["MC_USD_Billion"])
        * 100,
        2
    )
    actual = concentration.iloc[0][
        "Top_5_Market_Cap_Percent"
    ]
    assert actual == expected
    conn.close()
def test_market_cap_gap():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df, conn, "Banks")
    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )
    assert gap.iloc[0]["Market_Cap_Gap"] == 90.0
    conn.close()
# Stage 4 tests
def test_fallback_extraction_succeeds(monkeypatch):
    from etl_pipeline import extract_with_fallback
    calls = []
    def fake_extract(url, table_attribs):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionError("Primary source failed")
        return valid_data()
    monkeypatch.setattr(
        "etl_pipeline.extract",
        fake_extract
    )
    result = extract_with_fallback(
        "primary",
        "fallback",
        ["Name", "MC_USD_Billion"]
    )
    assert len(result) == 10
    assert calls == ["primary", "fallback"]
def test_fallback_extraction_fails(monkeypatch):
    from etl_pipeline import extract_with_fallback

    def fail_extract(url, table_attribs):
        raise ConnectionError(
            f"{url} failed"
        )
    monkeypatch.setattr(
        "etl_pipeline.extract",
        fail_extract
    )
    with pytest.raises(
        RuntimeError,
        match="Both primary and fallback data sources failed"
    ):
        extract_with_fallback(
            "primary",
            "fallback",
            ["Name", "MC_USD_Billion"]
        )
def test_missing_target_table(monkeypatch):
    html = """
    <html>
        <table class="wikitable">
            <tr><th>Unrelated</th></tr>
            <tr><td>Data</td></tr>
        </table>
    </html>
    """
    class Response:
        text = html
        def raise_for_status(self):
            pass
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )
    with pytest.raises(
        ValueError,
        match="Required bank market-cap table not found"
    ):
        extract(
            "http://test",
            ["Name", "MC_USD_Billion"]
        )
def test_zero_market_cap():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = 0
    with pytest.raises(
        ValueError,
        match="Market-cap values must be positive"
    ):
        validate_data(df)
def test_invalid_exchange_rate_currency_value(tmp_path):
    path = tmp_path / "exchange_rate.csv"
    pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0.80, "invalid", 82.95]
    }).to_csv(path, index=False)
    with pytest.raises(
        ValueError,
        match="numeric and non-empty"
    ):
        transform(valid_data(), path)
def test_historical_rank_change():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    df2 = valid_data()
    df2.loc[1, "MC_USD_Billion"] = 110
    df2["Snapshot_Date"] = "2026-09-23"
    df2.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    result = historical_comparison(
        conn,
        "Banks"
    )
    bank_a = result[
        result["Name"] == "Bank A"
    ].iloc[0]
    bank_b = result[
        result["Name"] == "Bank B"
    ].iloc[0]
    assert bank_a["Previous_Rank"] == 1
    assert bank_a["Current_Rank"] == 2
    assert bank_a["Rank_Change"] == -1
    assert bank_b["Previous_Rank"] == 2
    assert bank_b["Current_Rank"] == 1
    assert bank_b["Rank_Change"] == 1
    conn.close()
def test_historical_market_cap_percentage_change():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    df2 = valid_data()
    df2.loc[0, "MC_USD_Billion"] = 120
    df2["Snapshot_Date"] = "2026-09-23"
    df2.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    result = historical_comparison(
        conn,
        "Banks"
    )
    bank_a = result[
        result["Name"] == "Bank A"
    ].iloc[0]
    assert bank_a["Previous_MC"] == 100
    assert bank_a["Current_MC"] == 120
    assert bank_a["MC_Change_Percent"] == 20.0
    conn.close()
def test_sql_analysis_uses_latest_snapshot():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    latest = valid_data()
    latest.loc[9, "MC_USD_Billion"] = 200
    latest["Snapshot_Date"] = "2026-09-23"
    latest.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )
    assert rankings.iloc[0]["Name"] == "Bank J"
    assert rankings.iloc[0]["Current_Rank"] == 1
    assert rankings.iloc[0]["MC_USD_Billion"] == 200
    conn.close()
def test_sql_analysis_does_not_mix_snapshots():
    conn = sqlite3.connect(":memory:")
    df = valid_data()
    load_to_db(df.copy(), conn, "Banks")
    conn.execute(
        """
        UPDATE Banks
        SET Snapshot_Date = '2026-09-22'
        """
    )
    latest = valid_data()
    latest.loc[0, "MC_USD_Billion"] = 200
    latest["Snapshot_Date"] = "2026-09-23"
    latest.to_sql(
        "Banks",
        conn,
        if_exists="append",
        index=False
    )
    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )
    assert len(rankings) == 10
    assert gap.iloc[0]["Market_Cap_Gap"] == 190.0
    conn.close()
def test_data_quality_multiple_missing_values():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = None
    df.loc[1, "MC_USD_Billion"] = None
    summary = data_quality_summary(df)
    assert summary["records"] == 10
    assert summary["missing_values"] == 2