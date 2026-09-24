# ETL orchestration, validation, transformation and loading for Largest Banks data
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

from analytics import (
    advanced_sql_analysis,
    historical_comparison,
    historical_trend,
    run_query,
)
from extraction import (
    extract_multi_source,
    log_progress,
    validate_data,
)


# Configuration
url = (
    "https://web.archive.org/web/20230908091635/"
    "https://en.wikipedia.org/wiki/List_of_largest_banks"
)
companies_market_cap_url = (
    "https://companiesmarketcap.com/banks/largest-banks-by-market-cap"
)
tradingview_url = (
    "https://www.tradingview.com/markets/world-stocks/worlds-largest-banks/"
)
table_attribs = ["Name", "MC_USD_Billion"]
output_csv = "./data/Largest_banks_data.csv"
db_name = "Banks.db"
table_name = "Largest_banks"
csv_path = "./data/exchange_rate.csv"


def data_quality_summary(df):
    return {
        "records": len(df),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_names": int(df["Name"].duplicated().sum()),
        "min_market_cap": float(df["MC_USD_Billion"].min()),
        "max_market_cap": float(df["MC_USD_Billion"].max())
    }


def transform(df, csv_path):
    exchange_df = pd.read_csv(csv_path)
    required_columns = {"Currency", "Rate"}
    if not required_columns.issubset(exchange_df.columns):
        raise ValueError(
            "Exchange-rate file must contain Currency and Rate columns"
        )
    required_rates = {"GBP", "EUR", "INR"}
    if not required_rates.issubset(
        set(exchange_df["Currency"].dropna())
    ):
        raise ValueError("Required exchange rates are missing")
    if exchange_df["Currency"].duplicated().any():
        raise ValueError("Duplicate currencies found")
    exchange_df["Rate"] = pd.to_numeric(
        exchange_df["Rate"], errors="coerce"
    )
    if exchange_df["Rate"].isna().any():
        raise ValueError(
            "Exchange rates must be numeric and non-empty"
        )
    if (exchange_df["Rate"] <= 0).any():
        raise ValueError("Exchange rates must be positive")
    exchange_rate = dict(
        zip(exchange_df["Currency"], exchange_df["Rate"])
    )
    gbp_rate, eur_rate, inr_rate = (
        float(exchange_rate[x]) for x in ("GBP", "EUR", "INR")
    )
    df["MC_GBP_Billion"] = [
        np.round(x * gbp_rate, 2)
        for x in df["MC_USD_Billion"]
    ]
    df["MC_EUR_Billion"] = [
        np.round(x * eur_rate, 2)
        for x in df["MC_USD_Billion"]
    ]
    df["MC_INR_Billion"] = [
        np.round(x * inr_rate, 2)
        for x in df["MC_USD_Billion"]
    ]
    return df


def load_to_csv(df, output_path):
    df.to_csv(output_path, index=False)


def load_to_db(df, sql_connection, table_name, snapshot_type="RECONCILED"):
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    df["Snapshot_Date"] = snapshot_date
    df["Snapshot_Type"] = snapshot_type
    table_exists = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' "
        f"AND name='{table_name}'", sql_connection
    )
    if not table_exists.empty:
        columns = pd.read_sql(
            f"PRAGMA table_info({table_name})",
            sql_connection
        )["name"].tolist()
        if "Snapshot_Type" not in columns:
            sql_connection.execute(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN Snapshot_Type TEXT DEFAULT 'LEGACY'"
            )
        sql_connection.execute(
            f"DELETE FROM {table_name} WHERE Snapshot_Date = ?",
            (snapshot_date,)
        )
    df.to_sql(
        table_name,
        sql_connection,
        if_exists="append" if not table_exists.empty else "replace",
        index=False
    )


def run_etl():
    conn = None
    try:
        log_progress("Preliminaries complete. Initiating ETL process")
        df, reconciliation = extract_multi_source(
            url,
            companies_market_cap_url,
            tradingview_url
        )
        print("\nSource Reconciliation:")
        print(reconciliation)
        validate_data(df)
        quality = data_quality_summary(df)
        log_progress(
            f"Data quality: {quality['records']} records, "
            f"{quality['missing_values']} missing values, "
            f"{quality['duplicate_names']} duplicate names, "
            f"market cap range "
            f"{quality['min_market_cap']} - {quality['max_market_cap']}"
        )
        print("\nData Quality Summary:")
        print(quality)
        log_progress("Data extraction and validation complete")
        df = transform(df, csv_path)
        log_progress(
            "Data transformation and exchange-rate validation complete"
        )
        load_to_csv(df, output_csv)
        log_progress("Data saved to CSV file")
        conn = sqlite3.connect(db_name)
        log_progress("SQL Connection initiated")
        load_to_db(df, conn, table_name)
        log_progress("Data loaded to Database as a table")
        run_query(
            """
            SELECT Name, MC_USD_Billion, MC_GBP_Billion
            FROM Largest_banks
            WHERE Snapshot_Date = (
                SELECT MAX(Snapshot_Date)
                FROM Largest_banks
            )
            ORDER BY MC_USD_Billion DESC
            LIMIT 5
            """,
            conn
        )
        run_query(
            """
            SELECT ROUND(AVG(MC_GBP_Billion), 2)
            AS Avg_GBP_Market_Cap
            FROM Largest_banks
            WHERE Snapshot_Date = (
                SELECT MAX(Snapshot_Date)
                FROM Largest_banks
            )
            """,
            conn
        )
        run_query(
            """
            SELECT Name, MC_USD_Billion
            FROM Largest_banks
            WHERE Snapshot_Date = (
                SELECT MAX(Snapshot_Date)
                FROM Largest_banks
            )
            AND MC_USD_Billion > (
                SELECT AVG(MC_USD_Billion)
                FROM Largest_banks
                WHERE Snapshot_Date = (
                    SELECT MAX(Snapshot_Date)
                    FROM Largest_banks
                )
            )
            ORDER BY MC_USD_Billion DESC
            """,
            conn
        )
        trend = historical_trend(conn, table_name)
        if not trend.empty:
            print("\nHistorical Trend:")
            print(trend)

        comparison = historical_comparison(conn, table_name)
        if not comparison.empty:
            print("\nHistorical Comparison:")
            print(comparison)
        rankings, concentration, gap = advanced_sql_analysis(
            conn,
            table_name
        )
        print("\nCurrent Rankings:")
        print(rankings)
        print("\nTop 5 Market-Cap Concentration:")
        print(concentration)
        print("\nMarket-Cap Gap:")
        print(gap)
        log_progress("Process Complete")
    except Exception as error:
        log_progress(f"ETL process failed: {error}")
        print(f"\nETL process failed: {error}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    run_etl()
