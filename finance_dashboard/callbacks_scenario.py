"""
Scenario planning callbacks.
Handles table edits, KPI updates, chart rendering, and assumption logs.
"""
import pandas as pd
from dash import callback, Output, Input, State, clientside_callback
import plotly.graph_objects as go
from .charts import CATEGORY_COLORS, PALETTE


# Chart type button handlers - REMOVED (only Grouped Bar chart now)


@callback(
    Output("scenario-kpi-delta", "style"),
    Output("scenario-kpi-annual", "style"),
    Input("scenario-store", "data"),
    Input("scenario-table", "data"),
)
def color_delta_kpis(store_data, table_data):
    """Color KPI values red/green based on savings."""
    if not table_data:
        return {}, {}

    baseline_total = sum(row["baseline"] for row in table_data)
    scenario_total = sum(row["scenario_amount"] for row in table_data)
    delta = scenario_total - baseline_total

    delta_color = PALETTE["success"] if delta <= 0 else PALETTE["error"]

    return {"color": delta_color}, {"color": delta_color}


@callback(
    Output("scenario-store", "data"),
    Input("scenario-table", "data"),
    State("scenario-store", "data"),
    prevent_initial_call=False,
)
def update_store_from_table(table_data, store_data):
    """Sync table edits to store."""
    if not table_data or not store_data:
        return store_data or {"overrides": {}, "essentiality": {}}

    overrides = {}
    essentiality = {}

    for row in table_data:
        key = f"{row['type']}/{row['subtype']}"
        baseline = row["baseline"]
        scenario = row["scenario_amount"]

        # Track changes
        if scenario != baseline:
            overrides[key] = scenario

        # Track essentiality
        essentiality[key] = row.get("essentiality", "adjustable")

    store_data["overrides"] = overrides
    store_data["essentiality"] = essentiality

    return store_data


@callback(
    Output("scenario-kpi-baseline", "children"),
    Output("scenario-kpi-scenario", "children"),
    Output("scenario-kpi-delta", "children"),
    Output("scenario-kpi-annual", "children"),
    Input("scenario-store", "data"),
    Input("scenario-table", "data"),
)
def update_kpis(store_data, table_data):
    """Update KPI cards with totals."""
    if not table_data:
        return "€0", "€0", "€0", "€0"

    baseline_total = sum(row["baseline"] for row in table_data)
    scenario_total = sum(row["scenario_amount"] for row in table_data)
    delta = scenario_total - baseline_total
    annual = delta * 12

    return (
        f"€{baseline_total:,.0f}",
        f"€{scenario_total:,.0f}",
        f"€{delta:+,.0f}",
        f"€{annual:+,.0f}",
    )


@callback(
    Output("scenario-table", "style_data_conditional"),
    Input("scenario-store", "data"),
    Input("scenario-table", "derived_virtual_data"),
)
def update_table_styles(store_data, table_data):
    """Highlight changed rows in table (show savings/overspend)."""
    if not table_data:
        return []

    ess_colors = {
        "essential": "rgba(150, 150, 150, 0.2)",      # Grey - fixed
        "adjustable": "rgba(255, 152, 0, 0.2)",       # Amber - flexible
        "optional": "rgba(76, 175, 80, 0.2)",         # Green - truly optional
    }

    styles = []
    for i, row in enumerate(table_data):
        styles.append({
            "if": {"row_index": i,"column_id": "essentiality"},
            "backgroundColor": ess_colors.get(row.get("essentiality", "adjustable"), "rgba(255, 152, 0, 0.8)"),
        })
        delta = row["scenario_amount"] - row["baseline"]

        # Color scenario_amount cell based on savings/overspend
        if delta < 0:
            # Reduced spending (green)
            styles.append({
                "if": {"row_index": i, "column_id": "scenario_amount"},
                "backgroundColor": "rgba(76, 175, 80, 0.15)",
                "color": PALETTE["success"],
                "fontWeight": "bold",
            })
        elif delta > 0:
            # Increased spending (red)
            styles.append({
                "if": {"row_index": i, "column_id": "scenario_amount"},
                "backgroundColor": "rgba(209, 99, 167, 0.15)",
                "color": PALETTE["error"],
                "fontWeight": "bold",
            })

    return styles


@callback(
    Output("scenario-chart", "figure"),
    Input("scenario-store", "data"),
    Input("scenario-table", "data"),
)
def update_scenario_chart(store_data, table_data):
    """Build stacked bar chart grouped by essentiality (Baseline vs Scenario)."""
    if not table_data or len(table_data) == 0:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False)
        return fig

    # Aggregate by essentiality from store (not from table display format)
    essentiality_summary = {"essential": {}, "adjustable": {}, "optional": {}}
    essentiality_map = store_data.get("essentiality", {}) if store_data else {}
    
    for row in table_data:
        key = f"{row['type']}/{row['subtype']}"
        # Get essentiality from store, fall back to "adjustable"
        ess = essentiality_map.get(key, "adjustable")
        baseline = row["baseline"]
        scenario = row["scenario_amount"]

        if "baseline" not in essentiality_summary[ess]:
            essentiality_summary[ess]["baseline"] = 0
            essentiality_summary[ess]["scenario"] = 0

        essentiality_summary[ess]["baseline"] += baseline
        essentiality_summary[ess]["scenario"] += scenario

    # Prepare data for stacked bars
    essentialities = ["essential", "adjustable", "optional"]
    baseline_values = [essentiality_summary[e].get("baseline", 0) for e in essentialities]
    scenario_values = [essentiality_summary[e].get("scenario", 0) for e in essentialities]

    # Color mapping for essentiality
    ess_colors = {
        "essential": "rgba(150, 150, 150, 0.8)",      # Grey - fixed
        "adjustable": "rgba(255, 152, 0, 0.8)",       # Amber - flexible
        "optional": "rgba(76, 175, 80, 0.8)",         # Green - truly optional
    }

    # Create stacked bars
    fig = go.Figure()

    # Baseline stacked bar
    for i, ess in enumerate(essentialities):
        fig.add_trace(go.Bar(
            x=["Baseline"],
            y=[baseline_values[i]],
            name=ess.capitalize(),
            marker_color=ess_colors[ess],
            text=f"€{baseline_values[i]:.0f}" if baseline_values[i] > 0 else "",
            textposition="inside",
            hovertemplate=f"{ess.capitalize()}: €%{{y:.0f}}<extra></extra>",
        ))

    # Scenario stacked bar
    for i, ess in enumerate(essentialities):
        fig.add_trace(go.Bar(
            x=["Scenario"],
            y=[scenario_values[i]],
            marker_color=ess_colors[ess],
            showlegend=False,
            text=f"€{scenario_values[i]:.0f}" if scenario_values[i] > 0 else "",
            textposition="inside",
            hovertemplate=f"{ess.capitalize()}: €%{{y:.0f}}<extra></extra>",
        ))

    # Add income reference line
    if store_data and "baseline_income" in store_data:
        income = store_data["baseline_income"]
        fig.add_hline(
            y=income,
            line_dash="dash",
            line_color=PALETTE["success"],
            annotation_text="Income ceiling",
            annotation_position="right",
        )

    fig.update_layout(
        barmode="stack",
        height=400,
        template="plotly_dark",
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["surface"],
        font=dict(family="Inter, system-ui, sans-serif", color=PALETTE["text"], size=11),
        margin=dict(l=40, r=80, t=24, b=12),
        hovermode="closest",
        xaxis_title="",
        yaxis_title="€ / month",
    )

    fig.update_xaxes(gridcolor=PALETTE["border"])
    fig.update_yaxes(gridcolor=PALETTE["border"])

    return fig


@callback(
    Output("scenario-log", "children"),
    Input("scenario-store", "data"),
    Input("scenario-table", "data"),
)
def update_assumption_log(store_data, table_data):
    """Generate markdown assumption log."""
    if not table_data or not store_data:
        return "📝 No adjustments yet. Edit the Scenario € column to make changes."

    changes = []
    for row in table_data:
        baseline = row["baseline"]
        scenario = row["scenario_amount"]
        delta = scenario - baseline

        if delta != 0:
            changes.append({
                "key": f"{row['type']}/{row['subtype']}",
                "from": baseline,
                "to": scenario,
                "delta": delta,
                "abs_delta": abs(delta),
            })

    if not changes:
        return "📝 No adjustments yet. Edit the Scenario € column to make changes."

    # Sort by absolute delta (largest changes first)
    changes.sort(key=lambda x: x["abs_delta"], reverse=True)

    total_delta = sum(c["delta"] for c in changes)
    annual_delta = total_delta * 12
    change_count = len(changes)

    log = f"**Scenario adjustments** — {change_count} changes · €{total_delta:+,.0f}/month · €{annual_delta:+,.0f}/year\n\n"

    for change in changes:
        sign = "↓" if change["delta"] < 0 else "↑"
        log += f"- {change['key']:25} €{change['from']:6.0f} → €{change['to']:6.0f}  ({sign} €{change['delta']:+.0f})\n"
    return log

