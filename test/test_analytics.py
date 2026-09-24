import sqlite3
import pandas as pd
import pytest

from analytics import (
    advanced_sql_analysis,
    historical_comparison,
    historical_trend,
    run_query,
)
from etl_pipeline import load_to_db

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
def add_snapshot(connection, dataframe, date):
    snapshot = dataframe.copy()
    snapshot["Snapshot_Date"] = date
    snapshot["Snapshot_Type"] = "RECONCILED"
    snapshot.to_sql("Banks", connection, if_exists="append", index=False)
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

def test_historical_comparison_calculates_changes():
    conn = sqlite3.connect(":memory:")

    first = valid_data()
    add_snapshot(conn, first, "2026-09-22")

    second = valid_data()
    second.loc[0, "MC_USD_Billion"] = 110
    add_snapshot(conn, second, "2026-09-23")

    result = historical_comparison(conn, "Banks")

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

def test_historical_rank_change():
    conn = sqlite3.connect(":memory:")

    first = valid_data()
    add_snapshot(conn, first, "2026-09-22")

    second = valid_data()
    second.loc[1, "MC_USD_Billion"] = 110
    add_snapshot(conn, second, "2026-09-23")

    result = historical_comparison(conn, "Banks")

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

def test_sql_analysis_does_not_mix_snapshots():
    conn = sqlite3.connect(":memory:")

    first = valid_data()
    add_snapshot(conn, first, "2026-09-22")

    latest = valid_data()
    latest.loc[0, "MC_USD_Billion"] = 200
    add_snapshot(conn, latest, "2026-09-23")

    rankings, concentration, gap = advanced_sql_analysis(
        conn,
        "Banks"
    )

    assert len(rankings) == 10
    assert rankings.iloc[0]["Name"] == "Bank A"
    assert rankings.iloc[0]["MC_USD_Billion"] == 200
    assert rankings.iloc[0]["Current_Rank"] == 1
    assert gap.iloc[0]["Market_Cap_Gap"] == 190.0

    conn.close()

def test_sql_analysis_latest_snapshot_values():
    connection = sqlite3.connect(":memory:")

    first = valid_data()
    add_snapshot(connection, first, "2026-09-22")

    latest = valid_data()
    latest.loc[0, "MC_USD_Billion"] = 500
    add_snapshot(connection, latest, "2026-09-23")

    rankings, _, _ = advanced_sql_analysis(
        connection,
        "Banks"
    )

    assert rankings.iloc[0]["Name"] == "Bank A"
    assert rankings.iloc[0]["MC_USD_Billion"] == 500
    assert rankings.iloc[0]["Current_Rank"] == 1

    connection.close()

