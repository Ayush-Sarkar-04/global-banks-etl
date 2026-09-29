# Global Banks ETL — Project Documentation

> Comprehensive technical documentation for the Global Banks Data ETL Pipeline.
>
> This document records the project's architecture, evolution, implementation decisions, validation strategy, source-reconciliation model, historical snapshot design, testing approach, and current state.

---

# 1. Project Overview

Global Banks ETL is a compact Python data-engineering project built around a simple objective:

> Extract the market capitalization of the world's largest banks, validate the data, transform it into multiple currencies, store it historically, and perform analytical SQL queries.

The project deliberately remains a small ETL system rather than becoming a large data platform.

The current implementation has three main Python modules:

```text
extraction.py
etl_pipeline.py
analytics.py
```

The system follows:

```text
                 ┌─────────────────────┐
                 │     Web Sources     │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │       Extract       │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │      Validate       │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Multi-source        │
                 │ Reconciliation      │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │      Transform      │
                 │ USD → GBP/EUR/INR   │
                 └──────────┬──────────┘
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
        ┌───────────┐               ┌───────────┐
        │   CSV     │               │  SQLite   │
        └───────────┘               └─────┬─────┘
                                          ↓
                                  ┌───────────────┐
                                  │ SQL Analytics │
                                  └───────────────┘
                                          ↓
                                  Historical Analysis
```

---

# 2. Project Scope

The project focuses on practical ETL and data-engineering concepts:

- web extraction
- HTML parsing
- validation
- source fallback
- multi-source reconciliation
- data-quality monitoring
- currency transformation
- CSV processing
- SQLite storage
- historical snapshots
- SQL analysis
- automated testing
- CI
- execution logging

The project does **not** attempt to become:

- a production distributed data platform
- a real-time market-data system
- a full data warehouse
- an autonomous financial decision system
- a frontend-heavy analytics application

Keeping the system compact is an intentional design decision.

---

# 3. Current Repository Structure

```text
global-banks-etl/
│
├── .github/
│   └── workflows/
│       └── test.yml
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
├── requirements.txt
├── README.md
├── PROJECT DOCUMENTATION.md
└── .gitignore
```

Generated runtime artifacts include:

```text
Banks.db
code_log.txt
```

---

# 4. Module Architecture

## 4.1 extraction.py

`extraction.py` owns the extraction and source-reconciliation layer.

Responsibilities:

- HTTP requests
- HTML parsing
- source-specific extraction
- table detection
- market-cap parsing
- bank-name normalization
- source fallback
- current-source reconciliation
- Wikipedia reference validation
- extraction-level validation
- extraction logging

Conceptually:

```text
CompaniesMarketCap ─┐
                    ├── normalize ── parse ── reconcile
TradingView ────────┘

Wikipedia ─────────────── reference / validation
```

The module does not own the currency transformation or database loading stages.

---

## 4.2 etl_pipeline.py

`etl_pipeline.py` owns the ETL orchestration and core pipeline stages.

Responsibilities:

- pipeline configuration
- data-quality summary
- exchange-rate loading
- currency transformation
- CSV output
- SQLite loading
- snapshot management
- ETL orchestration
- stage-level error handling
- process logging

Its role is to connect the extraction and analytics layers without moving extraction-specific logic into the orchestration layer.

---

## 4.3 analytics.py

`analytics.py` owns reusable SQL and historical analysis.

Responsibilities include:

- reusable SQL query execution
- current ranking analysis
- top-5 analysis
- average market-cap analysis
- above-average bank analysis
- market-cap concentration
- market-cap gap
- historical trend
- historical comparison
- rank movement

The module is kept separate so analytical SQL does not become mixed into extraction or transformation logic.

---

# 5. Source Architecture

The current implementation uses three sources with different roles.

## 5.1 CompaniesMarketCap

Role:

```text
CURRENT MARKET-CAP SOURCE
```

Used as one of the current values contributing to reconciliation.

---

## 5.2 TradingView

Role:

```text
CURRENT MARKET-CAP SOURCE
```

Used as the second current value contributing to reconciliation.

---

## 5.3 Wikipedia

Role:

```text
REFERENCE / VALIDATION SOURCE
```

Wikipedia is intentionally not treated as a current market-cap source in the same way as CompaniesMarketCap and TradingView.

Its value is used to provide an independent reference check.

This distinction was introduced so that a reference discrepancy does not incorrectly become a failure of the current-market extraction process.

---

# 6. Extraction Strategy

The extraction layer uses:

- `requests`
- `BeautifulSoup`
- HTML inspection
- header-based table identification
- regular-expression parsing where required by the source structure
- request timeouts
- HTTP error handling

The extractor is designed to avoid relying exclusively on a fixed table index.

Instead, it searches for the expected structure and validates the resulting records.

---

# 7. Bank Name Normalization

Different sources may represent the same institution differently.

The project therefore maintains aliases for common bank-name variations.

Examples include:

```text
JPMorgan Chase
JP Morgan Chase
JPMorgan Chase & Co.
```

The normalization layer maps recognized variations to a common name.

The alias system includes common names such as:

- JPMorgan Chase
- China Construction Bank
- Bank of America
- Agricultural Bank of China
- HSBC
- Industrial and Commercial Bank of China
- Bank of China
- Morgan Stanley
- Royal Bank of Canada
- Goldman Sachs
- Wells Fargo
- HDFC Bank
- China Merchants Bank
- Interactive Brokers
- UniCredit
- Mizuho Financial
- BNP Paribas

A key design change was made later in the project:

> Unaliased banks are not automatically discarded.

If the extracted row contains a valid bank name and market-cap value, the bank can be retained even when it is not present in the predefined alias dictionary.

The alias dictionary is therefore a normalization aid rather than an extraction whitelist.

---

# 8. Market-Cap Parsing

Market capitalization can appear in different textual formats.

The parser supports values such as:

```text
$897.21 B
897.22 B USD
1.2 T USD
500 M
```

The parser normalizes values into USD billions.

Conversions include:

```text
1 T = 1000 B
1 B = 1 B
1 M = 0.001 B
```

The resulting canonical field is:

```text
MC_USD_Billion
```

Invalid, missing, zero, negative, or non-numeric market-cap values are rejected by validation.

---

# 9. Extraction Validation

The extraction layer validates the structural integrity of the resulting dataset.

Core checks include:

- required columns exist
- ten banks are extracted
- bank names are not empty
- bank names are unique
- market-cap values are present
- market-cap values are numeric
- market-cap values are positive

The pipeline intentionally fails when extraction produces an insufficient or structurally invalid dataset rather than silently continuing with incomplete records.

---

# 10. Multi-Source Reconciliation

One of the most important architectural changes was moving from a single-source model to a multi-source model.

The current design separates:

```text
CURRENT SOURCE RECONCILIATION
```

from:

```text
REFERENCE VALIDATION
```

For each bank, current-source values are collected from the available current sources.

The accepted market capitalization is:

```text
median(available current-source values)
```

---

# 11. Source Count

Each bank records:

```text
Source_Count
```

This represents the number of current sources that contributed a market-cap value.

Possible states include:

```text
0
1
2
```

and the architecture also supports the reconciliation status representation used by the current output.

---

# 12. Reconciliation Status

The output records:

```text
Reconciliation_Status
```

The current model distinguishes:

```text
THREE_SOURCE
TWO_SOURCE
SINGLE_SOURCE
NO_SOURCE
```

The three-source state is retained for extensibility of the reconciliation model even though the current-market source set contains two current sources and Wikipedia is treated separately as a reference source.

---

# 13. Spread Status

A second field was introduced because source count alone does not tell us whether the sources agree.

For the available current-source values:

```text
spread = (max - min) / median × 100
```

The current threshold is:

```text
5%
```

Interpretation:

```text
≤ 5%  → AGREED
> 5%  → REVIEW
```

This distinction was important because an earlier implementation could label a bank as `TWO_SOURCE` without communicating whether those two sources materially disagreed.

The final design separates:

```text
Reconciliation_Status
```

from:

```text
Spread_Status
```

A source disagreement therefore becomes visible without automatically stopping the entire pipeline.

---

# 14. Handling Source Failure

The pipeline is intentionally resilient to partial current-source failure.

If:

```text
CompaniesMarketCap + TradingView
```

both work:

```text
two-source reconciliation
```

If one current source fails:

```text
single-source continuation
```

If both current sources fail:

```text
extraction failure
```

This creates a deliberate distinction between:

```text
partial degradation
```

and:

```text
complete inability to obtain current market data
```

---

# 15. Wikipedia Reference Validation

Wikipedia is handled independently from the current-source reconciliation.

The output includes:

```text
Wikipedia_Difference_Percent
Reference_Status
```

Reference status values include:

```text
REFERENCE_MATCH
REFERENCE_REVIEW
REFERENCE_UNAVAILABLE
```

A Wikipedia failure does not stop the pipeline.

This was a deliberate architectural decision after observing that an unavailable reference source should not invalidate otherwise usable current-source data.

---

# 16. Data Quality Layer

Before transformation, the pipeline creates a data-quality summary.

Current summary information includes:

- record count
- missing values
- duplicate bank names
- minimum market capitalization
- maximum market capitalization

The purpose is not to replace validation.

Instead:

```text
Validation
    ↓
"Is the data acceptable?"

Data Quality Summary
    ↓
"What does the accepted dataset look like?"
```

---

# 17. Currency Transformation

The source market-cap value is represented in USD billions.

The transformation layer reads exchange rates from:

```text
data/exchange_rate.csv
```

The output contains:

```text
MC_USD_Billion
MC_GBP_Billion
MC_EUR_Billion
MC_INR_Billion
```

NumPy is used for numerical rounding.

Exchange-rate validation checks:

- required exchange-rate column
- required currencies
- numeric values
- positive values
- duplicate currencies
- missing values

---

# 18. CSV Output

The latest transformed dataset is written to:

```text
data/Largest_banks_data.csv
```

This file represents the latest processed output.

It is separate from the historical SQLite layer.

---

# 19. SQLite Architecture

The main database is:

```text
Banks.db
```

The database stores bank records and historical snapshots.

The principal table is:

```text
Largest_banks
```

The database allows multiple dated snapshots to coexist.

---

# 20. Snapshot Model

Each stored dataset is associated with:

```text
Snapshot_Date
```

Current snapshots are marked:

```text
Snapshot_Type = RECONCILED
```

Legacy records from the earlier schema can be represented as:

```text
Snapshot_Type = LEGACY
```

The system retains up to five distinct snapshots.

This creates a compact rolling historical window rather than an unlimited database.

---

# 21. Same-Day Snapshot Protection

Repeated executions on the same day do not create duplicate historical snapshots.

The current same-day snapshot is replaced with the latest run.

Conceptually:

```text
Run 1 — 2026-09-29
Run 2 — 2026-09-29
Run 3 — 2026-09-29

Database:
2026-09-29 → latest snapshot only
```

This prevents multiple executions of the pipeline from artificially appearing as separate market observations.

---

# 22. Legacy Schema Migration

The database loader contains a migration path for older tables that predate:

```text
Snapshot_Type
```

When an existing table does not contain this column, the loader adds it with:

```text
LEGACY
```

This allows older database records to remain usable while new snapshots use the current schema.

This migration path is now explicitly tested.

---

# 23. Historical Analytics

The historical layer supports analysis across the retained snapshots.

## Historical trend

`historical_trend()` provides time-series information for selected banks and metrics.

It supports the current snapshot window and handles the case where no snapshots are available.

## Historical comparison

`historical_comparison()` compares the two most recent snapshots.

The comparison includes:

- previous rank
- current rank
- rank change
- previous market capitalization
- current market capitalization
- market-cap percentage change

---

# 24. SQL Analytics

The analytics module provides reusable SQL analysis for the latest data.

Current analysis includes:

- current ranking by USD market capitalization
- top five banks
- average GBP market capitalization
- banks above the current average
- top-five concentration
- market-cap gap
- historical trend
- historical comparison
- rank movement

The market-cap gap represents the difference between the largest and smallest tracked banks.

Top-five concentration measures the share of the total market capitalization represented by the five largest tracked banks.

---

# 25. Reusable Query Execution

The project includes a reusable query runner.

The query runner:

1. receives SQL
2. executes it against SQLite
3. prints the result
4. returns the resulting DataFrame

Returning the DataFrame was added so that the function is useful both interactively and inside automated tests.

---

# 26. ETL Orchestration

The main orchestration function is:

```text
run_etl()
```

The execution sequence is conceptually:

```text
1. Extract
2. Validate
3. Data-quality summary
4. Transform
5. Load CSV
6. Load SQLite
7. Historical analysis
8. SQL analysis
9. Log completion
```

Stage-specific exception handling was added so failures can be identified by pipeline stage rather than being presented as one generic pipeline failure.

---

# 27. Error Handling Philosophy

The project uses two different philosophies depending on the failure.

## Recoverable source failure

Example:

```text
Wikipedia unavailable
```

The pipeline can continue because Wikipedia is a reference source.

## Partial current-source failure

Example:

```text
CompaniesMarketCap unavailable
TradingView available
```

The pipeline can continue using the remaining current source.

## Complete current-source failure

Example:

```text
CompaniesMarketCap unavailable
TradingView unavailable
```

The pipeline fails because there is no current market-cap source left.

## Structural data failure

Example:

```text
required column missing
duplicate bank names
invalid market-cap values
```

The pipeline stops rather than producing silently corrupted output.

---

# 28. Logging Evolution

The project originally used a custom helper:

```python
log_progress(message)
```

The helper wrote timestamped messages directly into:

```text
code_log.txt
```

The codebase also contained direct `print()` usage.

This created two output mechanisms:

```text
log_progress() → file
print()         → terminal
```

The logging architecture was subsequently migrated toward Python's standard:

```python
logging
```

The intent is:

```text
application code
      ↓
Python logging
      ↓
terminal / file handlers
```

This gives the application standard log levels such as:

```text
INFO
WARNING
ERROR
```

and separates log generation from the physical destination.

---

# 29. Testing Architecture

The project uses:

```text
pytest
```

Tests are divided according to module responsibility.

```text
test_extraction.py
test_etl_pipeline.py
test_analytics.py
```

The test suite covers:

- validation
- extraction
- parsing
- fallback behavior
- source reconciliation
- reference-source failure
- exchange-rate validation
- transformation
- CSV loading
- SQLite loading
- snapshots
- same-day protection
- legacy migration
- historical analysis
- SQL analysis
- ETL stage failures
- ETL success path

The current verified local suite contains:

```text
65 passing tests
```

---

# 30. Extraction Test Coverage

Extraction tests include cases for:

- wrong record counts
- duplicate banks
- empty bank names
- negative market caps
- missing columns
- zero market caps
- NaN market caps
- positive infinity
- HTTP errors
- fallback extraction
- fallback failure
- insufficient recognized banks
- missing target tables
- bank-name aliases
- unknown bank names
- market-cap parsing
- ranked-source extraction
- unaliased-bank retention
- source reconciliation
- large source spread
- two-source handling
- unavailable reference source
- multi-source success
- one-source failure
- Wikipedia reference failure

---

# 31. ETL Test Coverage

Pipeline tests include:

- currency transformation
- CSV creation
- snapshot creation
- data-quality summaries
- exchange-rate validation
- SQLite loading
- same-day snapshot replacement
- snapshot retention
- historical behavior
- stage-specific ETL failures

The successful ETL path is also tested with mocked pipeline stages.

The success-path test verifies that:

- the process completes
- the expected data reaches SQLite
- the snapshot is marked `RECONCILED`
- the completion message is logged

---

# 32. Analytics Test Coverage

Analytics tests cover:

- reusable SQL query execution
- current ranking
- historical comparison
- historical trend
- advanced SQL analysis
- concentration analysis
- market-cap gap
- empty historical state
- latest-snapshot isolation
- legacy database migration

The historical trend function was explicitly added to the test suite after being identified as an uncovered analytics path.

---

# 33. CI

The repository contains:

```text
.github/workflows/test.yml
```

The CI workflow:

1. checks out the repository
2. sets up Python 3.10
3. installs dependencies
4. runs the pytest suite

The project therefore validates the automated test suite on pushes to the main branch and pull requests.

---

# 34. Iteration History

The project evolved through several deliberate iterations.

## Iteration 1 — Basic ETL

The original concept was a small ETL pipeline:

```text
Extract
  ↓
Transform
  ↓
Load
```

The original implementation focused on extracting the top banks, converting market caps, saving CSV output, loading SQLite, and performing SQL queries.

The goal was deliberately small.

---

## Iteration 2 — Validation and robustness

The next iteration strengthened the extraction layer.

Changes included:

- fixed validation rules
- HTTP error handling
- table detection
- malformed-row handling
- market-cap parsing
- bank-name normalization
- fallback behavior
- extraction tests

This changed the project from a simple scraper into a more defensible ETL pipeline.

---

## Iteration 3 — Historical snapshots

Historical storage was then introduced.

The database gained:

```text
Snapshot_Date
```

The system was changed from:

```text
latest dataset only
```

to:

```text
latest dataset + historical snapshots
```

A five-snapshot rolling window was selected to keep the project compact.

Same-day protection was also introduced.

---

## Iteration 4 — Historical analytics

With snapshots available, the project gained:

- historical comparison
- rank movement
- market-cap change
- historical trend analysis

This created an analytical layer rather than using SQLite only as a storage destination.

---

## Iteration 5 — Multi-source extraction

The project was then expanded to use multiple web sources.

Current-source extraction became:

```text
CompaniesMarketCap
TradingView
```

and Wikipedia became:

```text
reference / validation
```

This was a significant design change.

The project no longer depended entirely on one current-market source.

---

## Iteration 6 — Reconciliation model

The multi-source architecture required an explicit reconciliation strategy.

The project introduced:

```text
Source_Count
Reconciliation_Status
Spread_Status
```

and median-based reconciliation.

A 5% spread threshold was introduced to distinguish:

```text
AGREED
```

from:

```text
REVIEW
```

Importantly, `REVIEW` does not automatically stop the pipeline.

---

## Iteration 7 — Reference-source separation

Wikipedia initially had the potential to behave like another source in the pipeline.

The architecture was refined so that Wikipedia became a reference source.

This introduced:

```text
Wikipedia_Difference_Percent
Reference_Status
```

and allowed Wikipedia failure to be non-fatal.

---

## Iteration 8 — Source-failure resilience

The extraction layer was then changed so that one source failing would not necessarily terminate the run.

The behavior became:

```text
2 current sources available
    → reconcile

1 current source available
    → continue with single source

0 current sources available
    → fail
```

This made source availability explicit in the output.

---

## Iteration 9 — Legacy compatibility

As the snapshot model evolved, older database schemas needed to remain usable.

The loader gained migration behavior for tables without:

```text
Snapshot_Type
```

Old records become:

```text
LEGACY
```

while new snapshots become:

```text
RECONCILED
```

This avoided requiring users to manually recreate their database.

---

## Iteration 10 — Testing expansion

The project progressively expanded its test suite.

Testing moved beyond isolated utility functions into:

- source failures
- reconciliation behavior
- historical behavior
- snapshot management
- database migration
- ETL stage failures
- complete ETL success path

The current local verification is:

```text
65 passed
```

---

## Iteration 11 — CI

GitHub Actions was added so the test suite runs automatically.

This changed the project from:

```text
locally tested
```

to:

```text
locally tested + CI verified
```

---

## Iteration 12 — Code quality and logging

The project then received:

- type hints
- docstrings
- stage-specific ETL error handling
- standard logging migration

These changes were intended to improve maintainability without changing the core ETL architecture.

---

# 35. Important Design Decisions

## Decision 1 — Keep the project compact

The project intentionally uses a small number of modules.

The goal is to demonstrate sound data-engineering design without introducing unnecessary framework layers.

---

## Decision 2 — Use median reconciliation

The median was selected as a simple robust statistic for combining current-source values.

It avoids allowing one unusually high or low source value to directly determine the reconciled value.

---

## Decision 3 — Separate source count from source agreement

A bank can have two sources without those sources agreeing closely.

Therefore:

```text
Reconciliation_Status
```

and:

```text
Spread_Status
```

remain separate.

---

## Decision 4 — Do not fail because Wikipedia is unavailable

Wikipedia is a reference source, not a required current-market source.

Therefore its failure is represented explicitly rather than treated as a pipeline failure.

---

## Decision 5 — Do not discard every unknown bank

The alias dictionary is not a whitelist.

An unknown bank name can still be retained when its row is structurally valid.

This reduces unnecessary data loss when a source introduces a new naming variation.

---

## Decision 6 — Keep historical storage bounded

The project retains five distinct snapshots.

This provides enough history for trend and comparison analysis without turning a compact portfolio project into an unlimited historical warehouse.

---

## Decision 7 — Replace same-day snapshots

Multiple executions on the same date should represent the latest state rather than create artificial observations.

Therefore same-day data is replaced.

---

## Decision 8 — Preserve legacy database records

Schema evolution should not require destroying the existing database.

The migration path therefore adds the missing snapshot-type field and labels old records as `LEGACY`.

---

## Decision 9 — Treat review states as visible, not fatal

A source spread above 5% is a data-quality signal.

It is not automatically a reason to discard the record.

The system retains the median value and exposes the disagreement through status fields.

---

# 36. Current Data Model

The principal bank dataset contains fields including:

| Field | Purpose |
|---|---|
| `Name` | Bank name |
| `MC_USD_Billion` | Reconciled/current market cap in USD billions |
| `MC_GBP_Billion` | GBP conversion |
| `MC_EUR_Billion` | EUR conversion |
| `MC_INR_Billion` | INR conversion |
| `Source_Count` | Number of current sources contributing |
| `Reconciliation_Status` | Current-source availability state |
| `Spread_Status` | Current-source agreement state |
| `Wikipedia_Difference_Percent` | Reference-source difference |
| `Reference_Status` | Wikipedia reference state |
| `Snapshot_Date` | Snapshot date |
| `Snapshot_Type` | `RECONCILED` or `LEGACY` |

---

# 37. Operational Flow

A normal successful run can be summarized as:

```text
START
  ↓
Extract Wikipedia reference
  ↓
Extract CompaniesMarketCap
  ↓
Extract TradingView
  ↓
Normalize bank names
  ↓
Parse market caps
  ↓
Reconcile current sources
  ↓
Validate output
  ↓
Generate data-quality summary
  ↓
Load exchange rates
  ↓
Transform currencies
  ↓
Write CSV
  ↓
Open SQLite
  ↓
Migrate legacy schema if required
  ↓
Store current snapshot
  ↓
Maintain five-snapshot window
  ↓
Run SQL analysis
  ↓
Run historical analysis
  ↓
Log completion
  ↓
END
```

Failure behavior branches according to the stage and whether the failure is recoverable.

---

# 38. Known Engineering Limitations

The current implementation is intentionally practical rather than production-grade.

Known limitations include:

## Web-source drift

The extraction layer depends on the current structure of external websites.

Changes in HTML structure, table markup, access restrictions, or source behavior can require extractor updates.

Multi-source extraction reduces the impact of a single source failure but does not eliminate source-drift risk.

## Reference-source access

Wikipedia access may fail because of HTTP restrictions or external service behavior.

The pipeline handles this as a non-fatal reference failure.

## Exchange-rate dependency

`data/exchange_rate.csv` is a required input to the transformation stage.

The file must be present for a fresh execution.

## SQL table-name interpolation

Some SQL statements construct table names using f-strings.

The current table name is a trusted internal constant rather than user-supplied input.

This is an area that can be hardened further if the project ever accepts dynamic table names.

## Python version

The current project and CI target Python 3.10.

---

# 39. Current Status

At the latest project checkpoint:

```text
Core ETL                COMPLETE
Multi-source extraction COMPLETE
Reconciliation         COMPLETE
Historical snapshots   COMPLETE
Historical analytics   COMPLETE
Automated tests        COMPLETE
CI                     COMPLETE
Logging migration      COMPLETE
Documentation          CURRENT
```

Latest local test result:

```text
65 passed
```

The project is therefore beyond the initial ETL implementation and now functions as a compact, tested, multi-source historical ETL and analytics system.

---

# 40. Remaining Hardening Backlog

The remaining items are intentionally separated from the completed core architecture.

## High priority

### Exchange-rate dependency

Continue treating:

```text
data/exchange_rate.csv
```

as an explicit project input and ensure fresh clones contain the required file.

### SQL safety hardening

Consider validating trusted table names through a whitelist before interpolating them into SQL.

---

## Medium priority

### Exception specificity

Some pipeline stages still use broad exception handling.

Future hardening can narrow these to expected exception types while allowing unexpected programming errors to surface.

### Web scraping resilience

Potential future improvements include:

- more explicit source-structure checks
- clearer source-specific failures
- source access policy review
- stronger detection of markup drift

---

## Low priority

### Logging formatting

Some logger calls can be standardized to lazy `%s` formatting instead of f-strings.

### CI static analysis

Potential additions:

```text
flake8
bandit
```

These are quality/security enhancements rather than core ETL requirements.

---

# 41. Technology Stack

| Technology | Role |
|---|---|
| Python 3.10 | Application language |
| Pandas | Data manipulation |
| NumPy | Numerical operations |
| Requests | HTTP extraction |
| BeautifulSoup | HTML parsing |
| SQLite | Persistent storage |
| SQL | Analytics |
| Pytest | Testing |
| GitHub Actions | CI |

---

# 42. Running the Project

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the ETL:

```bash
python etl_pipeline.py
```

Run tests:

```bash
python -m pytest -q
```

---

# 43. Outputs

Latest CSV:

```text
data/Largest_banks_data.csv
```

SQLite database:

```text
Banks.db
```

Execution log:

```text
code_log.txt
```

The database provides the historical layer, while the CSV provides the latest processed dataset.

---

# 44. Project Philosophy

The project evolved without changing its central idea:

```text
Keep the pipeline small.
Make the data trustworthy.
Make failures visible.
Keep historical context.
Test the important paths.
```

The architecture was expanded only when a new requirement exposed a real weakness:

```text
single source
    ↓
multi-source extraction
    ↓
reconciliation
    ↓
reference validation
    ↓
historical storage
    ↓
historical analytics
    ↓
broader automated testing
    ↓
CI and maintainability improvements
```

The result is still a compact ETL project, but it now demonstrates a substantially more complete data-engineering workflow than the original implementation.

---

# 45. Documentation Boundary

This document intentionally contains the detailed engineering history.

The root `README.md` is intentionally short and serves as the project's landing page.

Use:

```text
README.md
```

for:

- project overview
- current capabilities
- architecture at a glance
- setup
- execution
- testing
- output locations

Use:

```text
PROJECT DOCUMENTATION.md
```

for:

- architecture
- source design
- reconciliation
- database model
- historical model
- testing strategy
- iterations
- design decisions
- limitations
- hardening backlog
- implementation history
