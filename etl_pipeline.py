# ETL orchestration, validation, transformation and loading for Largest Banks data
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

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
    validate_data,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(message)s",
    handlers=[
        logging.FileHandler("code_log.txt"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


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


def data_quality_summary(df: pd.DataFrame) -> dict[str, float | int]:
    """Return record counts, missing values, duplicates, and market-cap range"""
    return {
        "records": len(df),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_names": int(df["Name"].duplicated().sum()),
        "min_market_cap": float(df["MC_USD_Billion"].min()),
        "max_market_cap": float(df["MC_USD_Billion"].max())
    }


def transform(df: pd.DataFrame, csv_path: str | Path) -> pd.DataFrame:
    """Add GBP, EUR, and INR market-cap values using validated exchange rates"""
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


def load_to_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    """Write the transformed bank dataset to a CSV file"""
    df.to_csv(output_path, index=False)


def load_to_db(
    df: pd.DataFrame,
    sql_connection: sqlite3.Connection,
    table_name: str,
    snapshot_type: str = "RECONCILED"
) -> None:
    """Append the current bank snapshot to SQLite and preserve snapshot history"""
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


def run_etl() -> None:
    """Run extraction, transformation, loading, and SQL analysis stages"""
    conn = None
    logger.info("Preliminaries complete. Initiating ETL process")

    try:
        df, reconciliation = extract_multi_source(
            url,
            companies_market_cap_url,
            tradingview_url
        )
        logger.info("Source Reconciliation:\n%s", reconciliation)
        validate_data(df)
        quality = data_quality_summary(df)
        logger.info(
            "Data quality: %s records, %s missing values, "
            "%s duplicate names, market cap range %s - %s",
            quality["records"],
            quality["missing_values"],
            quality["duplicate_names"],
            quality["min_market_cap"],
            quality["max_market_cap"],
        )
        logger.info("Data Quality Summary:\n%s", quality)
        logger.info("Data extraction and validation complete")
    except Exception as error:
        logger.error("ETL extraction stage failed: %s", error)
        return

    try:
        df = transform(df, csv_path)
        logger.info(
            "Data transformation and exchange-rate validation complete"
        )
    except Exception as error:
        logger.error("ETL transformation stage failed: %s", error)
        return

    try:
        load_to_csv(df, output_csv)
        logger.info("Data saved to CSV file")
        conn = sqlite3.connect(db_name)
        logger.info("SQL Connection initiated")
        load_to_db(df, conn, table_name)
        logger.info("Data loaded to Database as a table")
    except Exception as error:
        logger.error("ETL load stage failed: %s", error)
        return

    try:
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
            logger.info("Historical Trend:\n%s", trend)

        comparison = historical_comparison(conn, table_name)
        if not comparison.empty:
            logger.info("Historical Comparison:\n%s", comparison)
        rankings, concentration, gap = advanced_sql_analysis(
            conn,
            table_name
        )
        logger.info("Current Rankings:\n%s", rankings)
        logger.info(
            "Top 5 Market-Cap Concentration:\n%s",
            concentration
        )
        logger.info("Market-Cap Gap:\n%s", gap)
        logger.info("Process Complete")
    except Exception as error:
        logger.error("ETL analysis stage failed: %s", error)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    run_etl()
