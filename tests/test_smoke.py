import pytest
from pathlib import Path
from finance_dashboard import app

def test_app_import():
    assert app.app is not None

@pytest.mark.skipif(
    not Path("data/raw_bank_exports").exists(),
    reason="No local bank exports present"
)
def test_sample_data_loads():
    from finance_dashboard.data_loader import load_raw_exports
    raw = load_raw_exports()
    assert not raw.empty