import os
import pandas as pd
import numpy as np
import dash
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# App 04 - Factory Digital Twin / Production Control Prototype
# Uses only Production_Orders.csv and Machine_Downtime.csv.
# Note: no machine-to-line mapping is available, so downtime
# analytics are intentionally kept separate from line filters.
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROD_PATH = os.path.join(BASE_DIR, "Production_Orders.csv")
DOWN_PATH = os.path.join(BASE_DIR, "Machine_Downtime.csv")

COLORS = {
    "cyan": "#45d7ff",
    "green": "#42e6b5",
    "amber": "#ffb703",
    "red": "#ff5c7c",
    "muted": "#7f9bb5",
    "panel": "rgba(8, 27, 48, 0.88)",
    "bg": "rgba(0,0,0,0)",
}


def require_columns(df, required, dataset_name):
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(
            f"{dataset_name} is missing required columns: {', '.join(missing)}"
        )


def numeric_columns(df, columns):
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_data():
    if not os.path.exists(PROD_PATH):
        raise FileNotFoundError(f"Required file not found: {PROD_PATH}")
    if not os.path.exists(DOWN_PATH):
        raise FileNotFoundError(f"Required file not found: {DOWN_PATH}")

    prod = pd.read_csv(PROD_PATH)
    down = pd.read_csv(DOWN_PATH)
    prod.columns = prod.columns.str.strip()
    down.columns = down.columns.str.strip()

    require_columns(
        prod,
        [
            "Production_Order_ID", "Product_ID", "Product_Name", "Start_Date",
            "Due_Date", "Completion_Date", "Planned_Qty", "Produced_Qty",
            "Good_Qty", "Rejected_Qty", "Line_ID", "Efficiency_Pct",
            "Delay_Days", "Primary_Bottleneck", "Overtime_Hours"
        ],
        "Production_Orders.csv",
    )
    require_columns(
        down,
        ["Downtime_ID", "Date", "Machine_ID", "Business_Area",
         "Downtime_Hours", "Reason", "Planned"],
        "Machine_Downtime.csv",
    )

    prod = numeric_columns(
        prod,
        ["Planned_Qty", "Produced_Qty", "Good_Qty", "Rejected_Qty",
         "Efficiency_Pct", "Delay_Days", "Overtime_Hours"],
    )
    down = numeric_columns(down, ["Downtime_Hours"])

    for col in ["Start_Date", "Due_Date", "Completion_Date"]:
        prod[col] = pd.to_datetime(prod[col], errors="coerce")
    down["Date"] = pd.to_datetime(down["Date"], errors="coerce")

    # Preserve missing bottlenecks as an explicit category rather than silently
    # dropping them from groupby-based charts.
    prod["Primary_Bottleneck"] = (
        prod["Primary_Bottleneck"].fillna("Unspecified").astype(str).str.strip()
    )
    prod.loc[prod["Primary_Bottleneck"].eq(""), "Primary_Bottleneck"] = "Unspecified"

    for col in ["Line_ID", "Production_Order_ID", "Product_Name"]:
        prod[col] = prod[col].fillna("Unknown").astype(str)
    for col in ["Reason", "Machine_ID", "Business_Area", "Planned"]:
        down[col] = down[col].fillna("Unknown").astype(str)

    # Data quality flags. Do not silently convert invalid quantities into zero.
    prod["Quantity_Check"] = np.where(
        prod[["Planned_Qty", "Produced_Qty", "Good_Qty", "Rejected_Qty"]].isna().any(axis=1),
        "Missing quantity",
        np.where(
            (prod[["Planned_Qty", "Produced_Qty", "Good_Qty", "Rejected_Qty"]] < 0).any(axis=1),
            "Negative quantity",
            np.where(
                (prod["Good_Qty"] + prod["Rejected_Qty"] != prod["Produced_Qty"]),
                "Produced != Good + Rejected",
                "OK",
            ),
        ),
    )

    # Use provided Delay_Days where valid; otherwise calculate from due/completion dates.
    calculated_delay = (prod["Completion_Date"] - prod["Due_Date"]).dt.days
    calculated_delay = calculated_delay.clip(lower=0)
    prod["Delay_Days_Used"] = prod["Delay_Days"].where(
        prod["Delay_Days"].notna(), calculated_delay
    ).clip(lower=0)

    prod["Delivery_Status"] = np.select(
        [
            prod["Completion_Date"].isna(),
            prod["Delay_Days_Used"].fillna(0) > 0,
        ],
        ["Completion date missing", "Late"],
        default="On time",
    )

    # Status thresholds are configurable business rules, not facts from source data.
    reject_rate = prod["Rejected_Qty"].div(prod["Produced_Qty"].replace(0, np.nan))
    prod["Reject_Rate_Pct"] = (reject_rate * 100).fillna(0)
    prod["Production_Status"] = np.select(
        [
            (prod["Efficiency_Pct"] < 70) | (prod["Reject_Rate_Pct"] > 10),
            prod["Efficiency_Pct"] < 85,
        ],
        ["CRITICAL BOTTLENECK", "MODERATE LOSS"],
        default="OPTIMAL FLOW",
    )

    down["Downtime_Class"] = np.where(
        down["Planned"].str.strip().str.lower().isin(["yes", "y", "true", "1"]),
        "Planned",
        np.where(
            down["Planned"].str.strip().str.lower().isin(["no", "n", "false", "0"]),
            "Unplanned",
            "Unknown",
        ),
    )

    return prod, down


df_prod, df_down = load_data()

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "App 04 - Factory Production Control (Final Review)"


def panel(children, **kwargs):
    return dbc.Card(
        dbc.CardBody(children),
        style={
            "background": COLORS["panel"],
            "border": "1px solid rgba(49, 164, 226, 0.3)",
            "height": "100%",
        },
        **kwargs,
    )


def empty_figure(message="No data available for the selected filters."):
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font={"color": "#a9c0d5", "size": 14},
    )
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"], margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


app.layout = html.Div(
    style={
        "background": "linear-gradient(145deg, #020812 0%, #041324 48%, #020914 100%)",
        "minHeight": "100vh", "padding": "clamp(10px, 2vw, 24px)", "color": "#eef7ff",
        "fontFamily": "Segoe UI, sans-serif", "width": "100%",
        "maxWidth": "100vw", "boxSizing": "border-box", "overflowX": "hidden",
    },
    children=[
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(
                            "PRODUCTION CONTROL ENGINE • APP 04",
                            style={"color": COLORS["cyan"], "letterSpacing": "2px",
                                   "fontSize": "12px", "fontWeight": "bold"},
                        ),
                        html.H2(
                            "FACTORY DIGITAL TWIN & PRODUCTION CONTROL",
                            style={"fontWeight": "800", "color": "#ffffff"},
                        ),
                        html.P(
                            "Where is throughput lost before delivery?",
                            style={"color": COLORS["muted"], "fontSize": "15px"},
                        ),
                        html.P(
                            "Analytical prototype • downtime is not linked to individual lines "
                            "because no machine-to-line mapping was supplied.",
                            style={"color": "#a9c0d5", "fontSize": "12px"},
                        ),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        dbc.Button(
                            "Download Filtered Production Plan (CSV)",
                            id="btn-download-prod-csv", color="info",
                            className="float-md-end mt-2", style={"fontWeight": "bold"},
                        ),
                        dcc.Download(id="download-prod-csv"),
                    ],
                    md=4,
                ),
            ],
            className="mb-4",
        ),

        dbc.Row(id="kpi-cards", className="g-3 mb-4"),

        panel(
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Production Line", style={"color": COLORS["green"]}),
                            dcc.Dropdown(
                                id="filter-line",
                                options=[{"label": "All Production Lines", "value": "All"}]
                                + [{"label": x, "value": x} for x in sorted(df_prod["Line_ID"].unique())],
                                value="All", clearable=False, style={"color": "#000"},
                            ),
                        ],
                        md=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Primary Bottleneck", style={"color": COLORS["green"]}),
                            dcc.Dropdown(
                                id="filter-bottleneck",
                                options=[{"label": "All Bottlenecks", "value": "All"}]
                                + [{"label": x, "value": x} for x in sorted(df_prod["Primary_Bottleneck"].unique())],
                                value="All", clearable=False, style={"color": "#000"},
                            ),
                        ],
                        md=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Production Status", style={"color": COLORS["green"]}),
                            dcc.Dropdown(
                                id="filter-status",
                                options=[{"label": "All Statuses", "value": "All"}]
                                + [{"label": x, "value": x} for x in
                                   ["CRITICAL BOTTLENECK", "MODERATE LOSS", "OPTIMAL FLOW"]],
                                value="All", clearable=False, style={"color": "#000"},
                            ),
                        ],
                        md=4,
                    ),
                ],
                className="g-3",
            ),
            className="mb-4",
        ),

        dbc.Row(
            [
                dbc.Col(panel([
                    html.H6("A. Production Flow: Planned vs Produced vs Good",
                            style={"color": COLORS["cyan"]}),
                    dcc.Graph(id="chart-production-flow", style={"height": "310px"}),
                ]), md=6, className="mb-3"),
                dbc.Col(panel([
                    html.H6("B. Orders by Recorded Primary Bottleneck",
                            style={"color": COLORS["red"]}),
                    html.P("Count of affected orders, not lost hours.",
                           style={"fontSize": "11px", "color": COLORS["muted"]}),
                    dcc.Graph(id="chart-bottleneck-breakdown", style={"height": "280px"}),
                ]), md=6, className="mb-3"),
            ],
            className="g-3",
        ),

        dbc.Row(
            [
                dbc.Col(panel([
                    html.H6("C. Rejected Units by Production Line",
                            style={"color": COLORS["cyan"]}),
                    dcc.Graph(id="chart-line-rejects", style={"height": "300px"}),
                ]), md=6, className="mb-3"),
                dbc.Col(panel([
                    html.H6("D. Equipment Downtime by Reason (All Records)",
                            style={"color": COLORS["amber"]}),
                    html.P("Independent of production-line filters: no machine-to-line mapping is available.",
                           style={"fontSize": "11px", "color": COLORS["muted"]}),
                    dcc.Graph(id="chart-downtime-reasons", style={"height": "300px"}),
                ]), md=6, className="mb-3"),
            ],
            className="g-3",
        ),

        dbc.Row(
            [
                dbc.Col(panel([
                    html.H6("E. Delivery Performance", style={"color": COLORS["cyan"]}),
                    dcc.Graph(id="chart-delivery", style={"height": "300px"}),
                ]), md=6, className="mb-3"),
                dbc.Col(panel([
                    html.H6("F. Planned vs Unplanned Downtime",
                            style={"color": COLORS["amber"]}),
                    dcc.Graph(id="chart-downtime-class", style={"height": "300px"}),
                ]), md=6, className="mb-3"),
            ],
            className="g-3",
        ),

        dbc.Row([
            dbc.Col(panel([
                html.H5("G. Line Performance & Review Priorities",
                        style={"color": COLORS["green"], "fontWeight": "bold"}),
                html.P(
                    "Priority labels are rule-based review suggestions, not proof of root cause. "
                    "Rates are recalculated for the selected filters.",
                    style={"color": COLORS["muted"], "fontSize": "12px"},
                ),
                dash_table.DataTable(
                    id="table-line-performance",
                    columns=[
                        {"name": "Line", "id": "Line_ID"},
                        {"name": "Orders", "id": "Orders", "type": "numeric"},
                        {"name": "Avg Efficiency %", "id": "Avg_Efficiency_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Reject Rate %", "id": "Reject_Rate_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Plan Attainment %", "id": "Plan_Attainment_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Late Orders", "id": "Late_Orders", "type": "numeric"},
                        {"name": "Delay Rate %", "id": "Delay_Rate_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Review Priority", "id": "Review_Priority"},
                        {"name": "Review Reason", "id": "Review_Reason"},
                    ],
                    page_size=5,
                    sort_action="native",
                    style_table={"overflowX": "auto", "width": "100%"},
                    style_header={
                        "backgroundColor": "#041324", "color": COLORS["cyan"],
                        "fontWeight": "bold", "border": "1px solid rgba(49, 164, 226, 0.3)",
                    },
                    style_cell={
                        "backgroundColor": "#081b30", "color": "#eef7ff",
                        "border": "1px solid rgba(49, 164, 226, 0.1)",
                        "textAlign": "left", "padding": "8px",
                        "minWidth": "78px", "maxWidth": "220px",
                        "whiteSpace": "normal", "height": "auto",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": '{Review_Priority} = "High"'}, "color": COLORS["red"]},
                        {"if": {"filter_query": '{Review_Priority} = "Medium"'}, "color": COLORS["amber"]},
                        {"if": {"filter_query": '{Review_Priority} = "Review"'}, "color": COLORS["amber"]},
                    ],
                ),
            ]), md=12, className="mb-3")
        ]),

        dbc.Row([
            dbc.Col(panel([
                html.H5("Production Orders & Recommended Review Actions",
                        style={"color": COLORS["green"], "fontWeight": "bold"}),
                html.P(
                    "Status thresholds (<70% efficiency, >10% reject rate) are provisional "
                    "rules and should be confirmed by the business.",
                    style={"color": COLORS["muted"], "fontSize": "12px"},
                ),
                dash_table.DataTable(
                    id="table-production",
                    columns=[
                        {"name": "Order ID", "id": "Production_Order_ID"},
                        {"name": "Line", "id": "Line_ID"},
                        {"name": "Product", "id": "Product_Name"},
                        {"name": "Planned", "id": "Planned_Qty", "type": "numeric"},
                        {"name": "Produced", "id": "Produced_Qty", "type": "numeric"},
                        {"name": "Good", "id": "Good_Qty", "type": "numeric"},
                        {"name": "Rejected", "id": "Rejected_Qty", "type": "numeric"},
                        {"name": "Efficiency %", "id": "Efficiency_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Reject Rate %", "id": "Reject_Rate_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "Bottleneck", "id": "Primary_Bottleneck"},
                        {"name": "Status", "id": "Production_Status"},
                        {"name": "Delivery", "id": "Delivery_Status"},
                        {"name": "Delay Days", "id": "Delay_Days_Used", "type": "numeric"},
                        {"name": "Data Check", "id": "Quantity_Check"},
                    ],
                    page_size=12,
                    sort_action="native",
                    filter_action="native",
                    export_format="csv",
                    style_table={"overflowX": "auto", "width": "100%"},
                    style_header={
                        "backgroundColor": "#041324", "color": COLORS["cyan"],
                        "fontWeight": "bold", "border": "1px solid rgba(49, 164, 226, 0.3)",
                    },
                    style_cell={
                        "backgroundColor": "#081b30", "color": "#eef7ff",
                        "border": "1px solid rgba(49, 164, 226, 0.1)",
                        "textAlign": "left", "padding": "8px",
                        "minWidth": "95px", "maxWidth": "240px",
                        "whiteSpace": "normal", "height": "auto",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": '{Production_Status} = "CRITICAL BOTTLENECK"'},
                         "color": COLORS["red"]},
                        {"if": {"filter_query": '{Production_Status} = "MODERATE LOSS"'},
                         "color": COLORS["amber"]},
                        {"if": {"filter_query": '{Delivery_Status} = "Late"'},
                         "backgroundColor": "rgba(255, 92, 124, 0.12)"},
                        {"if": {"filter_query": '{Quantity_Check} != "OK"'},
                         "backgroundColor": "rgba(255, 183, 3, 0.16)"},
                    ],
                ),
            ]), md=12)
        ]),
        html.P(
            "Data class in source files indicates modeled/synthetic factory records. "
            "Treat findings as a prototype analysis, not verified real-world factory performance.",
            style={"color": COLORS["muted"], "fontSize": "11px", "marginTop": "14px"},
        ),
    ],
)


def filtered_production(line_filter, bottleneck_filter, status_filter):
    f = df_prod.copy()
    if line_filter != "All":
        f = f[f["Line_ID"] == line_filter]
    if bottleneck_filter != "All":
        f = f[f["Primary_Bottleneck"] == bottleneck_filter]
    if status_filter != "All":
        f = f[f["Production_Status"] == status_filter]
    return f


def make_kpi(title, value, subtitle):
    return dbc.Col(
        panel([
            html.Div(title, style={"color": COLORS["muted"], "fontSize": "12px"}),
            html.H3(value, style={"color": "#ffffff", "fontWeight": "800", "margin": "6px 0"}),
            html.Div(subtitle, style={"color": COLORS["muted"], "fontSize": "11px"}),
        ]),
        xs=12, sm=6, lg=3,
    )


@app.callback(
    [
        Output("kpi-cards", "children"),
        Output("chart-production-flow", "figure"),
        Output("chart-bottleneck-breakdown", "figure"),
        Output("chart-line-rejects", "figure"),
        Output("chart-downtime-reasons", "figure"),
        Output("chart-delivery", "figure"),
        Output("chart-downtime-class", "figure"),
        Output("table-production", "data"),
        Output("table-line-performance", "data"),
    ],
    [
        Input("filter-line", "value"),
        Input("filter-bottleneck", "value"),
        Input("filter-status", "value"),
    ],
)
def update_dashboard(line_filter, bottleneck_filter, status_filter):
    f = filtered_production(line_filter, bottleneck_filter, status_filter)

    if f.empty:
        fig_empty = empty_figure()
        return [], fig_empty, fig_empty, fig_empty, fig_empty, fig_empty, fig_empty, [], []

    planned = f["Planned_Qty"].sum(min_count=1)
    produced = f["Produced_Qty"].sum(min_count=1)
    good = f["Good_Qty"].sum(min_count=1)
    rejected = f["Rejected_Qty"].sum(min_count=1)
    late_orders = int((f["Delivery_Status"] == "Late").sum())
    mean_eff = f["Efficiency_Pct"].mean()
    reject_rate_total = (rejected / produced * 100) if pd.notna(produced) and produced else 0
    bottleneck_count = int((f["Primary_Bottleneck"] != "Unspecified").sum())
    kpis = [
        make_kpi("Planned Units", f"{planned:,.0f}" if pd.notna(planned) else "N/A", "Filtered production orders"),
        make_kpi("Good Units", f"{good:,.0f}" if pd.notna(good) else "N/A", "Accepted output"),
        make_kpi("Avg. Order Efficiency", f"{mean_eff:.1f}%" if pd.notna(mean_eff) else "N/A", "Simple mean across filtered orders"),
        make_kpi("Late Orders", f"{late_orders:,}", f"Out of {len(f):,} filtered orders"),
    ]

    flow = f.groupby("Line_ID", as_index=False)[
        ["Planned_Qty", "Produced_Qty", "Good_Qty"]
    ].sum()
    fig_a = px.bar(
        flow, x="Line_ID", y=["Planned_Qty", "Produced_Qty", "Good_Qty"],
        barmode="group", template="plotly_dark",
        labels={"value": "Units", "variable": "Measure", "Line_ID": "Production Line"},
        color_discrete_map={
            "Planned_Qty": "#009dff", "Produced_Qty": COLORS["amber"],
            "Good_Qty": COLORS["green"],
        },
    )
    fig_a.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                        margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")

    bottle = f.groupby("Primary_Bottleneck", as_index=False).agg(
        Affected_Orders=("Production_Order_ID", "nunique")
    ).sort_values("Affected_Orders", ascending=True)
    fig_b = px.bar(
        bottle, x="Affected_Orders", y="Primary_Bottleneck", orientation="h",
        text="Affected_Orders", template="plotly_dark",
        labels={"Affected_Orders": "Affected orders", "Primary_Bottleneck": "Recorded bottleneck"},
        color_discrete_sequence=[COLORS["red"]],
    )
    fig_b.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                        margin=dict(l=10, r=10, t=10, b=10))

    rejects = f.groupby("Line_ID", as_index=False).agg(
        Rejected_Qty=("Rejected_Qty", "sum"),
        Produced_Qty=("Produced_Qty", "sum"),
    )
    rejects["Reject_Rate_Pct"] = np.where(
        rejects["Produced_Qty"] > 0,
        rejects["Rejected_Qty"] / rejects["Produced_Qty"] * 100,
        0,
    )
    fig_c = px.bar(
        rejects, x="Line_ID", y="Rejected_Qty", text="Rejected_Qty",
        hover_data={"Reject_Rate_Pct": ":.2f"},
        template="plotly_dark", color_discrete_sequence=[COLORS["red"]],
        labels={"Rejected_Qty": "Rejected units", "Line_ID": "Production line"},
    )
    fig_c.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                        margin=dict(l=10, r=10, t=10, b=10))

    # Equipment downtime is deliberately not filtered by production line/bottleneck/status:
    # source data does not provide a documented machine-to-line key.
    down_reason = df_down.groupby("Reason", as_index=False)["Downtime_Hours"].sum()
    if down_reason.empty:
        fig_d = empty_figure("No downtime records available.")
    else:
        fig_d = px.bar(
            down_reason.sort_values("Downtime_Hours", ascending=True),
            x="Downtime_Hours", y="Reason", orientation="h", text="Downtime_Hours",
            template="plotly_dark", color_discrete_sequence=[COLORS["amber"]],
            labels={"Downtime_Hours": "Downtime hours", "Reason": "Recorded reason"},
        )
        fig_d.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                            margin=dict(l=10, r=10, t=10, b=10))

    delivery = f["Delivery_Status"].value_counts().rename_axis("Delivery_Status").reset_index(name="Orders")
    fig_e = px.bar(
        delivery, x="Delivery_Status", y="Orders", text="Orders",
        template="plotly_dark", color="Delivery_Status",
        color_discrete_map={"Late": COLORS["red"], "On time": COLORS["green"],
                            "Completion date missing": COLORS["amber"]},
        labels={"Delivery_Status": "Delivery status", "Orders": "Orders"},
    )
    fig_e.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                        showlegend=False, margin=dict(l=10, r=10, t=10, b=10))

    down_class = df_down.groupby("Downtime_Class", as_index=False)["Downtime_Hours"].sum()
    fig_f = px.bar(
        down_class, x="Downtime_Class", y="Downtime_Hours", text="Downtime_Hours",
        template="plotly_dark",
        color="Downtime_Class",
        color_discrete_map={"Planned": COLORS["cyan"], "Unplanned": COLORS["red"], "Unknown": COLORS["amber"]},
        labels={"Downtime_Class": "Downtime classification", "Downtime_Hours": "Downtime hours"},
    )
    fig_f.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                        showlegend=False, margin=dict(l=10, r=10, t=10, b=10))

    # Line-level operational metrics: aggregate counts and rates from filtered orders.
    line_perf = f.groupby("Line_ID", as_index=False).agg(
        Orders=("Production_Order_ID", "nunique"),
        Avg_Efficiency_Pct=("Efficiency_Pct", "mean"),
        Planned_Qty=("Planned_Qty", "sum"),
        Produced_Qty=("Produced_Qty", "sum"),
        Rejected_Qty=("Rejected_Qty", "sum"),
        Late_Orders=("Delivery_Status", lambda x: int((x == "Late").sum())),
    )
    line_perf["Reject_Rate_Pct"] = np.where(
        line_perf["Produced_Qty"] > 0,
        line_perf["Rejected_Qty"] / line_perf["Produced_Qty"] * 100, np.nan,
    )
    line_perf["Plan_Attainment_Pct"] = np.where(
        line_perf["Planned_Qty"] > 0,
        line_perf["Produced_Qty"] / line_perf["Planned_Qty"] * 100, np.nan,
    )
    line_perf["Delay_Rate_Pct"] = np.where(
        line_perf["Orders"] > 0, line_perf["Late_Orders"] / line_perf["Orders"] * 100, np.nan,
    )

    # Transparent peer-comparison triage. When only one line remains after filters,
    # avoid labelling it as the best/worst against itself.
    priorities, reasons = [], []
    if len(line_perf) < 2:
        for _, row in line_perf.iterrows():
            priorities.append("Review")
            reasons.append("Peer comparison unavailable: select All Production Lines to compare lines")
    else:
        max_delay = line_perf["Delay_Rate_Pct"].max()
        min_eff = line_perf["Avg_Efficiency_Pct"].min()
        max_reject = line_perf["Reject_Rate_Pct"].max()
        for _, row in line_perf.iterrows():
            reason_parts = []
            if pd.notna(row["Delay_Rate_Pct"]) and row["Delay_Rate_Pct"] == max_delay and row["Late_Orders"] > 0:
                reason_parts.append("Highest delay rate in current selection")
            if pd.notna(row["Avg_Efficiency_Pct"]) and row["Avg_Efficiency_Pct"] == min_eff:
                reason_parts.append("Lowest average efficiency in current selection")
            if pd.notna(row["Reject_Rate_Pct"]) and row["Reject_Rate_Pct"] == max_reject:
                reason_parts.append("Highest reject rate in current selection")
            reasons.append("; ".join(reason_parts) if reason_parts else "Monitor against peer lines")
            priorities.append("High" if len(reason_parts) >= 2 else ("Medium" if reason_parts else "Monitor"))
    line_perf["Review_Priority"] = priorities
    line_perf["Review_Reason"] = reasons
    line_perf = line_perf.sort_values(
        ["Review_Priority", "Delay_Rate_Pct"], ascending=[True, False]
    )
    priority_order = {"High": 0, "Medium": 1, "Monitor": 2}
    line_perf["_priority_sort"] = line_perf["Review_Priority"].map(priority_order)
    line_perf = line_perf.sort_values(["_priority_sort", "Delay_Rate_Pct"], ascending=[True, False])
    line_perf_data = line_perf[[
        "Line_ID", "Orders", "Avg_Efficiency_Pct", "Reject_Rate_Pct",
        "Plan_Attainment_Pct", "Late_Orders", "Delay_Rate_Pct",
        "Review_Priority", "Review_Reason",
    ]].replace({np.nan: None}).to_dict("records")

    table_cols = [
        "Production_Order_ID", "Line_ID", "Product_Name", "Planned_Qty", "Produced_Qty",
        "Good_Qty", "Rejected_Qty", "Efficiency_Pct", "Reject_Rate_Pct",
        "Primary_Bottleneck", "Production_Status", "Delivery_Status",
        "Delay_Days_Used", "Quantity_Check",
    ]
    table_data = f[table_cols].replace({np.nan: None}).to_dict("records")
    return kpis, fig_a, fig_b, fig_c, fig_d, fig_e, fig_f, table_data, line_perf_data


@app.callback(
    Output("download-prod-csv", "data"),
    Input("btn-download-prod-csv", "n_clicks"),
    State("filter-line", "value"),
    State("filter-bottleneck", "value"),
    State("filter-status", "value"),
    prevent_initial_call=True,
)
def export_production_csv(n_clicks, line_filter, bottleneck_filter, status_filter):
    f = filtered_production(line_filter, bottleneck_filter, status_filter).copy()
    return dcc.send_data_frame(f.to_csv, "Factory_Production_Action_Plan.csv", index=False)


if __name__ == "__main__":
    app.run(debug=False, port=8054)
