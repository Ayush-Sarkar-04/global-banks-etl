# Historical and SQL analytics for Largest Banks data
import pandas as pd


def run_query(query_statement, sql_connection):
    print(f"\nQuery: {query_statement}")
    result = pd.read_sql(query_statement, sql_connection)
    print(result)
    return result


def historical_trend(sql_connection, table_name):
    dates = pd.read_sql(
        f"""
        SELECT DISTINCT Snapshot_Date
        FROM {table_name}
        ORDER BY Snapshot_Date DESC
        LIMIT 5
        """,
        sql_connection
    )
    if dates.empty:
        return pd.DataFrame()

    trend_dates = dates["Snapshot_Date"].tolist()
    placeholders = ", ".join("?" for _ in trend_dates)

    query = f"""
        SELECT Snapshot_Date, Name, MC_USD_Billion,
        RANK() OVER (
            PARTITION BY Snapshot_Date
            ORDER BY MC_USD_Billion DESC
        ) AS Rank
        FROM {table_name}
        WHERE Snapshot_Date IN ({placeholders})
        ORDER BY Snapshot_Date, Rank
    """
    return pd.read_sql(
        query,
        sql_connection,
        params=trend_dates
    )


def historical_comparison(sql_connection, table_name):
    dates = pd.read_sql(
        f"""
        SELECT DISTINCT Snapshot_Date
        FROM {table_name}
        ORDER BY Snapshot_Date DESC
        LIMIT 5
        """,
        sql_connection
    )
    if len(dates) < 2:
        print("\nHistorical comparison requires at least two snapshots.")
        return pd.DataFrame()
    latest = dates.iloc[0]["Snapshot_Date"]
    previous = dates.iloc[-1]["Snapshot_Date"]
    query = f"""
        WITH ranked AS (
            SELECT Snapshot_Date, Name, MC_USD_Billion,
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
                * 100.0 / previous.MC_USD_Billion, 2
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


def advanced_sql_analysis(sql_connection, table_name):
    latest = f"(SELECT MAX(Snapshot_Date) FROM {table_name})"
    rankings = pd.read_sql(
        f"""SELECT Name, MC_USD_Billion,
        RANK() OVER (ORDER BY MC_USD_Billion DESC) AS Current_Rank
        FROM {table_name}
        WHERE Snapshot_Date = {latest}
        ORDER BY Current_Rank""",
        sql_connection
    )
    concentration = pd.read_sql(
        f"""SELECT ROUND(
        100.0 * SUM(
            CASE WHEN Current_Rank <= 5
            THEN MC_USD_Billion ELSE 0 END
        ) / SUM(MC_USD_Billion), 2)
        AS Top_5_Market_Cap_Percent
        FROM (
            SELECT MC_USD_Billion,
            RANK() OVER (
                ORDER BY MC_USD_Billion DESC
            ) AS Current_Rank
            FROM {table_name}
            WHERE Snapshot_Date = {latest}
        )""",
        sql_connection
    )
    gap = pd.read_sql(
        f"""SELECT ROUND(
        MAX(MC_USD_Billion) - MIN(MC_USD_Billion), 2)
        AS Market_Cap_Gap
        FROM {table_name}
        WHERE Snapshot_Date = {latest}""",
        sql_connection
    )
    return rankings, concentration, gap
