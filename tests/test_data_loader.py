import pytest, io, tempfile
import pandas as pd
from pathlib import Path
from finance_dashboard.data_loader import (
    load_raw_csv, merge_new_transactions, sort_transactions, COLS
)

def test_load_raw_csv_new_schema(tmp_path, raw_csv_text):
    csv_file = tmp_path / "export.csv"
    csv_file.write_text(raw_csv_text, encoding="utf-8")
    df = load_raw_csv(csv_file)
    assert len(df) == 2
    assert df[COLS["amount"]].iloc[0] == -42.50
    assert str(df[COLS["value_date"]].iloc[0].date()) == "2025-01-15"

def test_merge_deduplicates(minimal_transactions):
    duplicate = minimal_transactions.copy()
    merged = merge_new_transactions(minimal_transactions, duplicate)
    assert len(merged) == len(minimal_transactions)  # no duplicates added

def test_merge_adds_new_rows(minimal_transactions):
    extra = minimal_transactions.iloc[:1].copy()
    extra[COLS["date"]] = pd.to_datetime(["2025-03-01"])
    extra[COLS["value_date"]] = pd.to_datetime(["2025-03-01"])
    extra[COLS["amount"]] = [-100.00]
    merged = merge_new_transactions(minimal_transactions, extra)
    assert len(merged) == len(minimal_transactions) + 1

def test_sort_transactions_descending(minimal_transactions):
    sorted_df = sort_transactions(minimal_transactions)
    dates = sorted_df[COLS["value_date"]].tolist()
    assert dates == sorted(dates, reverse=True)