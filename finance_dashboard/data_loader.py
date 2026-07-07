"""
Data loading module for personal finance dashboard.
Handles multiple CSV export schema versions from German banks.
"""
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime


# Canonical column names used throughout the app (raw bank export schema)
COLS = {
    "date": "Buchungsdatum",
    "value_date": "Wertstellung",
    "amount": "Betrag (€)",
    "recipient": "Zahlungsempfänger*in",
    "purpose": "Verwendungszweck",
    "account": "Kontonummer",
    "payer": "Zahlungspflichtige*r",
    "blz": "BLZ",
    "type": "spending_type",
    "subtype": "subtype",
}

# Columns to display in the transaction table
DISPLAY_COLUMNS = [
    COLS["date"], COLS["type"], COLS["subtype"], COLS["amount"],
    COLS["recipient"], COLS["purpose"],
]

# Base paths (relative to project root)
RAW_EXPORTS_DIR = Path("data/raw_bank_exports")
LEDGER_DIR = Path("data/working_ledger")
LEDGER_BASENAME = "ledger"

MERGE_ID_COLUMNS = [
    COLS["date"],
    COLS["amount"],
    COLS["recipient"],
    COLS["purpose"],
]

RAW_TO_CANONICAL = {
    # no-op mapping: raw schema is canonical now
}

RAW_OUTPUT_COLUMN_ORDER = [
    "Buchungsdatum",
    "Wertstellung",
    "Status",
    "Zahlungspflichtige*r",
    "Zahlungsempfänger*in",
    "Verwendungszweck",
    "Umsatztyp",
    "IBAN",
    "Betrag (€)",
    "Gläubiger-ID",
    "Mandatsreferenz",
    "Kundenreferenz",
    "spending_type",
    "subtype",
    "confidence",
    "matched_keyword",
]

CANONICAL_TO_RAW = {v: k for k, v in RAW_TO_CANONICAL.items()}


def _detect_skiprows(filepath: Path) -> int:
    with open(filepath, encoding="utf-8") as f:
        first_line = f.readline()
    if "Buchungsdatum" in first_line or "Wertstellung" in first_line:
        return 0
    return 4


def load_raw_csv(filepath: Path) -> pd.DataFrame:
    """Load the latest bank CSV export schema into a normalized DataFrame."""
    skiprows = _detect_skiprows(filepath)
    df = pd.read_csv(
        filepath,
        encoding="utf-8",
        sep=";",
        skiprows=skiprows,
        decimal=",",
        quotechar='"',
    )

    df[COLS["amount"]] = (
        df[COLS["amount"]].astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    df[COLS["value_date"]] = pd.to_datetime(df[COLS["value_date"]], format="%d.%m.%y")
    df[COLS["date"]] = pd.to_datetime(df[COLS["date"]], format="%d.%m.%y")
    return df


def normalize_bank_export(filepath: Path) -> pd.DataFrame:
    """Normalize a raw bank export file to canonical columns."""
    return load_raw_csv(filepath)


def load_working_ledger(latest_only: bool = True) -> Optional[pd.DataFrame]:
    """Load the latest working ledger CSV from LEDGER_DIR, or None if absent."""
    if not LEDGER_DIR.exists():
        return None

    csv_files = sorted(
        LEDGER_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not csv_files:
        return None

    latest = csv_files[0]
    df = pd.read_csv(latest)

    if COLS["date"] not in df.columns and COLS["value_date"] in df.columns:
        df[COLS["date"]] = df[COLS["value_date"]]

    if COLS["value_date"] in df.columns:
        df[COLS["value_date"]] = pd.to_datetime(df[COLS["value_date"]])
    if COLS["date"] in df.columns:
        df[COLS["date"]] = pd.to_datetime(df[COLS["date"]])

    return df


def load_raw_exports() -> pd.DataFrame:
    """Load and concatenate all raw bank exports from RAW_EXPORTS_DIR."""
    if not RAW_EXPORTS_DIR.exists():
        raise FileNotFoundError(f"No raw exports directory: {RAW_EXPORTS_DIR}")

    frames: list[pd.DataFrame] = []
    for fp in sorted(RAW_EXPORTS_DIR.glob("*.csv")):
        frames.append(load_raw_csv(fp))

    if not frames:
        raise FileNotFoundError(f"No CSV exports found in {RAW_EXPORTS_DIR}")

    return pd.concat(frames, ignore_index=True)


def merge_new_transactions(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Merge new transactions into an existing ledger and dedupe by identity."""
    if existing is None or existing.empty:
        combined = new.copy()
    else:
        combined = pd.concat([existing, new], ignore_index=True)

    combined = combined.drop_duplicates(
        subset=MERGE_ID_COLUMNS,
        keep="first",
    )

    combined[COLS["value_date"]] = pd.to_datetime(combined[COLS["value_date"]])
    combined[COLS["date"]] = pd.to_datetime(combined[COLS["date"]])
    combined = sort_transactions(combined)
    return combined


def save_ledger(df: pd.DataFrame) -> Path:
    """Persist the current working ledger to LEDGER_DIR with a timestamped filename."""
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LEDGER_DIR / f"{LEDGER_BASENAME}_{ts}.csv"

    save_df = df.copy()

    if COLS["date"] not in save_df.columns and COLS["value_date"] in save_df.columns:
        save_df[COLS["date"]] = save_df[COLS["value_date"]]

    if "Zahlungspflichtige*r" not in save_df.columns:
        save_df["Zahlungspflichtige*r"] = pd.NA
    for extra_col in ["spending_type", "subtype", "confidence", "matched_keyword"]:
        if extra_col not in save_df.columns:
            save_df[extra_col] = pd.NA

    ordered_cols = [col for col in RAW_OUTPUT_COLUMN_ORDER if col in save_df.columns]
    save_df.to_csv(path, index=False, columns=ordered_cols)
    return path


def sort_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by value date descending, falling back to booking date."""
    sort_cols = [COLS["value_date"], COLS["date"]]
    return df.sort_values(by=sort_cols, ascending=False).reset_index(drop=True)
