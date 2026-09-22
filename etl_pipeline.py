# Code for ETL operations on Largest Banks data
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
def log_progress(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("code_log.txt", "a") as f:
        f.write(f"{timestamp} : {message}\n")
def extract(url, table_attribs):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    tables = soup.find_all("table", {"class": "wikitable"})
    target_table = None
    for table in tables:
        headers = [
            cell.get_text(" ", strip=True).lower()
            for cell in table.find_all("th")
        ]
        header_text = " ".join(headers)
        if "market cap" in header_text and "bank" in header_text:
            target_table = table
            break
    if target_table is None:
        raise ValueError("Required bank market-cap table not found")
    rows = target_table.find_all("tr")
    data = []
    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        try:
            name = cols[1].get_text(" ", strip=True)
            market_cap = cols[2].get_text(" ", strip=True)
            market_cap = float(
                market_cap.replace(",", "").replace("\n", "")
            )
            data.append([name, market_cap])
        except (ValueError, IndexError):
            continue
        if len(data) == 10:
            break
    df = pd.DataFrame(data, columns=table_attribs)
    validate_data(df)
    return df
def validate_data(df):
    required_columns = ["Name", "MC_USD_Billion"]
    if not all(column in df.columns for column in required_columns):
        raise ValueError("Required columns are missing")
    if len(df) != 10:
        raise ValueError(f"Expected 10 banks, found {len(df)}")
    if df["Name"].isna().any() or (df["Name"].str.strip() == "").any():
        raise ValueError("Bank names cannot be empty")
    if df["Name"].duplicated().any():
        raise ValueError("Duplicate bank names found")
    if df["MC_USD_Billion"].isna().any():
        raise ValueError("Market-cap values cannot be empty")
    if (df["MC_USD_Billion"] <= 0).any():
        raise ValueError("Market-cap values must be positive")
    if not pd.api.types.is_numeric_dtype(df["MC_USD_Billion"]):
        raise ValueError("Market-cap values must be numeric")
def transform(df, csv_path):
    exchange_df = pd.read_csv(csv_path)
    required_rates = {"GBP", "EUR", "INR"}
    if not required_rates.issubset(exchange_df["Currency"]):
        raise ValueError("Required exchange rates are missing")
    exchange_rate = dict(
        zip(exchange_df["Currency"], exchange_df["Rate"])
    )
    gbp_rate = float(exchange_rate["GBP"])
    eur_rate = float(exchange_rate["EUR"])
    inr_rate = float(exchange_rate["INR"])
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
def load_to_db(df, sql_connection, table_name):
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    df["Snapshot_Date"] = snapshot_date
    table_exists = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' "
        f"AND name='{table_name}'",
        sql_connection
    )
    if not table_exists.empty:
        sql_connection.execute(
            f"DELETE FROM {table_name} "
            "WHERE Snapshot_Date = ?",
            (snapshot_date,)
        )
    df.to_sql(
        table_name,
        sql_connection,
        if_exists="append" if not table_exists.empty else "replace",
        index=False
    )
def run_query(query_statement, sql_connection):
    print(f"\nQuery: {query_statement}")
    result = pd.read_sql(query_statement, sql_connection)
    print(result)
def historical_comparison(sql_connection, table_name):
    dates = pd.read_sql(
        f"""
        SELECT DISTINCT Snapshot_Date
        FROM {table_name}
        ORDER BY Snapshot_Date DESC
        LIMIT 2
        """,
        sql_connection
    )
    if len(dates) < 2:
        print("\nHistorical comparison requires at least two snapshots.")
        return pd.DataFrame()
    latest = dates.iloc[0]["Snapshot_Date"]
    previous = dates.iloc[1]["Snapshot_Date"]
    query = f"""
        WITH ranked AS (
            SELECT
                Snapshot_Date,
                Name,
                MC_USD_Billion,
                RANK() OVER (
                    PARTITION BY Snapshot_Date
                    ORDER BY MC_USD_Billion DESC
                ) AS Rank
            FROM {table_name}
            WHERE Snapshot_Date IN (?, ?)
        )
        SELECT
            previous.Name,
            previous.Rank AS Previous_Rank,
            current.Rank AS Current_Rank,
            previous.Rank - current.Rank AS Rank_Change,
            previous.MC_USD_Billion AS Previous_MC,
            current.MC_USD_Billion AS Current_MC,
            ROUND(
                (current.MC_USD_Billion - previous.MC_USD_Billion)
                * 100.0 / previous.MC_USD_Billion,
                2
            ) AS MC_Change_Percent
        FROM ranked previous
        JOIN ranked current
            ON previous.Name = current.Name
        WHERE previous.Snapshot_Date = ?
          AND current.Snapshot_Date = ?
        ORDER BY current.Rank
    """
    return pd.read_sql(
        query,
        sql_connection,
        params=[latest, previous, previous, latest]
    )
# Configuration
url = (
    "https://web.archive.org/web/20230908091635/"
    "https://en.wikipedia.org/wiki/List_of_largest_banks"
)
table_attribs = ["Name", "MC_USD_Billion"]
output_csv = "./data/Largest_banks_data.csv"
db_name = "Banks.db"
table_name = "Largest_banks"
csv_path = "./data/exchange_rate.csv"
# ETL Process
try:
    log_progress(
        "Preliminaries complete. Initiating ETL process"
    )
    df = extract(url, table_attribs)
    log_progress(
        "Data extraction and validation complete"
    )
    df = transform(df, csv_path)
    log_progress(
        "Data transformation complete. Initiating Loading process"
    )
    load_to_csv(df, output_csv)
    log_progress("Data saved to CSV file")
    conn = sqlite3.connect(db_name)
    log_progress("SQL Connection initiated")
    load_to_db(df, conn, table_name)
    log_progress(
        "Data loaded to Database as a table"
    )
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
    comparison = historical_comparison(
        conn,
        table_name
    )
    if not comparison.empty:
        print("\nHistorical Comparison:")
        print(comparison)
    conn.close()
    log_progress("Process Complete")
except Exception as error:
    log_progress(
        f"ETL process failed: {error}"
    )
    print(
        f"\nETL process failed: {error}"
    )