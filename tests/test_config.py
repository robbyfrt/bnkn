from finance_dashboard.config import CONFIG

def test_config_loads():
    assert CONFIG is not None

def test_required_keys_present():
    assert "paths" in CONFIG
    assert "raw_exports_dir" in CONFIG["paths"]
    assert "ledger_dir" in CONFIG["paths"]
    assert "mapping_file" in CONFIG["paths"]

def test_optional_blocks_absent_is_fine():
    # n8n and scenarios are commented out — their absence must not raise
    assert CONFIG.get("n8n") is None
    assert CONFIG.get("scenarios") is None