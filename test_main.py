import sqlite3
import pandas as pd
import pytest
from unittest.mock import patch, Mock

from etl_pipeline import (
    extract,
    validate_data,
    transform,
    load_to_db,
    historical_comparison
)


def valid_dataframe():
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


def test_valid_data_passes():
    validate_data(valid_dataframe())


def test_wrong_record_count_fails():
    df = valid_dataframe().head(9)

    with pytest.raises(ValueError, match="Expected 10 banks"):
        validate_data(df)


def test_duplicate_bank_fails():
    df = valid_dataframe()
    df.loc[1, "Name"] = "Bank A"

    with pytest.raises(ValueError, match="Duplicate bank names"):
        validate_data(df)


def test_empty_bank_name_fails():
    df = valid_dataframe()
    df.loc[0, "Name"] = ""

    with pytest.raises(ValueError, match="Bank names cannot be empty"):
        validate_data(df)


def test_negative_market_cap_fails():
    df = valid_dataframe()
    df.loc[0, "MC_USD_Billion"] = -10

    with pytest.raises(ValueError, match="must be positive"):
        validate_data(df)


def test_missing_column_fails():
    df = valid_dataframe().drop(columns=["MC_USD_Billion"])

    with pytest.raises(ValueError, match="Required columns"):
        validate_data(df)


def test_extract_finds_correct_table():
    html = """
    <html>
        <table class="wikitable">
            <tr>
                <th>Country</th>
                <th>Revenue</th>
            </tr>
            <tr>
                <td>USA</td>
                <td>100</td>
            </tr>
            <tr>
                <td>India</td>
                <td>90</td>
            </tr>
        </table>

        <table class="wikitable">
            <tr>
                <th>Bank</th>
                <th>Market Cap</th>
            </tr>
    """

    for i in range(10):
        html += f"""
            <tr>
                <td>{i}</td>
                <td>Bank {chr(65 + i)}</td>
                <td>{100 - i}.0</td>
            </tr>
        """

    html += """
        </table>
    </html>
    """

    response = Mock()
    response.text = html

    with patch("etl_pipeline.requests.get", return_value=response):
        df = extract(
            "https://example.com",
            ["Name", "MC_USD_Billion"]
        )

    assert len(df) == 10
    assert df.iloc[0]["Name"] == "Bank A"
    assert df.iloc[0]["MC_USD_Billion"] == 100.0


def test_http_error_is_raised():
    response = Mock()
    response.raise_for_status.side_effect = Exception("HTTP error")

    with patch("etl_pipeline.requests.get", return_value=response):
        with pytest.raises(Exception, match="HTTP error"):
            extract(
                "https://example.com",
                ["Name", "MC_USD_Billion"]
            )


def test_transform_creates_currency_columns(tmp_path):
    df = valid_dataframe()

    rates = pd.DataFrame({
        "Currency": ["GBP", "EUR", "INR"],
        "Rate": [0.80, 0.93, 82.95]
    })

    rate_file = tmp_path / "exchange_rate.csv"
    rates.to_csv(rate_file, index=False)

    result = transform(df, str(rate_file))

    assert "MC_GBP_Billion" in result.columns
    assert "MC_EUR_Billion" in result.columns
    assert "MC_INR_Billion" in result.columns

    assert result.iloc[0]["MC_GBP_Billion"] == 80.0
    assert result.iloc[0]["MC_EUR_Billion"] == 93.0
    assert result.iloc[0]["MC_INR_Billion"] == 8295.0


def test_snapshot_is_created(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    load_to_db(
        valid_dataframe(),
        conn,
        "Largest_banks"
    )

    result = pd.read_sql(
        "SELECT * FROM Largest_banks",
        conn
    )

    assert len(result) == 10
    assert "Snapshot_Date" in result.columns
    assert result["Snapshot_Date"].nunique() == 1

    conn.close()


def test_same_day_snapshot_is_not_duplicated(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    df = valid_dataframe()

    load_to_db(df, conn, "Largest_banks")
    load_to_db(df, conn, "Largest_banks")

    result = pd.read_sql(
        "SELECT * FROM Largest_banks",
        conn
    )

    assert len(result) == 10

    conn.close()


def test_historical_comparison_requires_two_snapshots(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    df = valid_dataframe()
    df["Snapshot_Date"] = "2026-09-22"

    df.to_sql(
        "Largest_banks",
        conn,
        index=False
    )

    result = historical_comparison(
        conn,
        "Largest_banks"
    )

    assert result.empty

    conn.close()


def test_historical_comparison_returns_two_snapshot_data(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    previous = valid_dataframe()
    previous["Snapshot_Date"] = "2026-09-22"

    current = valid_dataframe()
    current["Snapshot_Date"] = "2026-09-23"

    combined = pd.concat(
        [previous, current],
        ignore_index=True
    )

    combined.to_sql(
        "Largest_banks",
        conn,
        index=False
    )

    result = historical_comparison(
        conn,
        "Largest_banks"
    )

    assert len(result) == 10
    assert "Previous_Rank" in result.columns
    assert "Current_Rank" in result.columns
    assert "Rank_Change" in result.columns
    assert "Previous_MC" in result.columns
    assert "Current_MC" in result.columns
    assert "MC_Change_Percent" in result.columns

    conn.close()


def test_historical_comparison_calculates_changes(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    previous = valid_dataframe()
    previous["Snapshot_Date"] = "2026-09-22"

    current = valid_dataframe()
    current["Snapshot_Date"] = "2026-09-23"

    current.loc[0, "MC_USD_Billion"] = 80
    current.loc[1, "MC_USD_Billion"] = 110

    combined = pd.concat(
        [previous, current],
        ignore_index=True
    )

    combined.to_sql(
        "Largest_banks",
        conn,
        index=False
    )

    result = historical_comparison(
        conn,
        "Largest_banks"
    )

    bank_a = result[result["Name"] == "Bank A"].iloc[0]
    bank_b = result[result["Name"] == "Bank B"].iloc[0]

    assert bank_a["Previous_Rank"] == 1
    assert bank_a["Current_Rank"] == 2
    assert bank_a["Rank_Change"] == -1
    assert bank_a["MC_Change_Percent"] == -20.0

    assert bank_b["Previous_Rank"] == 2
    assert bank_b["Current_Rank"] == 1
    assert bank_b["Rank_Change"] == 1
    assert bank_b["MC_Change_Percent"] == 22.22

    conn.close()