import numpy as np
import pandas as pd
import pytest

from extraction import (
    extract,
    extract_multi_source,
    extract_ranked_source,
    extract_with_fallback,
    normalize_bank_name,
    parse_market_cap,
    reconcile_sources,
    validate_data,
)

def valid_data():
    return pd.DataFrame({
        "Name": [
            "Bank A", "Bank B", "Bank C", "Bank D", "Bank E",
            "Bank F", "Bank G", "Bank H", "Bank I", "Bank J"
        ],
        "MC_USD_Billion": [
            100, 90, 80, 70, 60,
            50, 40, 30, 20, 10
        ]
    })
def test_valid_data():
    validate_data(valid_data())

def test_wrong_record_count():
    df = valid_data().iloc[:9]
    with pytest.raises(ValueError):
        validate_data(df)

def test_duplicate_bank():
    df = valid_data()
    df.loc[1, "Name"] = "Bank A"
    with pytest.raises(ValueError):
        validate_data(df)

def test_empty_bank_name():
    df = valid_data()
    df.loc[0, "Name"] = ""
    with pytest.raises(ValueError):
        validate_data(df)

def test_negative_market_cap():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = -10
    with pytest.raises(ValueError):
        validate_data(df)

def test_missing_column():
    df = valid_data().drop(columns=["Name"])
    with pytest.raises(ValueError):
        validate_data(df)

def test_zero_market_cap():
    df = valid_data()
    df.loc[0, "MC_USD_Billion"] = 0
    with pytest.raises(
        ValueError,
        match="Market-cap values must be positive"
    ):
        validate_data(df)

def test_nan_market_cap():
    df = valid_data().astype({"MC_USD_Billion": float})
    df.loc[0, "MC_USD_Billion"] = np.nan
    with pytest.raises(
        ValueError,
        match="Market-cap values cannot be empty"
    ):
        validate_data(df)

def test_positive_infinity_market_cap():
    df = valid_data().astype({"MC_USD_Billion": float})
    df.loc[0, "MC_USD_Billion"] = np.inf
    with pytest.raises(
        ValueError,
        match="Market-cap values must be finite"
    ):
        validate_data(df)

def test_extractor_finds_correct_table(monkeypatch):
    html = """
    <table class="wikitable">
        <tr><th>Wrong</th></tr>
        <tr><td>Ignore</td></tr>
    </table>
    <table class="wikitable">
        <tr><th>Bank</th><th>Name</th><th>Market Cap</th></tr>
        <tr><td>1</td><td>Bank A</td><td>100</td></tr>
        <tr><td>2</td><td>Bank B</td><td>90</td></tr>
        <tr><td>3</td><td>Bank C</td><td>80</td></tr>
        <tr><td>4</td><td>Bank D</td><td>70</td></tr>
        <tr><td>5</td><td>Bank E</td><td>60</td></tr>
        <tr><td>6</td><td>Bank F</td><td>50</td></tr>
        <tr><td>7</td><td>Bank G</td><td>40</td></tr>
        <tr><td>8</td><td>Bank H</td><td>30</td></tr>
        <tr><td>9</td><td>Bank I</td><td>20</td></tr>
        <tr><td>10</td><td>Bank J</td><td>10</td></tr>
    </table>
    """
    class Response:
        text = html
        def raise_for_status(self):
            pass
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )
    df = extract(
        "http://test",
        ["Name", "MC_USD_Billion"]
    )
    assert len(df) == 10
    assert df.iloc[0]["Name"] == "Bank A"

def test_http_error(monkeypatch):
    def fail(*args, **kwargs):
        import requests
        raise requests.RequestException("Connection failed")
    monkeypatch.setattr("requests.get", fail)
    with pytest.raises(ConnectionError):
        extract(
            "http://test",
            ["Name", "MC_USD_Billion"]
        )

def test_fallback_extraction_succeeds(monkeypatch):
    from extraction import extract_with_fallback
    calls = []
    def fake_extract(url, table_attribs):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionError("Primary source failed")
        return valid_data()
    monkeypatch.setattr(
        "extraction.extract",
        fake_extract
    )
    result = extract_with_fallback(
        "primary",
        "fallback",
        ["Name", "MC_USD_Billion"]
    )
    assert len(result) == 10
    assert calls == ["primary", "fallback"]

def test_fallback_extraction_fails(monkeypatch):
    from extraction import extract_with_fallback

    def fail_extract(url, table_attribs):
        raise ConnectionError(
            f"{url} failed"
        )
    monkeypatch.setattr(
        "extraction.extract",
        fail_extract
    )
    with pytest.raises(
        RuntimeError,
        match="Both primary and fallback data sources failed"
    ):
        extract_with_fallback(
            "primary",
            "fallback",
            ["Name", "MC_USD_Billion"]
        )

def test_extractor_rejects_insufficient_records(monkeypatch):
    html = """
    <table class="wikitable">
        <tr><th>Bank</th><th>Name</th><th>Market Cap</th></tr>
        <tr><td>1</td><td>Bank A</td><td>100</td></tr>
        <tr><td>2</td><td>Bank B</td><td>90</td></tr>
    </table>
    """
    class Response:
        text = html
        def raise_for_status(self):
            pass
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="Insufficient valid bank records"):
        extract("http://test", ["Name", "MC_USD_Billion"])

def test_missing_target_table(monkeypatch):
    html = """
    <html>
        <table class="wikitable">
            <tr><th>Unrelated</th></tr>
            <tr><td>Data</td></tr>
        </table>
    </html>
    """
    class Response:
        text = html
        def raise_for_status(self):
            pass
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )
    with pytest.raises(
        ValueError,
        match="Required bank market-cap table not found"
    ):
        extract(
            "http://test",
            ["Name", "MC_USD_Billion"]
        )

def test_normalize_bank_name_alias_and_formatting():
    assert normalize_bank_name("JPMorgan Chase, Inc.") == "JPMorgan Chase"
    assert normalize_bank_name("Industrial and Commercial Bank of China") == (
        "Industrial and Commercial Bank of China"
    )

def test_normalize_bank_name_preserves_unknown_name():
    assert normalize_bank_name("Example Community Bank") == "Example Community Bank"

def test_parse_market_cap_supports_billion_trillion_and_million():
    assert parse_market_cap("123.45 B USD") == 123.45
    assert parse_market_cap("1.5 T USD") == 1500.0
    assert parse_market_cap("250 M USD") == 0.25

def test_parse_market_cap_rejects_invalid_value():
    with pytest.raises(ValueError, match="Unable to parse market cap"):
        parse_market_cap("not-a-market-cap")

def test_extract_ranked_source_normalizes_and_parses_rows(monkeypatch):
    banks = [
        ("JPMorgan Chase", "900 B USD"),
        ("Bank of America", "400 B USD"),
        ("Industrial & Commercial Bank of China", "300 B USD"),
        ("Agricultural Bank of China", "250 B USD"),
        ("HSBC", "200 B USD"),
        ("China Construction Bank", "190 B USD"),
        ("Bank of China", "180 B USD"),
        ("Morgan Stanley", "170 B USD"),
        ("Royal Bank of Canada", "160 B USD"),
        ("Goldman Sachs", "150 B USD"),
    ]

    rows = "".join(
        f"<tr><td>{name}</td><td>{market_cap}</td></tr>"
        for name, market_cap in banks
    )
    html = f"<table>{rows}</table>"

    class Response:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )

    result = extract_ranked_source(
        "http://test",
        "CompaniesMarketCap"
    )

    assert len(result) == 10
    assert result.iloc[0]["Name"] == "JPMorgan Chase"
    assert result.iloc[2]["Name"] == "Industrial and Commercial Bank of China"
    assert result.iloc[0]["MC_USD_Billion"] == 900.0
    assert result.iloc[2]["MC_USD_Billion"] == 300.0

def test_extract_ranked_source_retains_unaliased_bank(monkeypatch):
    banks = [
        ("JPMorgan Chase", "900 B USD"),
        ("Bank of America", "400 B USD"),
        ("Industrial & Commercial Bank of China", "300 B USD"),
        ("Agricultural Bank of China", "250 B USD"),
        ("HSBC", "200 B USD"),
        ("China Construction Bank", "190 B USD"),
        ("Bank of China", "180 B USD"),
        ("Morgan Stanley", "170 B USD"),
        ("Royal Bank of Canada", "160 B USD"),
        ("Example Community Bank", "150 B USD"),
    ]

    rows = "".join(
        f"<tr><td>{name}</td><td>{market_cap}</td></tr>"
        for name, market_cap in banks
    )
    html = f"<table>{rows}</table>"

    class Response:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )

    result = extract_ranked_source(
        "http://test",
        "CompaniesMarketCap"
    )

    assert len(result) == 10
    assert "Example Community Bank" in result["Name"].tolist()


def test_extract_ranked_source_rejects_insufficient_recognized_banks(monkeypatch):
    html = """
    <table>
        <tr><td>JPMorgan Chase</td><td>900 B USD</td></tr>
        <tr><td>Bank of America</td><td>400 B USD</td></tr>
        <tr><td>HSBC</td><td>200 B USD</td></tr>
    </table>
    """

    class Response:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response()
    )

    with pytest.raises(
        ValueError,
        match="returned fewer than 8 recognized banks"
    ):
        extract_ranked_source(
            "http://test",
            "TradingView"
        )

def test_reconcile_sources_uses_median_and_marks_agreed():
    names = valid_data()["Name"]
    source_frames = {
        "Wikipedia": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [100] * 10
        }),
        "CompaniesMarketCap": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [101] * 10
        }),
        "TradingView": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [102] * 10
        })
    }

    result, audit = reconcile_sources(source_frames)

    first = audit.iloc[0]
    assert result.iloc[0]["MC_USD_Billion"] == 101.0
    assert first["Source_Count"] == 3
    assert first["Accepted_MC_USD_Billion"] == 101.0
    assert first["Reconciliation_Status"] == "THREE_SOURCE"
    assert first["Spread_Status"] == "AGREED"

def test_reconcile_sources_marks_large_spread_for_review():
    names = valid_data()["Name"]
    source_frames = {
        "Wikipedia": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [100] * 10
        }),
        "CompaniesMarketCap": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [130] * 10
        }),
        "TradingView": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [110] * 10
        })
    }

    result, audit = reconcile_sources(source_frames)

    first = audit.iloc[0]
    assert result.iloc[0]["MC_USD_Billion"] == 110.0
    assert first["Source_Spread_Percent"] > 5
    assert first["Reconciliation_Status"] == "THREE_SOURCE"
    assert first["Spread_Status"] == "REVIEW"

def test_reconcile_sources_handles_two_available_sources():
    names = valid_data()["Name"]
    source_frames = {
        "CompaniesMarketCap": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [100] * 10
        }),
        "TradingView": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [120] * 10
        })
    }

    result, audit = reconcile_sources(source_frames)

    assert len(result) == 10
    assert audit.iloc[0]["Source_Count"] == 2
    assert audit.iloc[0]["Accepted_MC_USD_Billion"] == 110.0
    assert audit.iloc[0]["Reconciliation_Status"] == "TWO_SOURCE"
    assert audit.iloc[0]["Spread_Status"] == "REVIEW"

def test_reconcile_sources_marks_reference_unavailable():
    names = valid_data()["Name"]
    source_frames = {
        "CompaniesMarketCap": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [100] * 10
        }),
        "TradingView": pd.DataFrame({
            "Name": names,
            "MC_USD_Billion": [102] * 10
        })
    }

    result, audit = reconcile_sources(source_frames)

    assert len(result) == 10
    assert set(audit["Reference_Status"]) == {"REFERENCE_UNAVAILABLE"}
    assert audit["Wikipedia_Difference_Percent"].isna().all()


def test_extract_multi_source_reconciles_all_available_sources(monkeypatch):
    names = valid_data()["Name"]

    wikipedia = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [100] * 10
    })
    companies = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [101] * 10
    })
    tradingview = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [102] * 10
    })

    def fake_fallback(*args, **kwargs):
        return wikipedia

    def fake_ranked_source(url, source_name):
        if source_name == "CompaniesMarketCap":
            return companies
        return tradingview

    monkeypatch.setattr(
        "extraction.extract_with_fallback",
        fake_fallback
    )
    monkeypatch.setattr(
        "extraction.extract_ranked_source",
        fake_ranked_source
    )

    result, audit = extract_multi_source(
        "wikipedia",
        "companies",
        "tradingview"
    )

    assert len(result) == 10
    assert set(audit["Source_Count"]) == {2}
    assert result.iloc[0]["MC_USD_Billion"] == 101.5
    assert audit.iloc[0]["Reference_Status"] == "REFERENCE_MATCH"

def test_extract_multi_source_continues_when_one_source_fails(monkeypatch):
    names = valid_data()["Name"]

    wikipedia = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [100] * 10
    })
    tradingview = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [120] * 10
    })

    def fake_fallback(*args, **kwargs):
        return wikipedia

    def fake_ranked_source(url, source_name):
        if source_name == "CompaniesMarketCap":
            raise ConnectionError("CompaniesMarketCap unavailable")
        return tradingview

    monkeypatch.setattr(
        "extraction.extract_with_fallback",
        fake_fallback
    )
    monkeypatch.setattr(
        "extraction.extract_ranked_source",
        fake_ranked_source
    )

    result, audit = extract_multi_source(
        "wikipedia",
        "companies",
        "tradingview"
    )

    assert len(result) == 10
    assert set(audit["Source_Count"]) == {1}
    assert set(audit["Reconciliation_Status"]) == {"SINGLE_SOURCE"}
    assert result.iloc[0]["MC_USD_Billion"] == 120.0



def test_extract_multi_source_continues_when_wikipedia_reference_fails(monkeypatch):
    names = valid_data()["Name"]
    tradingview = pd.DataFrame({
        "Name": names,
        "MC_USD_Billion": [120] * 10
    })

    def fail_reference(*args, **kwargs):
        raise RuntimeError("Both primary and fallback data sources failed")

    def fake_ranked_source(url, source_name):
        if source_name == "CompaniesMarketCap":
            raise ConnectionError("CompaniesMarketCap unavailable")
        return tradingview

    monkeypatch.setattr("extraction.extract_with_fallback", fail_reference)
    monkeypatch.setattr("extraction.extract_ranked_source", fake_ranked_source)

    result, audit = extract_multi_source(
        "wikipedia",
        "companies",
        "tradingview"
    )

    assert len(result) == 10
    assert set(audit["Source_Count"]) == {1}
    assert set(audit["Reconciliation_Status"]) == {"SINGLE_SOURCE"}
    assert set(audit["Spread_Status"]) == {"NOT_APPLICABLE"}
    assert result.iloc[0]["MC_USD_Billion"] == 120.0
