# Global Banks Data ETL Pipeline

A Python-based ETL pipeline for extracting market capitalization data for the world's largest banks, validating and transforming the data, storing historical snapshots, and performing SQL-based analysis.

## Overview

The project implements an end-to-end **Extract → Transform → Load** workflow.

The pipeline collects the top 10 banks from a web-based source, validates the extracted records, converts market capitalization values from USD into GBP, EUR, and INR, and stores the processed data in both CSV and SQLite.

The SQLite database also maintains dated snapshots, allowing the pipeline to track changes in bank rankings and market capitalization across different runs.

The project focuses on building a compact and reliable ETL workflow while demonstrating practical data engineering concepts such as web extraction, validation, transformation, database loading, historical data storage, SQL analysis, logging, and automated testing.

## Pipeline

```text
Web Data
   ↓
Extract
   ↓
Validate
   ↓
Transform
USD → GBP / EUR / INR
   ↓
Load
 ↙     ↘
CSV    SQLite
         ↓
    SQL Analysis
         ↓
Historical Comparison
```

## Features

### Web Data Extraction

The pipeline extracts the top 10 banks from the source using:

- `Requests` for HTTP requests
- `BeautifulSoup` for HTML parsing
- Header-based table identification instead of relying on a fixed table position
- Request timeouts and HTTP error handling
- Safe handling of malformed rows

### Data Validation

Extracted data is validated before transformation.

Validation checks include:

- Required columns are present
- Exactly 10 banks are extracted
- Bank names are not empty
- Duplicate bank names are rejected
- Market capitalization values are not empty
- Market capitalization values are numeric
- Market capitalization values are positive
- Required exchange rates are available

Invalid data causes the pipeline to stop rather than silently producing an incorrect dataset.

### Currency Transformation

Market capitalization values are provided in USD and converted into:

- GBP
- EUR
- INR

Exchange rates are read from `data/exchange_rate.csv`.

NumPy is used for numerical rounding during the transformation.

### Data Storage

The processed data is stored in two formats.

**CSV**

The latest processed dataset is saved to:

```text
data/Largest_banks_data.csv
```

**SQLite**

The complete dataset is stored in:

```text
Banks.db
```

SQLite provides the historical layer of the pipeline by retaining snapshots from different dates.

### Historical Snapshots

Each database load is associated with a `Snapshot_Date`.

The database therefore allows multiple snapshots to coexist:

```text
Snapshot_Date | Bank              | Market Cap
------------------------------------------------
2026-09-22    | JPMorgan Chase    | 432.92
2026-09-22    | Bank of America   | 231.52
...
2026-09-23    | JPMorgan Chase    | 432.92
2026-09-23    | Bank of America   | 231.52
...
```

If the pipeline is executed multiple times on the same day, the existing snapshot for that date is replaced instead of creating duplicate records.

### Historical Comparison

When at least two snapshots are available, the pipeline compares the two most recent snapshots.

The comparison includes:

- Previous rank
- Current rank
- Rank change
- Previous market capitalization
- Current market capitalization
- Market-cap percentage change

This allows changes in the relative position and market capitalization of each bank to be tracked over time.

### SQL Analysis

The pipeline performs SQL analysis on the latest snapshot, including:

- Top 5 banks by USD market capitalization
- Average GBP market capitalization
- Banks with market capitalization above the current average
- Historical ranking and market-cap comparison

## Dataset

The processed dataset contains the following fields:

| Column | Description |
|---|---|
| `Name` | Bank name |
| `MC_USD_Billion` | Market capitalization in USD billions |
| `MC_GBP_Billion` | Market capitalization in GBP billions |
| `MC_EUR_Billion` | Market capitalization in EUR billions |
| `MC_INR_Billion` | Market capitalization in INR billions |
| `Snapshot_Date` | Date on which the snapshot was stored |

## Project Structure

```text
global-banks-etl/
│
├── data/
│   ├── exchange_rate.csv
│   └── Largest_banks_data.csv
│
├── etl_pipeline.py
├── test_main.py
├── README.md
├── requirements.txt
├── .gitignore
│
├── Banks.db
└── code_log.txt
```

`Banks.db` and `code_log.txt` are generated during execution and are excluded from version control.

## Technologies

- **Python 3.10+**
- **Pandas** — data manipulation and analysis
- **NumPy** — numerical transformation and rounding
- **BeautifulSoup** — HTML parsing
- **Requests** — HTTP requests
- **SQLite** — database storage and historical snapshots
- **SQL** — analytical queries
- **Pytest** — automated testing

## Running the Project

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate the virtual environment

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the ETL pipeline

```bash
python etl_pipeline.py
```

The pipeline will:

1. Extract the bank data
2. Validate the records
3. Transform market capitalization values
4. Save the latest dataset to CSV
5. Store the snapshot in SQLite
6. Execute SQL analysis
7. Compare the latest two snapshots when historical data is available
8. Log the process

## Running Tests

The project uses `pytest` for automated testing.

Run:

```bash
pytest -q
```

The test suite covers:

- Data validation
- Table identification
- HTTP error handling
- Currency transformation
- Database loading
- Snapshot creation
- Same-day snapshot protection
- Historical comparison
- Rank-change calculations
- Market-cap change calculations

## Logging

The pipeline records execution progress and errors in:

```text
code_log.txt
```

Log entries include timestamps and messages for major stages of the ETL process.

## Key Data Engineering Concepts

This project demonstrates:

- Web data extraction
- HTML table parsing
- Data validation
- Data transformation
- Currency conversion
- CSV processing
- SQLite database operations
- Historical snapshot storage
- SQL analytical queries
- Ranking analysis
- Change tracking
- Error handling
- Process logging
- Automated testing
- End-to-end ETL design
