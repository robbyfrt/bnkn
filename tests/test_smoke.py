import pytest
from pathlib import Path
from finance_dashboard import app
from finance_dashboard.data_loader import load_raw_exports, load_working_ledger


def test_sample_data_loads():
    # Ensure sample raw exports can be loaded and the app imports successfully.
    raw_data = load_raw_exports()
    assert not raw_data.empty

    ledger = load_working_ledger(latest_only=True)
    assert ledger is not None
    assert not ledger.empty


def test_app_import():
    assert app.app is not None
