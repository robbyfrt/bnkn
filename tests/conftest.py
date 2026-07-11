import pytest
import pandas as pd
import io
from pathlib import Path
from finance_dashboard.data_loader import COLS

@pytest.fixture
def minimal_transactions():
    """Minimal in-memory ledger with known data."""
    return pd.DataFrame({
        COLS["date"]: pd.to_datetime(["2025-01-15", "2025-01-20", "2025-02-01"]),
        COLS["value_date"]: pd.to_datetime(["2025-01-15", "2025-01-20", "2025-02-01"]),
        COLS["amount"]: [-42.50, -9.99, 2500.00],
        COLS["recipient"]: ["ALDI SUED", "Netflix", "Arbeitgeber GmbH"],
        COLS["purpose"]: ["Lebensmittel", "Abo", "Gehalt Jan"],
        COLS["account"]: ["DE00...", "DE00...", "DE00..."],
        COLS["payer"]: [pd.NA, pd.NA, "Arbeitgeber GmbH"],
        COLS["type"]: ["unknown", "unknown", "unknown"],
        COLS["subtype"]: ["unknown", "unknown", "unknown"],
    })

@pytest.fixture
def minimal_mapping():
    return pd.DataFrame({
        "row": ["Zahlungsempfänger*in", "Zahlungsempfänger*in", "Zahlungsempfänger*in"],
        "keyword": ["ALDI", "Netflix", "Arbeitgeber"],
        "spending_type": ["Food", "Recurring", "Income"],
        "subtype": ["supermarket", "streaming", "salary"],
    })

@pytest.fixture
def raw_csv_text():
    header = [
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
    ]
    rows = [
        [
            "15.01.25",
            "15.01.25",
            "Gebucht",
            "",
            "ALDI SUED",
            "Lebensmittel",
            "Lastschrift",
            "DE00...",
            "-42,50",
            "",
            "",
            "",
        ],
        [
            "20.01.25",
            "20.01.25",
            "Gebucht",
            "",
            "Netflix",
            "Abo",
            "Lastschrift",
            "DE00...",
            "-9,99",
            "",
            "",
            "",
        ],
    ]
    lines = [";".join(header)] + [";".join(row) for row in rows]
    return "\n".join(lines) + "\n"