import pytest
import pandas as pd
from finance_dashboard.categorizer import (
    categorize_dataframe, categorize_unknowns, load_mapping, get_categorization_stats
)
from finance_dashboard.data_loader import COLS

def test_keyword_match_assigns_type(minimal_transactions, minimal_mapping):
    result = categorize_dataframe(minimal_transactions.copy(), minimal_mapping)
    aldi_row = result[result[COLS["recipient"]] == "ALDI SUED"].iloc[0]
    assert aldi_row[COLS["type"]] == "Food"
    assert aldi_row[COLS["subtype"]] == "supermarket"

def test_unmatched_stays_unknown(minimal_transactions, minimal_mapping):
    df = minimal_transactions.copy()
    df.loc[0, COLS["recipient"]] = "Unbekannte GmbH"
    result = categorize_dataframe(df, minimal_mapping)
    assert result.loc[0, COLS["type"]] == "unknown"

def test_categorize_unknowns_skips_known(minimal_transactions, minimal_mapping):
    df = minimal_transactions.copy()
    df.loc[0, COLS["type"]] = "Food"  # pre-categorized
    result = categorize_unknowns(df, minimal_mapping)
    assert result.loc[0, COLS["type"]] == "Food"  # not overwritten

def test_load_mapping_rejects_missing_columns(tmp_path):
    bad = tmp_path / "bad_mapping.csv"
    bad.write_text("row,keyword\nZahlungsempfänger*in,ALDI\n")
    with pytest.raises(ValueError, match="spending_type"):
        load_mapping(bad)

def test_coverage_stats(minimal_transactions, minimal_mapping):
    df = categorize_dataframe(minimal_transactions.copy(), minimal_mapping)
    stats = get_categorization_stats(df)
    assert stats["total_transactions"] == 3
    assert stats["coverage_pct"] == 100.0