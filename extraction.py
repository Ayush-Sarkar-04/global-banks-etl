# Extraction and source reconciliation for Largest Banks data
import logging
import re

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_URL = "https://en.wikipedia.org/wiki/List_of_largest_banks"
DEFAULT_TABLE_ATTRIBS = ["Name", "MC_USD_Billion"]


BANK_ALIASES = {
    "jpmorgan chase": "JPMorgan Chase",
    "jp morgan chase": "JPMorgan Chase",
    "china construction bank": "China Construction Bank",
    "bank of america": "Bank of America",
    "agricultural bank of china": "Agricultural Bank of China",
    "hsbc": "HSBC",
    "industrial and commercial bank of china": "Industrial and Commercial Bank of China",
    "icbc": "Industrial and Commercial Bank of China",
    "bank of china": "Bank of China",
    "morgan stanley": "Morgan Stanley",
    "royal bank of canada": "Royal Bank of Canada",
    "goldman sachs": "Goldman Sachs",
    "wells fargo": "Wells Fargo",
    "hdfc bank": "HDFC Bank",
    "china merchants bank": "China Merchants Bank",
    "interactive brokers": "Interactive Brokers",
    "unicredit": "UniCredit",
    "mizuho financial": "Mizuho Financial",
    "bnp paribas": "BNP Paribas",
}


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
    if not pd.api.types.is_numeric_dtype(df["MC_USD_Billion"]):
        raise ValueError("Market-cap values must be numeric")
    if not np.isfinite(df["MC_USD_Billion"]).all():
        raise ValueError("Market-cap values must be finite")
    if (df["MC_USD_Billion"] <= 0).any():
        raise ValueError("Market-cap values must be positive")


def extract(url, table_attribs):
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ConnectionError(f"Source request failed: {error}") from error
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
    data = []
    for row in target_table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        try:
            name = cols[1].get_text(" ", strip=True)
            market_cap = float(
                cols[2].get_text(" ", strip=True)
                .replace(",", "")
                .replace("\n", "")
            )
            data.append([name, market_cap])
        except (ValueError, IndexError):
            continue
        if len(data) == 10:
            break
    if len(data) < 10:
        raise ValueError(
            f"Insufficient valid bank records extracted: {len(data)}"
        )
    df = pd.DataFrame(data, columns=table_attribs)
    validate_data(df)
    return df


def extract_with_fallback(url, fallback_url, table_attribs):
    try:
        return extract(url, table_attribs)
    except (ConnectionError, ValueError) as primary_error:
        logger.info(
            f"Primary extraction failed: {primary_error}. "
            "Attempting fallback source"
        )
        try:
            df = extract(fallback_url, table_attribs)
            logger.info("Fallback extraction completed successfully")
            return df
        except (ConnectionError, ValueError) as fallback_error:
            raise RuntimeError(
                "Both primary and fallback data sources failed. "
                f"Primary: {primary_error}. Fallback: {fallback_error}"
            ) from fallback_error


def normalize_bank_name(name):
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for alias in sorted(BANK_ALIASES, key=len, reverse=True):
        if alias in text:
            return BANK_ALIASES[alias]
    return name.strip()


def parse_market_cap(value):
    match = re.search(
        r"\$?\s*([\d,.]+)\s*(T|B|M)\b(?:\s*USD)?",
        str(value).upper()
    )
    if not match:
        raise ValueError(f"Unable to parse market cap: {value}")
    return float(match.group(1).replace(",", "")) * {
        "T": 1000,
        "B": 1,
        "M": 0.001
    }[match.group(2)]


def extract_ranked_source(url, source_name):
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ConnectionError(f"{source_name} request failed: {error}") from error
    records, soup = [], BeautifulSoup(response.text, "lxml")
    for row in soup.find_all("tr"):
        text = row.get_text(" ", strip=True)
        match = re.search(
            r"\$?\s*[\d,.]+\s*(?:T|B|M)\b(?:\s*USD)?",
            text,
            re.I
        )
        if not match:
            continue
        market_cap_start = match.start()
        name_text = text[:market_cap_start].strip()
        name_text = re.sub(r"^\s*\d+[.)]?\s+", "", name_text)
        name = normalize_bank_name(name_text)
        if not name:
            continue
        try:
            records.append([name, parse_market_cap(match.group(0))])
        except ValueError:
            continue
    df = (
        pd.DataFrame(records, columns=["Name", "MC_USD_Billion"])
        .drop_duplicates("Name")
        .head(10)
    )
    if len(df) < 8:
        raise ValueError(
            f"{source_name} returned fewer than 8 recognized banks"
        )
    return df


def reconcile_sources(source_frames, reference_frames=None):
    merged = pd.concat(
        [
            f.set_index("Name")["MC_USD_Billion"].rename(source)
            for source, f in source_frames.items()
        ],
        axis=1
    )
    source_columns = list(source_frames)
    merged["Source_Count"] = merged[source_columns].notna().sum(axis=1)
    merged["Accepted_MC_USD_Billion"] = merged[source_columns].median(axis=1)
    merged["Source_Spread_Percent"] = (
        (merged[source_columns].max(axis=1) - merged[source_columns].min(axis=1))
        / merged["Accepted_MC_USD_Billion"]
        * 100
    )
    # Keep source verification and reconciliation outcome as separate fields.
    # Reconciliation_Status preserves the TWO_SOURCE / SINGLE_SOURCE label,
    # while Spread_Status records whether the available values agree within
    # the 5% reconciliation threshold.
    merged["Reconciliation_Status"] = np.select(
        [
            merged["Source_Count"].eq(3),
            merged["Source_Count"].eq(2),
            merged["Source_Count"].eq(1),
        ],
        [
            "THREE_SOURCE",
            "TWO_SOURCE",
            "SINGLE_SOURCE",
        ],
        default="NO_SOURCE"
    )
    merged["Spread_Status"] = np.where(
        merged["Source_Count"].ge(2),
        np.where(
            merged["Source_Spread_Percent"].le(5),
            "AGREED",
            "REVIEW",
        ),
        "NOT_APPLICABLE",
    )
    if reference_frames:
        reference = pd.concat(
            [
                f.set_index("Name")["MC_USD_Billion"].rename(source)
                for source, f in reference_frames.items()
            ],
            axis=1
        )
        merged = merged.join(reference, how="outer")
        if "Wikipedia" in reference.columns:
            merged["Wikipedia_Difference_Percent"] = (
                (merged["Wikipedia"] - merged["Accepted_MC_USD_Billion"]).abs()
                / merged["Accepted_MC_USD_Billion"]
                * 100
            )
            merged["Reference_Status"] = np.where(
                merged["Wikipedia_Difference_Percent"].le(5),
                "REFERENCE_MATCH",
                "REFERENCE_REVIEW"
            )
        else:
            merged["Reference_Status"] = "REFERENCE_UNAVAILABLE"
    else:
        merged["Wikipedia_Difference_Percent"] = np.nan
        merged["Reference_Status"] = "REFERENCE_UNAVAILABLE"
    merged = merged.dropna(
        subset=["Accepted_MC_USD_Billion"]
    ).sort_values(
        "Accepted_MC_USD_Billion",
        ascending=False
    ).head(10)
    result = merged[["Accepted_MC_USD_Billion"]].reset_index().rename(
        columns={"Accepted_MC_USD_Billion": "MC_USD_Billion"}
    )
    validate_data(result)
    return result, merged.reset_index()


def extract_multi_source(wikipedia_url, companies_url, tradingview_url):
    current_urls = {
        "CompaniesMarketCap": companies_url,
        "TradingView": tradingview_url
    }
    current_frames, reference_frames = {}, {}
    try:
        reference_frames["Wikipedia"] = extract_with_fallback(
            wikipedia_url,
            DEFAULT_FALLBACK_URL,
            DEFAULT_TABLE_ATTRIBS
        )
        logger.info("Wikipedia reference extraction completed successfully")
    except (ConnectionError, ValueError, RuntimeError) as error:
        logger.info(f"Wikipedia reference extraction failed: {error}")
    for source, source_url in current_urls.items():
        try:
            current_frames[source] = extract_ranked_source(
                source_url,
                source
            )
            logger.info(f"{source} extraction completed successfully")
        except (ConnectionError, ValueError) as error:
            logger.info(f"{source} extraction failed: {error}")
    if not current_frames:
        raise RuntimeError("All current market-cap sources failed")
    result, reconciliation = reconcile_sources(
        current_frames,
        reference_frames
    )
    logger.info(
        "Source reconciliation completed using "
        f"{len(current_frames)} current source(s)"
    )
    return result, reconciliation
