"""
Data loading module for personal finance dashboard.
Handles multiple CSV export schema versions from German banks.
"""
import pandas as pd
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


# Canonical column names used throughout the app
COLS = {
    "date": "Buchungstag",
    "value_date": "Wertstellung",
    "amount": "Betrag (EUR)",
    "recipient": "Auftraggeber / Begünstigter",
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


@dataclass
class SchemaVersion:
    """Describes a bank CSV export schema version."""
    name: str
    encoding: str
    separator: str
    skiprows: int
    decimal: str
    date_format: str
    rename_map: dict
    drop_columns: list
    amount_cleanup: bool  # needs non-breaking space + € removal


# Known schema versions
SCHEMA_OLD = SchemaVersion(
    name="legacy",
    encoding="ansi",
    separator=";",
    skiprows=6,
    decimal=",",
    date_format="%d.%m.%Y",
    rename_map={},
    drop_columns=["Unnamed: 11"],
    amount_cleanup=False,
)

SCHEMA_NEW_V1 = SchemaVersion(
    name="new_v1",
    encoding="utf-8",
    separator=";",
    skiprows=4,
    decimal=",",
    date_format="%d.%m.%y",
    rename_map={
        "Buchungsdatum": "Buchungstag",
        "Zahlungsempfänger*in": "Auftraggeber / Begünstigter",
        "Betrag": "Betrag (EUR)",
    },
    drop_columns=["Status", "Umsatztyp"],
    amount_cleanup=True,
)

SCHEMA_NEW_V2 = SchemaVersion(
    name="new_v2",
    encoding="utf-8",
    separator=";",
    skiprows=4,
    decimal=",",
    date_format="%d.%m.%y",
    rename_map={
        "Buchungsdatum": "Buchungstag",
        "Zahlungsempfänger*in": "Auftraggeber / Begünstigter",
        "Betrag (€)": "Betrag (EUR)",
    },
    drop_columns=["Status", "Umsatztyp", "IBAN"],
    amount_cleanup=True,
)


def detect_schema(filepath: Path) -> SchemaVersion:
    """Auto-detect CSV schema version by peeking at headers."""
    # Try UTF-8 first, fall back to ANSI
    for enc in ["utf-8", "ansi"]:
        try:
            # Read first few lines to detect
            with open(filepath, encoding=enc) as f:
                lines = [f.readline() for _ in range(7)]
            header_line = lines[4] if enc == "utf-8" else lines[6]

            if "Betrag (€)" in header_line or "Betrag (€)" in header_line:
                return SCHEMA_NEW_V2
            elif "Buchungsdatum" in header_line:
                return SCHEMA_NEW_V1
            elif "Buchungstag" in header_line:
                return SCHEMA_OLD
        except (UnicodeDecodeError, IndexError):
            continue

    # Fallback: use filename heuristic
    if "-" in filepath.stem:
        return SCHEMA_NEW_V1
    return SCHEMA_OLD


def load_raw_csv(filepath: Path, schema: Optional[SchemaVersion] = None) -> pd.DataFrame:
    """Load a single bank CSV export into a normalized DataFrame."""
    if schema is None:
        schema = detect_schema(filepath)

    df = pd.read_csv(
        filepath,
        encoding=schema.encoding,
        sep=schema.separator,
        skiprows=schema.skiprows,
        decimal=schema.decimal,
        quotechar='"',
    )

    # Rename columns to canonical names
    if schema.rename_map:
        df = df.rename(columns=schema.rename_map)

    # Drop schema-specific extra columns (ignore errors for missing cols)
    if schema.drop_columns:
        df = df.drop(columns=schema.drop_columns, errors="ignore")

    # Clean amount column
    amount_col = COLS["amount"]
    if schema.amount_cleanup:
        df[amount_col] = df[amount_col].astype(str).apply(
            lambda x: x.replace("\xa0€", "").replace("\xa0", "")
        )
    df[amount_col] = (
        df[amount_col].astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # Parse dates
    df[COLS["value_date"]] = pd.to_datetime(df[COLS["value_date"]], format=schema.date_format)
    df[COLS["date"]] = pd.to_datetime(df[COLS["date"]], format=schema.date_format)

    return df


def load_from_directory(raw_dir: Path, filenames: list[str]) -> pd.DataFrame:
    """Load and concatenate multiple CSV files from a directory."""
    frames = []
    for name in filenames:
        fp = raw_dir / f"{name}.csv"
        if fp.exists():
            frames.append(load_raw_csv(fp))
        else:
            print(f"Warning: {fp} not found, skipping.")
    if not frames:
        raise FileNotFoundError(f"No valid CSV files found in {raw_dir}")
    return pd.concat(frames, ignore_index=True)


def load_combined(bigcsv: Path, ytd_file: Optional[Path] = None) -> pd.DataFrame:
    """
    Load a pre-combined CSV and optionally append a year-to-date export.
    This is the primary loading path.
    """
    df = pd.read_csv(bigcsv)
    df[COLS["value_date"]] = pd.to_datetime(df[COLS["value_date"]])
    df[COLS["date"]] = pd.to_datetime(df[COLS["date"]])

    if ytd_file and ytd_file.exists():
        ytd = load_raw_csv(ytd_file)
        # Deduplicate by removing any overlap
        if not df.empty:
            cutoff = df[COLS["date"]].max()
            ytd = ytd[ytd[COLS["date"]] > cutoff]
        df = pd.concat([df, ytd], ignore_index=True)

    return df


def sort_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by date descending, reset index."""
    return df.sort_values(by=COLS["date"], ascending=False).reset_index(drop=True)
