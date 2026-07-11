"""
Chart factory for the finance dashboard.
All chart creation logic isolated here for testability.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from finance_dashboard.config import CONFIG
from finance_dashboard.data_loader import COLS

# ── Color Palette (finance-appropriate: cool, precise) ─────────────────────
PALETTE = {
    "bg": "#171614",
    "surface": "#1C1B19",
    "surface_alt": "#201F1D",
    "border": "#393836",
    "text": "#CDCCCA",
    "text_muted": "#797876",
    "text_faint": "#5A5957",
    "primary": "#4F98A3",
    "primary_hover": "#227F8B",
    "error": "#D163A7",
    "warning": "#BB653B",
    "success": "#6DAA45",
}

# Category colors — ordered, muted, distinguishable
CATEGORY_COLORS = {
    "Car":        "#b71e1d",
    "Food":       "#20808D",
    "Recurring":  "#00bd8b",
    "Stuff":      "#7A3F52",  
    "Takeout":    "#D4884A",  
    "Travel+Fun": "#FFC553",
    "Unique":     "#6B7B8D",  
    "Income":     "#6DAA45",
    "Savings":    "#2D7A52", 
    "unknown":    "#B85CA0", 
}

PLOTLY_TEMPLATE = "plotly_dark"

CHART_LAYOUT_DEFAULTS = dict(
    template=PLOTLY_TEMPLATE,
    paper_bgcolor=PALETTE["bg"],
    plot_bgcolor=PALETTE["surface"],
    font=dict(family="Inter, system-ui, sans-serif", color=PALETTE["text"], size=12),
    margin=dict(l=48, r=24, t=36, b=24),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    ),
    colorway=list(CATEGORY_COLORS.values()),
)


def _apply_defaults(fig: go.Figure) -> go.Figure:
    """Apply consistent dark theme to any figure."""
    fig.update_layout(**CHART_LAYOUT_DEFAULTS)
    fig.update_xaxes(
        gridcolor=PALETTE["border"],
        zerolinecolor=PALETTE["border"],
    )
    fig.update_yaxes(
        gridcolor=PALETTE["border"],
        zerolinecolor=PALETTE["border"],
    )
    return fig


# ── Time Series: Monthly by Category ──────────────────────────────────────

def make_timeseries(
    costs_avg: pd.DataFrame,
    costs_raw: pd.DataFrame,
    timeline_months: int,
    selected_month: str,
) -> go.Figure:
    """
    Faceted area chart: smoothed spending per category over time.
    Dotted overlay shows raw monthly values.
    """
    plot_cols = [c for c in costs_avg.columns if c != "diff"]
    fig = px.area(
        costs_avg[plot_cols],
        facet_col="spending_type",
        facet_col_wrap=4,
        color_discrete_map=CATEGORY_COLORS,
    )
    fig.update_traces(line_shape="vh")

    # Time window
    if timeline_months and timeline_months > 0:
        max_dt = pd.Timestamp(selected_month) + pd.DateOffset(days=15)
        min_dt = pd.Timestamp(selected_month) - pd.DateOffset(months=int(timeline_months))
        fig.update_xaxes(range=[min_dt, max_dt], title="")

    timeseries_y_range = CONFIG["app"]["graphs"].get("timeseries_y_range", [-1500, 100])
    fig.update_yaxes(range=timeseries_y_range)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))

    # Raw values overlay (dotted)
    fig_raw = px.line(
        costs_raw.round(0)[plot_cols],
        facet_col="spending_type",
        facet_col_wrap=4,
        color_discrete_map=CATEGORY_COLORS,
    )
    fig_raw.update_traces(
        showlegend=False,
        line=dict(dash="dot", shape="vh", width=1),
        opacity=0.5,
    )
    fig.add_traces(fig_raw.data)

    _apply_defaults(fig)
    fig.update_layout(
        height=400,
        showlegend=False,
        margin=dict(l=48, r=12, t=48, b=12),
    )
    return fig


# ── Comparison Bar Chart ──────────────────────────────────────────────────

def make_comparison_bar(
    costs_mthly: pd.DataFrame,
    costs_avg: pd.DataFrame,
    costs_yearly: pd.DataFrame,
    selected_month: str,
) -> go.Figure:
    """
    Stacked bar: selected month vs. rolling average vs. yearly averages.
    Includes income + difference overlays.
    """
    month_before = pd.Timestamp(selected_month) - pd.DateOffset(months=1)

    combined = pd.concat([
        costs_yearly.tail(3),
        costs_avg.loc[costs_avg.index.strftime("%Y-%m") == month_before.strftime("%Y-%m")],
        costs_mthly.round(0).loc[costs_mthly.index.date == pd.Timestamp(selected_month).date()],
    ])

    if combined.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data for selected month", showarrow=False)
        return _apply_defaults(fig)

    labels = combined.index.year.astype(str).tolist()
    n_yearly = len(costs_yearly.tail(3))
    if len(labels) > n_yearly:
        labels[n_yearly] = "3m avg"
    if len(labels) > n_yearly + 1:
        labels[n_yearly + 1] = str(pd.Timestamp(selected_month).strftime("%b %Y"))
    combined.index = labels

    income = combined.pop("Income") if "Income" in combined.columns else pd.Series(dtype=float)
    diff = combined.pop("diff") if "diff" in combined.columns else pd.Series(dtype=float)

    # Main stacked bar
    fig = px.bar(
        -combined,
        color="spending_type",
        text_auto=True,
        color_discrete_map=CATEGORY_COLORS,
    )
    fig.update_traces(hovertemplate="%{y:.0f}€", width=0.55, textfont_size=10)

    # Income bar (thin, to the left)
    if not income.empty:
        fig.add_trace(go.Bar(
            x=income.index.tolist(),
            y=income.values,
            name="Income",
            offset=-0.45,
            base=0,
            width=0.15,
            marker_color="rgba(109, 170, 69, 0.7)",
            texttemplate="%{y:.0f}€",
            textposition="inside",
            textangle=270,
            textfont_size=10,
        ))

    # Difference bar
    if not diff.empty and not income.empty:
        fig.add_trace(go.Bar(
            x=diff.index.tolist(),
            y=diff.values,
            name="Balance",
            offset=-0.3,
            width=0.15,
            base=income.values - diff.values,
            marker_color=[
                "rgba(109, 170, 69, 0.5)" if v >= 0 else "rgba(209, 99, 167, 0.5)"
                for v in diff.values
            ],
            texttemplate="%{y:.0f}€",
            hovertemplate="%{y:.0f}€ balance",
            textposition="inside",
            textangle=270,
            textfont_size=10,
        ))

    _apply_defaults(fig)
    fig.update_layout(
        height=420,
        xaxis_title="",
        yaxis_title="€ / month",
        barmode="relative",
    )
    return fig


# ── Sunburst: Category Breakdown ─────────────────────────────────────────

def make_sunburst(costs_mthly_subtypes: pd.DataFrame) -> go.Figure:
    """Annual average spending as a sunburst chart (excl. Income)."""
    yearly_avg = costs_mthly_subtypes.resample("1YE").mean()
    # Drop Income category from multi-level columns (pandas 3.x compatible)
    if isinstance(yearly_avg.columns, pd.MultiIndex):
        keep = [c for c in yearly_avg.columns if c[0] != "Income"]
        yearly_avg = yearly_avg[keep].abs()
    else:
        yearly_avg = yearly_avg.drop(columns=["Income"], errors="ignore").abs()

    if yearly_avg.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False)
        return _apply_defaults(fig)

    last_year = yearly_avg.iloc[[-1]].round().T.reset_index()
    last_year.columns = [*last_year.columns[:-1], "value"]
    last_year = last_year[last_year["value"] > 0]

    fig = px.sunburst(
        last_year,
        path=["spending_type", "subtype"],
        values="value",
        color="spending_type",
        color_discrete_map=CATEGORY_COLORS,
    )

    _apply_defaults(fig)
    fig.update_layout(height=400, margin=dict(l=8, r=8, t=8, b=8))
    return fig


# ── Unknown Transactions Chart ────────────────────────────────────────────

def make_unknowns_bar(df_unknowns: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of top unknown recipients by total amount."""
    if df_unknowns.empty:
        fig = go.Figure()
        fig.add_annotation(text="All transactions mapped", showarrow=False)
        return _apply_defaults(fig)

    grouped = (
        df_unknowns.groupby(COLS["recipient"])[COLS["amount"]]
        .agg(["sum", "count"])
        .reset_index()
        .sort_values("sum")
        .head(20)
    )

    fig = go.Figure(go.Bar(
        y=grouped[COLS["recipient"]],
        x=grouped["sum"],
        orientation="h",
        marker_color=PALETTE["error"],
        text=grouped.apply(lambda r: f'{r["sum"]:.0f}€ ({r["count"]}x)', axis=1),
        textposition="auto",
        textfont_size=11,
    ))

    _apply_defaults(fig)
    fig.update_layout(
        height=max(300, len(grouped) * 28),
        xaxis_title="Total €",
        yaxis_title="",
        margin=dict(l=200, r=24, t=12, b=24),
    )
    return fig


# ── KPI helpers ───────────────────────────────────────────────────────────

def calc_diff(row: pd.Series) -> float:
    """Monthly balance: income - all spending (excl. savings transfers)."""
    savings = row.get("Savings", 0)
    return row.sum() - savings
