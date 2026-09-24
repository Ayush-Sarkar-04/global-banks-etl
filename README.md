# Global Banks Data ETL Pipeline

A Python-based ETL pipeline for extracting market capitalization data for the world's largest banks, validating and transforming the data, reconciling multiple current sources, storing historical snapshots, and performing SQL-based analysis.

## Overview

The project implements an end-to-end **Extract → Transform → Load** workflow.

The pipeline collects the top 10 banks from multiple web-based sources, validates and reconciles the extracted records, converts market capitalization values from USD into GBP, EUR, and INR, and stores the processed data in both CSV and SQLite.

CompaniesMarketCap and TradingView are used as current market-cap sources, while Wikipedia is used as a reference and validation source. Current-source values are reconciled using the median, with source count and spread information retained for auditability.

The SQLite database also maintains dated snapshots, allowing the pipeline to track changes in bank rankings and market capitalization across different runs.

The project focuses on building a compact and reliable ETL workflow while demonstrating practical data engineering concepts such as multi-source web extraction, validation, source reconciliation, data-quality monitoring, transformation, database loading, historical data storage, SQL analysis, logging, and automated testing.

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

The pipeline extracts the top 10 banks from current and reference sources using:

- `Requests` for HTTP requests
- `BeautifulSoup` for HTML parsing
- Header-based table identification instead of relying on a fixed table position
- Request timeouts and HTTP error handling
- Primary and fallback source handling when extraction fails
- Safe handling of malformed rows
- Bank-name normalization across sources
- Market-cap parsing for values expressed in billions, millions, or trillions
- Retention of recognized banks even when their names are not present in the predefined alias list

Current market-cap sources:

- CompaniesMarketCap
- TradingView

Reference source:

- Wikipedia — used for validation rather than as the current market-cap source

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
- Required exchange-rate columns are present
- Required currencies (GBP, EUR, INR) are available
- Exchange rates are numeric
- Exchange rates are positive
- Duplicate currencies are rejected

Invalid data causes the pipeline to stop rather than silently producing an incorrect dataset.

### Multi-Source Reconciliation

Current market-cap values are reconciled across the available current sources.

For each bank, the pipeline records:

- `Source_Count` — number of current sources contributing a market-cap value
- `Reconciliation_Status` — whether one, two, or three source values were available
- `Spread_Status` — whether the difference between the highest and lowest current-source values is within the 5% agreement threshold
- Reconciled market capitalization — calculated using the median of the available current-source values

A spread above 5% is marked for review but does not automatically stop the pipeline. If one current source is unavailable, the pipeline continues with the remaining source. If all current sources fail, extraction fails.

Wikipedia is handled separately as a reference check:

- `Wikipedia_Difference_Percent` records the difference from the reconciled current value
- `Reference_Status` records `REFERENCE_MATCH`, `REFERENCE_REVIEW`, or `REFERENCE_UNAVAILABLE`

Reference-source failure is therefore non-fatal and is explicitly represented in the output rather than being silently ignored.

### Data Quality Monitoring

The pipeline generates a data-quality summary before transformation.

The summary includes:

- Total record count
- Missing-value count
- Duplicate bank-name count
- Minimum market capitalization
- Maximum market capitalization

These checks provide visibility into the quality of the extracted dataset before further processing.

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

The pipeline retains up to five distinct snapshots, providing a compact historical window for trend and comparison analysis.

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

- Current ranking of banks by USD market capitalization
- Top 5 banks by USD market capitalization
- Average GBP market capitalization
- Banks with market capitalization above the current average
- Top 5 market-cap concentration
- Market-cap gap between the largest and smallest banks
- Historical ranking and market-cap comparison

## Dataset

The SQLite snapshot dataset contains the following fields:

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
├── extraction.py
├── analytics.py
│
├── test/
│   ├── test_etl_pipeline.py
│   ├── test_extraction.py
│   └── test_analytics.py
│
├── pytest.ini
├── README.md
├── requirements.txt
└── .gitignore
```

`Banks.db` and `code_log.txt` are generated during execution and excluded from version control.

## Technologies

- **Python 3.10+**
- **Pandas** — data manipulation and analysis
- **NumPy** — numerical transformation and rounding
- **BeautifulSoup** — HTML parsing
- **Requests** — HTTP requests
- **SQLite** — database storage and historical snapshots
- **SQL** — analytical queries
- **Pytest** — automated testing

The implementation is separated into three focused modules:

- `extraction.py` — web extraction, source fallback, bank-name normalization, market-cap parsing, validation, and source reconciliation
- `etl_pipeline.py` — ETL orchestration, data-quality monitoring, transformation, CSV loading, and SQLite loading
- `analytics.py` — SQL analysis, historical comparison, ranking analysis, concentration analysis, and reusable query execution

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
3. Generate a data-quality summary
4. Transform market capitalization values
5. Save the latest dataset to CSV
6. Store the snapshot in SQLite
7. Execute SQL analysis
8. Compare the latest two snapshots when historical data is available
9. Log the process
10. Maintain the historical snapshot window

## Running Tests

The project uses `pytest` for automated testing.

Run:

```bash
pytest -q
```

The test suite currently contains **53 automated tests**, covering:

- Data validation
- Table identification
- HTTP error handling
- Fallback extraction
- Multi-source extraction
- Bank-name normalization
- Market-cap parsing
- Source reconciliation
- Reference-source failure handling
- Currency transformation
- Exchange-rate validation
- Database loading
- Snapshot creation
- Same-day snapshot protection
- Historical comparison
- Rank-change calculations
- Market-cap change calculations
- Data-quality monitoring
- SQL analysis
- Latest-snapshot isolation
- Reusable SQL query execution
- ETL reliability and edge cases

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
- Data-quality monitoring
- Data transformation
- Currency conversion
- CSV processing
- SQLite database operations
- Historical snapshot storage
- SQL analytical queries
- Ranking analysis
- Change tracking
- Error handling
- Fallback source handling
- Multi-source reconciliation
- Reference-source validation
- Process logging
- Automated testing
- End-to-end ETL design
