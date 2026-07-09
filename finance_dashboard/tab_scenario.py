"""
Scenario planning tab layout.
"""
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from .config import CONFIG
from .charts import PALETTE, CATEGORY_COLORS

GRAPH_CONFIG = CONFIG["app"]["graphs"]


def scenario_layout(initial_table_data=None):
    """Build the scenario planning tab."""
    if initial_table_data is None:
        initial_table_data = []

    return dbc.Tab(
        label="Scenario",
        tab_id="tab-scenario",
        children=[
            # KPI Row
            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P("Baseline Monthly", className="kpi-label"),
                            html.H3("€0", id="scenario-kpi-baseline", className="kpi-value"),
                        ]),
                        className="kpi-card",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P("Scenario Monthly", className="kpi-label"),
                            html.H3("€0", id="scenario-kpi-scenario", className="kpi-value"),
                        ]),
                        className="kpi-card",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P("Δ Monthly", className="kpi-label"),
                            html.H3("€0", id="scenario-kpi-delta", className="kpi-value"),
                        ]),
                        className="kpi-card",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P("Savings / Year", className="kpi-label"),
                            html.H3("€0", id="scenario-kpi-annual", className="kpi-value"),
                        ]),
                        className="kpi-card",
                    ),
                    md=3,
                ),
            ], className="kpi-row"),

            # Main content: Left (table) + Right (chart)
            dbc.Row([
                dbc.Col([
                    html.H5("Spending Categories", className="section-title"),
                    html.P(
                        "Edit Scenario € to adjust monthly spending. Green = saved, Red = overspend. Essentiality: essential | adjustable | optional",
                        className="section-sub",
                    ),
                    dash_table.DataTable(
                        id="scenario-table",
                        columns=[
                            {"name": "Type", "id": "type", "editable": False},
                            {"name": "Subtype", "id": "subtype", "editable": False},
                            {
                                "name": "Essential",
                                "id": "essentiality",
                                "editable": True,
                                "type": "text",
                            },
                            {
                                "name": "Ø Baseline (€)",
                                "id": "baseline",
                                "type": "numeric",
                                "editable": False,
                                "format": {"specifier": ".0f"},
                            },
                            {
                                "name": "Scenario (€)",
                                "id": "scenario_amount",
                                "type": "numeric",
                                "editable": True,
                                "format": {"specifier": ".0f"},
                            },
                        ],
                        data=initial_table_data,
                        page_size=15,
                        sort_action="native",
                        sort_by=[{'column_id': 'baseline', 'direction': 'desc'}],
                        filter_action="native",
                        editable=True,
                        style_table={"overflowX": "auto", "overflowY": "auto"},
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
                            "overflow": "visible",
                            "textOverflow": "clip",
                            "maxWidth": 300,
                            "fontSize": "13px",
                            "fontFamily": "Inter, system-ui, sans-serif",
                            "padding": "8px 12px",
                        },
                        style_data_conditional=[],
                        style_filter={
                            "backgroundColor": PALETTE["surface_alt"],
                            "color": PALETTE["text"],
                        },
                    ),
                ], md=7),

                dbc.Col([
                    html.H5("Scenario Comparison", className="section-title"),
                    dcc.Graph(
                        id="scenario-chart",
                        figure={},
                        config={"displayModeBar": GRAPH_CONFIG.get("display_mode_bar", False)},
                    ),
                                # Assumption log (under chart, right side)
                    dbc.Row([
                        html.H5("Assumptions", className="section-title"),
                        dcc.Markdown(
                            id="scenario-log",
                            children="📝 No adjustments yet. Edit the Scenario € column to make changes.",
                            className="section-sub",
                        ),
                    ]),
                ], md=5),
            ]),


        ],
    )

