"""
Personal Finance Dashboard
Restructured Dash app with tabbed layout, dark theme, KPI cards,
and an unknown-transactions review panel.
"""
from itertools import groupby
from dash import Dash, html, dash_table, dcc, callback, Output, Input, State, ctx
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
import dash_ag_grid as dag
import pandas as pd
import numpy as np
from pathlib import Path
from io import StringIO

# Resolve assets/ relative to this file (inside the package)
_PKG_DIR = Path(__file__).parent

from .data_loader import (
    COLS,
    DISPLAY_COLUMNS,
    load_working_ledger,
    load_raw_exports,
    merge_new_transactions,
    save_ledger,
    sort_transactions,
)
from .categorizer import (
    load_mapping,
    categorize_dataframe,
    categorize_unknowns,
    get_unknown_transactions,
    get_categorization_stats,
    export_unknowns_for_n8n,
)
from .charts import (
    make_timeseries, make_comparison_bar, make_sunburst,
    make_unknowns_bar, calc_diff, PALETTE, CATEGORY_COLORS,
)
from .tab_scenario import scenario_layout
from . import callbacks_scenario  # Register scenario callbacks

# ── Configuration ─────────────────────────────────────────────────────────

DATA_DIR = Path("data/sample")
MAPPING_FILE = DATA_DIR / Path("mapping.csv")
ESSENTIALITY_FILE = DATA_DIR / Path("category_essentiality.csv")
AVG_WINDOW = 3  # rolling average in months

# ── Data Pipeline ─────────────────────────────────────────────────────────

print("Loading data...")

df_ledger = load_working_ledger(latest_only=True)
try:
    df_raw = load_raw_exports()
except FileNotFoundError:
    df_raw = None

if df_ledger is None and df_raw is None:
    raise RuntimeError(
        "No working ledger and no raw bank exports found. "
        "Place CSV exports in raw_bank_exports/ or create a ledger in working_ledger/."
    )

if df_raw is not None:
    df = merge_new_transactions(df_ledger if df_ledger is not None else pd.DataFrame(), df_raw)
else:
    df = df_ledger

mapping = load_mapping(MAPPING_FILE)
df = categorize_unknowns(df, mapping)
df = sort_transactions(df)

stats = get_categorization_stats(df)
print(f"Loaded {stats['total_transactions']} transactions "
      f"({stats['coverage_pct']}% mapped, {stats['months']:.0f} months)"
      f" from {stats['date_from'].strftime('%Y-%m-%d')}"
      f" to {stats['date_to'].strftime('%Y-%m-%d')}.")

# ── Aggregations ──────────────────────────────────────────────────────────

costs_mthly_subtypes = (
    df.pivot_table(
        columns=[COLS["type"], COLS["subtype"]],
        index=COLS["value_date"],
        values=COLS["amount"],
        aggfunc="sum",
    )
    .resample("1ME").sum()
)

costs_mthly = costs_mthly_subtypes.T.groupby(level=COLS["type"]).sum().T

# Reorder: put Savings and Income last
for col in ["Savings", "Income"]:
    if col in costs_mthly.columns:
        tmp = costs_mthly.pop(col)
        costs_mthly.insert(costs_mthly.shape[1], col, tmp)

months_series = costs_mthly.index.strftime("%b %Y").to_series()
months_series.index = costs_mthly.index

costs_mthly["diff"] = costs_mthly.apply(calc_diff, axis=1)
costs_yearly = costs_mthly.resample("1YE").mean().round(0)
costs_avg = costs_mthly.rolling(AVG_WINDOW).mean().round(0)

df = sort_transactions(df)
unknowns = get_unknown_transactions(df)

# Build baseline aggregates for scenario tab (exclude Income, use 2025 average)
baseline_data = []
# Filter to 2025 data only
df_2025 = df[df[COLS["value_date"]].dt.year == 2026]
costs_2025_subtypes = (
    df_2025.pivot_table(
        columns=[COLS["type"], COLS["subtype"]],
        index=COLS["value_date"],
        values=COLS["amount"],
        aggfunc="sum",
    )
    .resample("1ME").sum()
)

# Load essentiality defaults from CSV
essentiality_defaults = {}
if ESSENTIALITY_FILE.exists():
    ess_df = pd.read_csv(ESSENTIALITY_FILE)
    for _, row in ess_df.iterrows():
        key = f"{row['type']}/{row['subtype']}"
        essentiality_defaults[key] = row["essentiality"]

for (spending_type, subtype), col_data in costs_2025_subtypes.items():
    if spending_type == "Income":  # Skip income for scenario planning
        continue
    baseline_amount = col_data.mean()
    key = f"{spending_type}/{subtype}"
    baseline_data.append({
        "type": spending_type,
        "subtype": subtype,
        "baseline": -baseline_amount,  # Flip sign: show expenses as positive
        "scenario_amount": -baseline_amount,
        "delta": 0,
        "essentiality": essentiality_defaults.get(key, "adjustable"),
    })

baseline_df = pd.DataFrame(baseline_data).sort_values(["type", "subtype"]).reset_index(drop=True)

# Prepare initial table data for scenario tab
initial_scenario_table_data = []
for _, row in baseline_df.iterrows():
    baseline_amount = row["baseline"]
    initial_scenario_table_data.append({
        "type": row["type"],
        "subtype": row["subtype"],
        "essentiality": row["essentiality"],
        "baseline": round(baseline_amount, 0),
        "scenario_amount": round(baseline_amount, 0),
        "delta": 0,
    })

# Calculate average monthly income for income ceiling indicator
income_2025 = -df_2025[df_2025[COLS["type"]] == "Income"][COLS["amount"]].sum() / max(df_2025[COLS["value_date"]].dt.month.nunique(), 1) if not df_2025.empty else 0

# ── App Setup ─────────────────────────────────────────────────────────────

load_figure_template("darkly")

app = Dash(
    __name__,
    assets_folder=str(_PKG_DIR / "assets"),
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
)

# ── Reusable Components ──────────────────────────────────────────────────

def kpi_card(title: str, value: str, subtitle: str = "", color: str = PALETTE["text"]):
    return dbc.Card(
        dbc.CardBody([
            html.P(title, className="kpi-label"),
            html.H3(value, className="kpi-value", style={"color": color}),
            html.Small(subtitle, className="kpi-sub"),
        ]),
        className="kpi-card",
    )


def month_selector(dropdown_id="month-input"):
    return dcc.Dropdown(
        id=dropdown_id,
        options=[
            {"label": v, "value": str(i)} for i, v in months_series.items()
        ],
        value=str(months_series.index[-1]),
        clearable=False,
        className="month-dropdown",
    )


def timeline_selector():
    return dbc.RadioItems(
        id="ts-timeline",
        options=[
            {"label": "6m", "value": 6},
            {"label": "1y", "value": 12},
            {"label": "2y", "value": 24},
            {"label": "All", "value": 0},
        ],
        value=12,
        inline=True,
        className="timeline-radio",
    )


# ── Tab: Overview ─────────────────────────────────────────────────────────

tab_overview = dbc.Tab(label="Overview", tab_id="tab-overview", children=[
    # KPI Row
    dbc.Row([
        dbc.Col(kpi_card(
            "Transactions",
            f"{stats['total_transactions']:,}",
            f"{stats['transactions_per_month']:.0f} / month",
        ), md=3),
        dbc.Col(kpi_card(
            "Coverage",
            f"{stats['coverage_pct']}%",
            f"{stats['unknown_transactions']} unmapped",
            color=PALETTE["success"] if stats["coverage_pct"] > 90 else PALETTE["warning"],
        ), md=3),
        dbc.Col(kpi_card(
            "Unmapped Volume",
            f"{stats['unknown_per_month']:.0f}€/mo",
            f"{stats['unknown_amount']:.0f}€ total",
            color=PALETTE["error"],
        ), md=3),
        dbc.Col(kpi_card(
            "Date Range",
            f"{stats['months']:.0f} months",
            f"{stats['date_from'].strftime('%b %Y')} – {stats['date_to'].strftime('%b %Y')}",
        ), md=3),
    ], className="kpi-row"),

    # Controls
    dbc.Row([
        dbc.Col(month_selector(), md=3),
        dbc.Col(timeline_selector(), md=4),
    ], className="controls-row"),

    # Time series
    dbc.Row([
        dbc.Col(dcc.Graph(id="ts-chart", figure={}, config={"displayModeBar": False}), md=12),
    ]),

    # Comparison + Sunburst
    dbc.Row([
        dbc.Col(dcc.Graph(id="comparison-chart", figure={}, config={"displayModeBar": False}), md=8),
        dbc.Col(dcc.Graph(id="sunburst-chart", figure={}, config={"displayModeBar": False}), md=4),
    ]),
])


# ── Tab: Aggregations ─────────────────────────────────────────────────────

def make_spending_grid(
    costs_mthly_subtypes: pd.DataFrame,
    palette: dict,
    open_years_by_default: bool = False,
    highlight_factor: float = 1.5,
    height: str = "600px",
) -> dag.AgGrid:
    """
    Community-compatible AG Grid:
    - pinned left columns: spending_type, subtype
    - year column groups
    - closed year group -> yearly monthly average column
    - open year group -> individual month columns
    - DataTable-like conditional formatting
    """

    # 1) reshape: rows = (spending_type, subtype), cols = months
    df = costs_mthly_subtypes.T.copy()
    df.index = pd.MultiIndex.from_tuples(df.index)
    df = df.reset_index()
    df.columns = ["spending_type", "subtype"] + [
        c.strftime("%Y-%m") if hasattr(c, "strftime") else str(c)
        for c in df.columns[2:]
    ]

    # Only real month columns, newest first
    month_cols = [c for c in df.columns if isinstance(c, str) and len(c) == 7 and c[4] == "-"]
    month_cols = sorted(month_cols, reverse=True)

    def month_to_year(m: str) -> str:
        return m[:4]

    year_groups = {
        year: list(months)
        for year, months in groupby(month_cols, month_to_year)
    }

    # 2) compute yearly representations as monthly averages across months in that year
    for year, months in year_groups.items():
        df[f"{year}_mthly_avg"] = df[months].mean(axis=1).round(0)

    # 3) compute thresholds from the same dataframe used by the grid
    averages = {m: float(df[m].dropna().mean()) if df[m].notna().any() else 0.0 for m in month_cols}
    for year in year_groups:
        ycol = f"{year}_mthly_avg"
        averages[ycol] = float(df[ycol].dropna().mean()) if df[ycol].notna().any() else 0.0

    # 4) reusable numeric column factory
    def money_col(
        field: str,
        header: str,
        width: int = 82,
        group_show: str | None = None,
        yearly_avg_field: str | None = None,
        highlight_factor: float = 1.5,
    ):
        if yearly_avg_field is not None:
            condition = (
                f"params.value != null && "
                f"params.data != null && "
                f"params.data['{yearly_avg_field}'] != null && "
                f"params.value != 0 && "
                f"Math.abs(params.value) > Math.abs(params.data['{yearly_avg_field}']) * {highlight_factor}"
            )
            style_conditions = [
                {
                    "condition": condition,
                    "style": {
                        "backgroundColor": "rgba(209, 99, 167, 0.12)",
                        "color": PALETTE["error"],
                        "fontWeight": "700",
                    },
                }
            ]
        else:
            style_conditions = [
                {
                    "condition": "params.value != null && params.value === 0",
                    "style": {
                        "color": PALETTE["error"],
                        "fontWeight": "600",
                    },
                }
            ]

        col = {
            "field": field,
            "headerName": header,
            "type": "numericColumn",
            "width": width,
            "valueFormatter": {
                "function": 'params.value != null && params.value !== 0 ? params.value.toFixed(0) + "€" : ""'
            },
            "cellStyle": {
                "defaultStyle": {
                    "textAlign": "right",
                },
                "styleConditions": style_conditions,
            },
        }

        if group_show:
            col["columnGroupShow"] = group_show

        return col

    # 5) left pinned columns
    column_defs = [
        {
            "field": "spending_type",
            "headerName": "Spending Type",
            "pinned": "left",
            "width": 120,
            "cellStyle": {
                "fontWeight": "500",
            },
        },
        {
            "field": "subtype",
            "headerName": "Subtype",
            "pinned": "left",
            "width": 140,
            "cellStyle": {
                "fontWeight": "600",
            },
        },
    ]

    # 6) grouped year columns
    for year, months in year_groups.items():
        yearly_avg_field = f"{year}_mthly_avg"

        children = [
            money_col(
                field=yearly_avg_field,
                header=f"{year} avg",
                width=96,
                group_show="closed",
                yearly_avg_field=None,
                highlight_factor=highlight_factor,
            )
        ]

        for m in months:
            children.append(
                money_col(
                    field=m,
                    header=pd.Timestamp(m).strftime("%b"),
                    width=78,
                    group_show="open",
                    yearly_avg_field=yearly_avg_field,
                    highlight_factor=highlight_factor,
                )
            )

        column_defs.append(
            {
                "headerName": year,
                "groupId": f"year-{year}",
                "openByDefault": open_years_by_default,
                "marryChildren": True,
                "children": children,
            }
        )

    return dag.AgGrid(
        id="spending-grid",
        rowData=df.to_dict("records"),
        columnDefs=column_defs,
        defaultColDef={
            "resizable": True,
            "sortable": True,
        },
        dashGridOptions={
            "animateRows": False,
            "suppressAggFuncInHeader": True,
            "theme": {
                "function": "themeQuartz.withParams({"
                    f"backgroundColor: '{palette['bg']}',"
                    f"foregroundColor: '{palette['text']}',"
                    f"headerTextColor: '{palette['text_muted']}',"
                    f"headerBackgroundColor: '{palette['surface_alt']}',"
                    f"oddRowBackgroundColor: '{palette['surface']}',"
                    f"headerColumnResizeHandleColor: '{palette['border']}'"
                "})"
            },
        },
        style={"height": height},
    )


tab_aggregates = dbc.Tab(
    label="Aggregations",
    tab_id="tab-aggregates",
    children=[
        html.Div(
            "Highlighted monthly values are overspends: >1.5x of that category's average month in the same year.",
            style={
                "color": PALETTE["text_muted"],
                "fontSize": "0.9rem",
                "marginBottom": "8px",
            },
        ),
        make_spending_grid(
            costs_mthly_subtypes=costs_mthly_subtypes,
            palette=PALETTE,
            open_years_by_default=False,
            highlight_factor=1.5,
            height="900px",
        )
    ],
)

# ── Tab: Transactions ─────────────────────────────────────────────────────

def table_type(series):
    """Map pandas dtype to Dash table type."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    elif pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "text"


tab_transactions = dbc.Tab(label="Transactions", tab_id="tab-transactions", children=[
    dbc.Row([
        dbc.Col(month_selector("tx-month-input"), md=3, id="tx-month-wrapper"),
        dbc.Col(
            dbc.Button(
                "📥 Export Deduped CSV",
                id="export-csv-btn",
                color="primary",
                size="sm",
                className="ms-2",
            ),
            md=2,
        ),
    ], className="controls-row"),
    dcc.Download(id="download-dataframe-csv"),
    dash_table.DataTable(
        id="tx-table",
        data=df[DISPLAY_COLUMNS].to_dict("records"),
        columns=[
            {"name": c, "id": c, "type": table_type(df[c])} for c in DISPLAY_COLUMNS
        ],
        page_size=25,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": PALETTE["surface"],
            "color": PALETTE["text"],
            "fontWeight": "600",
            "borderBottom": f"1px solid {PALETTE['border']}",
        },
        style_cell={
            "backgroundColor": PALETTE["bg"],
            "color": PALETTE["text"],
            "border": f"1px solid {PALETTE['border']}",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "maxWidth": 400,
            "fontSize": "13px",
            "fontFamily": "Inter, system-ui, sans-serif",
            "padding": "8px 12px",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": '{spending_type} = "unknown"'},
                "backgroundColor": "rgba(209, 99, 167, 0.08)",
                "color": PALETTE["error"],
            },
            {
                "if": {"filter_query": f'{{{COLS["amount"]}}} > 0'},
                "color": PALETTE["success"],
            },
        ],
        style_filter={
            "backgroundColor": PALETTE["surface_alt"],
            "color": PALETTE["text"],
        },
    ),
])

# ── Tab: Mapping ──────────────────────────────────────────────────────────

tab_mapping = dbc.Tab(
    label="Mapping",
    tab_id="tab-mapping",
    children=[
        dbc.Row([
            dbc.Col([
                html.H5("Categorization Rules", className="section-title"),
                html.P(
                    f"Total mappings: {len(mapping['keyword'].dropna())} rules",
                    className="section-sub",
                ),
            ], md=10),
            dbc.Col([
                dbc.Button(
                    "🔄 Reload Mapping",
                    id="remap-btn",
                    color="primary",
                    size="sm",
                    className="ms-2",
                    style={"marginTop": "8px"},
                ),
            ], md=2, className="text-end"),
        ]),
        dbc.Row([
            dbc.Col([
                dash_table.DataTable(
                    id="mapping-table",
                    data=mapping.to_dict("records"),
                    columns=[
                        {"name": c, "id": c, "type": table_type(mapping[c])} for c in mapping.columns
                    ],
                    page_size=30,
                    sort_action="native",
                    filter_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": PALETTE["surface"],
                        "color": PALETTE["text"],
                        "fontWeight": "600",
                        "borderBottom": f"1px solid {PALETTE['border']}",
                    },
                    style_cell={
                        "backgroundColor": PALETTE["bg"],
                        "color": PALETTE["text"],
                        "border": f"1px solid {PALETTE['border']}",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "maxWidth": 400,
                        "fontSize": "13px",
                        "fontFamily": "Inter, system-ui, sans-serif",
                        "padding": "8px 12px",
                    },
                    style_filter={
                        "backgroundColor": PALETTE["surface_alt"],
                        "color": PALETTE["text"],
                    },
                ),
            ], md=12),
        ]),
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.P("Format:", className="kpi-label"),
                        html.Ul([
                            html.Li(html.Strong("row"), ": Column to search in (Auftraggeber, Verwendungszweck, Kontonummer, Zahlungspflichtige*r)"),
                            html.Li(html.Strong("spending_type"), ": Top-level category (Food, Transport, etc.)"),
                            html.Li(html.Strong("keyword"), ": Text to match in the column"),
                            html.Li(html.Strong("subtype"), ": Sub-category (groceries, bakery, etc.)"),
                        ], style={"fontSize": "13px"}),
                    ])
                ),
                md=12,
                className="mt-3",
            ),
        ]),
    ],
)


# ── Tab: Unmapped ─────────────────────────────────────────────────────────

tab_unmapped = dbc.Tab(
    label=f"Unmapped ({stats['unknown_transactions']})",
    tab_id="tab-unmapped",
    children=[
        dbc.Row([
            dbc.Col([
                html.H5("Top Unmapped Recipients", className="section-title"),
                html.P(
                    f"{stats['unknown_transactions']} transactions, "
                    f"~{stats['unknown_per_month']:.0f}€/month unassigned",
                    className="section-sub",
                ),
                dcc.Graph(id="unknowns-chart", figure=make_unknowns_bar(unknowns)),
            ], md=7),
            dbc.Col([
                html.H5("n8n Export", className="section-title"),
                html.P(
                    "Unknown transactions are auto-exported to "
                    "data/unknowns_for_n8n.json on startup. "
                    "Use this file as webhook payload in your n8n workflow.",
                    className="section-sub",
                ),
                dbc.Card([
                    dbc.CardBody([
                        html.P("Suggested n8n flow:", className="kpi-label"),
                        html.Ol([
                            html.Li("Webhook receives unknowns JSON"),
                            html.Li("LLM node suggests category + confidence"),
                            html.Li("Split by confidence: high → auto-apply, medium → review queue"),
                            html.Li("Human review node (n8n form or wait)"),
                            html.Li("Write approved mappings back to mapping.csv"),
                        ], style={"fontSize": "13px"}),
                    ])
                ], className="kpi-card", style={"marginTop": "16px"}),
            ], md=5),
        ]),
    ],
)

# ── Layout ────────────────────────────────────────────────────────────────

app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H4("Finance", className="app-title"),
            html.Span(
                f"{stats['date_from'].strftime('%Y')}–{stats['date_to'].strftime('%Y')}",
                className="app-subtitle",
            ),
        ], className="header-left"),
    ], className="app-header"),

    # Tabs
    dbc.Tabs(
        id="main-tabs",
        active_tab="tab-overview",
        children=[tab_overview, tab_aggregates,tab_transactions, tab_mapping, tab_unmapped, scenario_layout(initial_scenario_table_data)],
        className="main-tabs",
    ),

    # Store for scenario state
    dcc.Store(id="scenario-store", data={
        "scenario_name": "Scenario A",
        "overrides": {},
        "essentiality": essentiality_defaults,  # Initialize with CSV defaults
        "baseline_income": float(income_2025) if income_2025 > 0 else -float(income_2025),
    }),
], className="app-container")


# ── Callbacks ─────────────────────────────────────────────────────────────

@callback(
    Output("mapping-table", "data"),
    Input("remap-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reload_mapping(n_clicks):
    """Reload mapping CSV and update table."""
    global mapping, df

    if n_clicks is None or n_clicks == 0:
        return mapping.to_dict("records")

    # Reload mapping.csv
    mapping = load_mapping(MAPPING_FILE)

    # Re-categorize only currently unknown transactions
    df = categorize_unknowns(df, mapping)

    print(f"Remapped unknowns: {len(mapping['keyword'].dropna())} rules applied")

    return mapping.to_dict("records")


@callback(
    Output("ts-chart", "figure"),
    Input("ts-timeline", "value"),
    Input("month-input", "value"),
)
def update_timeseries(timeline, month):
    return make_timeseries(costs_avg, costs_mthly, timeline, month)


@callback(
    Output("comparison-chart", "figure"),
    Input("month-input", "value"),
)
def update_comparison(month):
    return make_comparison_bar(costs_mthly, costs_avg, costs_yearly, month)


@callback(
    Output("sunburst-chart", "figure"),
    Input("month-input", "value"),
)
def update_sunburst(_month):
    return make_sunburst(costs_mthly_subtypes)


@callback(
    Output("tx-table", "filter_query"),
    Output("tx-table", "sort_by"),
    Input("tx-month-input", "value"),
)
def update_table_filter(month):
    query = "{Buchungsdatum} scontains " + pd.Timestamp(month).date().__str__()[:-3]
    sort_by = [{"column_id": COLS["amount"], "direction": "asc"}]
    return query, sort_by


@callback(
    Output("download-dataframe-csv", "data"),
    Input("export-csv-btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_deduped_csv(n_clicks):
    """
    Export the deduplicated dataframe as CSV.
    Removes only exact duplicates: same date, amount, recipient, and purpose.
    This preserves recurring expenses while removing bank export overlaps.
    """
    if n_clicks is None or n_clicks == 0:
        return None
    
    original_count = len(df)
    
    # Deduplicate: only drop identical transactions
    # (same date, amount, recipient, purpose)
    deduped = df.drop_duplicates(
        subset=[COLS["date"], COLS["amount"], COLS["recipient"], COLS["purpose"]],
        keep="first"
    ).sort_values(by=COLS["value_date"], ascending=False)
    
    dropped_count = original_count - len(deduped)
    print(f"Deduplication: dropped {dropped_count} exact duplicate lines ({dropped_count/original_count*100:.1f}%)")
    
    # Persist ledger snapshot for user workflow
    ledger_path = save_ledger(deduped)
    print(f"Saved working ledger to {ledger_path}")

    # Return as CSV download as well
    return dcc.send_data_frame(
        deduped.to_csv,
        filename=f"finance_ledger_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        index=False,
    )


# ── Run ───────────────────────────────────────────────────────────────────

def main():
    """Entry point for `uvx finance-dashboard` or `finance-dashboard` CLI."""
    app.run(debug=True, host="0.0.0.0", port=8050)


if __name__ == "__main__":
    main()
