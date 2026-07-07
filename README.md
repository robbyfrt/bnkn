# bnkn

## Data flow

- Place bank CSV exports in `raw_bank_exports/`.
- Optional: place an existing `ledger_*.csv` in `working_ledger/` to reuse prior categorizations.
- On startup, the app:
  - loads the latest ledger from `working_ledger/` if present,
  - loads all raw exports from `raw_bank_exports/`,
  - merges and dedupes transactions by date, amount, recipient, and purpose,
  - categorizes only unknown rows via `mapping.csv`.
- Use the "Export Deduped CSV" button in the Transactions tab to save a new working ledger snapshot into `working_ledger/` and download it.
