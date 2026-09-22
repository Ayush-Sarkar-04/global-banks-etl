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
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")
    tables = soup.find_all("table", {"class": "wikitable"})
    target_table = tables[0]   # first wikitable under market cap
    rows = target_table.find_all("tr")
    data = []
    for row in rows[1:11]:  # top 10 banks
        cols = row.find_all("td")
        if len(cols) >= 3:
            name = cols[1].text.strip()
            mc = cols[2].text.strip().replace("\n", "")
            mc = float(mc)
            data.append([name, mc])
    df = pd.DataFrame(data, columns=table_attribs)
    return df
def transform(df, csv_path):
    exchange_df = pd.read_csv(csv_path)
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
    df.to_sql(
        table_name,
        sql_connection,
        if_exists="replace",
        index=False
    )
def run_query(query_statement, sql_connection):
    print(f"\nQuery: {query_statement}")
    result = pd.read_sql(
        query_statement,
        sql_connection
    )
    print(result)
# Configuration
url = "https://web.archive.org/web/20230908091635/https://en.wikipedia.org/wiki/List_of_largest_banks"
table_attribs = [
    "Name",
    "MC_USD_Billion"
]
output_csv = "./data/Largest_banks_data.csv"
db_name = "Banks.db"
table_name = "Largest_banks"
csv_path = "./data/exchange_rate.csv"
# ETL Process
log_progress(
    "Preliminaries complete. Initiating ETL process"
)
# Extract
df = extract(url, table_attribs)
log_progress(
    "Data extraction complete. Initiating Transformation process"
)
# Transform
df = transform(df, csv_path)
log_progress(
    "Data transformation complete. Initiating Loading process"
)
# Load to CSV
load_to_csv(df, output_csv)
log_progress(
    "Data saved to CSV file"
)
# DB Connection
conn = sqlite3.connect(db_name)
log_progress(
    "SQL Connection initiated"
)
# Load to DB
load_to_db(
    df,
    conn,
    table_name
)
log_progress(
    "Data loaded to Database as a table, Executing queries"
)
# Queries
run_query(
    "SELECT * FROM Largest_banks",
    conn
)
run_query(
    "SELECT AVG(MC_GBP_Billion) FROM Largest_banks",
    conn
)
run_query(
    "SELECT Name FROM Largest_banks LIMIT 5",
    conn
)
log_progress(
    "Process Complete"
)
conn.close()
log_progress(
    "Server Connection closed"
)