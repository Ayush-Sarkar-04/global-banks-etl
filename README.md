# Global Banks Data ETL Pipeline

A compact Python ETL pipeline that extracts market-cap data for the world's largest banks, validates and reconciles multiple sources, converts currencies, stores historical snapshots, and performs SQL analysis.

## What it does

```text
Web Sources
    ↓
Extract → Validate → Reconcile
    ↓
Transform USD → GBP / EUR / INR
    ↓
CSV + SQLite
    ↓
SQL Analysis + Historical Comparison
```

### Current sources

- **CompaniesMarketCap** — current market-cap source
- **TradingView** — current market-cap source
- **Wikipedia** — reference/validation source

Current-source values are reconciled using the **median** of available values. Source count, reconciliation status, spread status, and Wikipedia reference status are retained for auditability.

## Key capabilities

- Top-10 bank extraction from web sources
- HTML table detection and parsing with `Requests` + `BeautifulSoup`
- Source fallback and partial-source failure handling
- Bank-name normalization and market-cap parsing
- Multi-source reconciliation with a 5% spread review threshold
- Data-quality validation and summary
- USD → GBP / EUR / INR transformation
- CSV output
- SQLite storage with historical snapshots
- Up to five distinct snapshots retained
- Same-day snapshot replacement
- Historical rank and market-cap comparison
- SQL ranking, concentration, gap, and trend analysis
- Execution logging
- Automated testing and CI

## Project structure

```text
global-banks-etl/
├── .github/workflows/test.yml
├── data/
│   ├── exchange_rate.csv
│   └── Largest_banks_data.csv
├── etl_pipeline.py
├── extraction.py
├── analytics.py
├── test/
│   ├── test_etl_pipeline.py
│   ├── test_extraction.py
│   └── test_analytics.py
├── pytest.ini
├── requirements.txt
├── README.md
└── PROJECT DOCUMENTATION.md
```

## Modules

- `extraction.py` — web extraction, validation, normalization, parsing, fallback, and reconciliation
- `etl_pipeline.py` — orchestration, data quality, transformation, CSV loading, and SQLite loading
- `analytics.py` — SQL analysis, historical comparison, trend analysis, and reusable queries

## Run

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python etl_pipeline.py
```

Run tests:

```bash
python -m pytest -q
```

**Current test suite: 65 tests passing.**

## Outputs

- `data/Largest_banks_data.csv` — latest processed dataset
- `Banks.db` — SQLite database containing snapshots and analysis data
- `code_log.txt` — execution log

## Documentation

For the full technical history, architecture, iterations, source-reconciliation design, database model, testing strategy, and design decisions, see **[PROJECT DOCUMENTATION.md](PROJECT%20DOCUMENTATION.md)**.
