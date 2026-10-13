"""
App 05 — Marketing Attribution & Growth Analytics
Run from the folder containing this file and the CSV files:
    python app5_improved.py

Required: Marketing.csv
Optional: Web_Traffic_Daily.csv, Sales_Transactions.csv
Install dependencies:
    pip install dash dash-bootstrap-components pandas numpy plotly
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE_DIR = Path(__file__).resolve().parent
MARKETING_FILE = BASE_DIR / "Marketing.csv"
WEB_FILE = BASE_DIR / "Web_Traffic_Daily.csv"
SALES_FILE = BASE_DIR / "Sales_Transactions.csv"

REQUIRED_MARKETING = [
    "Campaign_ID", "Campaign_Name", "Product_ID", "Product_Name", "Platform",
    "Start_Date", "End_Date", "Spend_EGP", "Impressions", "Clicks",
    "Landing_Page_Sessions", "Orders_Attributed", "Attributed_Revenue_EGP"
]
NUMERIC_MARKETING = [
    "Spend_EGP", "Impressions", "Clicks", "Landing_Page_Sessions",
    "Orders_Attributed", "Attributed_Revenue_EGP"
]
BG = "#06111f"
CARD = "#0b1b2c"
CYAN = "#45d7ff"
MINT = "#42e6b5"
MUTED = "#9ab0c5"
TEXT = "#eef7ff"
PINK = "#ff6685"
GOLD = "#ffbf69"


def read_csv(path, required=None, label="CSV"):
    if not path.exists():
        return None, f"{label} not found: {path.name}"
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.astype(str).str.strip()
    except Exception as exc:
        return None, f"Could not read {path.name}: {exc}"
    missing = [c for c in (required or []) if c not in df.columns]
    if missing:
        return None, f"{path.name} is missing required columns: {', '.join(missing)}"
    return df, None


def numeric_clean(df, columns):
    """Coerce numeric values but retain an issue count; don't silently hide them."""
    issues = {}
    for col in columns:
        raw = df[col]
        parsed = pd.to_numeric(raw, errors="coerce")
        invalid = int((raw.notna() & parsed.isna()).sum())
        missing = int(raw.isna().sum())
        issues[col] = {"missing": missing, "non_numeric": invalid}
        df[col] = parsed
    return issues


def load_marketing():
    df, err = read_csv(MARKETING_FILE, REQUIRED_MARKETING, "Marketing data")
    if err:
        raise RuntimeError(err)
    issues = numeric_clean(df, NUMERIC_MARKETING)
    df["Start_Date"] = pd.to_datetime(df["Start_Date"], errors="coerce")
    df["End_Date"] = pd.to_datetime(df["End_Date"], errors="coerce")
    df["Platform"] = df["Platform"].fillna("Unknown").astype(str)
    df["Campaign_Name"] = df["Campaign_Name"].fillna("Unnamed campaign").astype(str)
    df["Product_ID"] = df["Product_ID"].fillna("Unknown").astype(str)
    df["Product_Name"] = df["Product_Name"].fillna("Unknown").astype(str)

    # Invalid/missing numeric cells remain NaN for audit and are excluded from sums.
    df["ROAS"] = np.where(df["Spend_EGP"] > 0,
                          df["Attributed_Revenue_EGP"] / df["Spend_EGP"], np.nan)
    df["CPA_EGP"] = np.where(df["Orders_Attributed"] > 0,
                             df["Spend_EGP"] / df["Orders_Attributed"], np.nan)
    df["CTR_Pct"] = np.where(df["Impressions"] > 0,
                             100 * df["Clicks"] / df["Impressions"], np.nan)
    df["Session_to_Order_Pct"] = np.where(df["Landing_Page_Sessions"] > 0,
                             100 * df["Orders_Attributed"] / df["Landing_Page_Sessions"], np.nan)
    df["Campaign_Status"] = np.select(
        [df["ROAS"] >= 5, df["ROAS"] >= 2],
        ["High ROAS (review)", "Moderate ROAS (review)"],
        default="Low ROAS (review)"
    )
    # This is only a descriptive ROAS band, never a profit verdict.
    df.loc[df["ROAS"].isna(), "Campaign_Status"] = "Not calculable"
    quality = {
        "rows": len(df),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_campaign_ids": int(df["Campaign_ID"].duplicated().sum()),
        "bad_date_rows": int((df["Start_Date"].isna() | df["End_Date"].isna()).sum()),
        "end_before_start": int((df["End_Date"] < df["Start_Date"]).sum()),
        "negative_numeric_cells": int(sum((df[c] < 0).sum() for c in NUMERIC_MARKETING)),
        "clicks_equal_sessions_rows": int((df["Clicks"] == df["Landing_Page_Sessions"]).sum()),
        "numeric_issues": issues,
    }
    return df, quality


def load_optional(path, required, label):
    return read_csv(path, required, label)


mkt, mkt_quality = load_marketing()
web, web_error = load_optional(
    WEB_FILE,
    ["Date", "Sessions", "Users", "Orders", "Conversion_Rate", "Avg_Page_Load_Sec"],
    "Website traffic data"
)
if web is not None:
    web["Date"] = pd.to_datetime(web["Date"], errors="coerce")
    for c in ["Sessions", "Users", "Orders", "Conversion_Rate", "Avg_Page_Load_Sec",
              "New_User_Pct", "Mobile_Pct", "Add_To_Cart_Rate", "Checkout_Rate"]:
        if c in web.columns:
            web[c] = pd.to_numeric(web[c], errors="coerce")
    web = web.dropna(subset=["Date"]).sort_values("Date")

sales, sales_error = load_optional(
    SALES_FILE,
    ["Order_Date", "Net_Sales_EGP", "Gross_Profit_EGP", "Returned"],
    "Sales transactions data"
)
if sales is not None:
    sales["Order_Date"] = pd.to_datetime(sales["Order_Date"], errors="coerce")
    for c in ["Net_Sales_EGP", "Gross_Profit_EGP", "Refund_Value_EGP", "Estimated_COGS_EGP"]:
        if c in sales.columns:
            sales[c] = pd.to_numeric(sales[c], errors="coerce")
    if "Returned" in sales.columns:
        sales["Returned"] = sales["Returned"].astype(str).str.strip().str.lower()

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "App 05 | Marketing Attribution & Growth Analytics"

def money(x):
    return f"EGP {x:,.0f}" if pd.notna(x) else "N/A"

def card_kpi(label, value_id, color=CYAN, note=None):
    children = [
        html.Div(label, style={"fontSize": "11px", "color": MUTED, "fontWeight": "700", "letterSpacing": "0.5px"}),
        html.H3(id=value_id, style={"color": color, "fontWeight": "800", "margin": "7px 0 0"})
    ]
    if note:
        children.append(html.Small(note, style={"color": MUTED}))
    return dbc.Card(dbc.CardBody(children), style={
        "background": CARD, "border": "1px solid #19354c", "borderRadius": "12px", "height": "100%"
    })

def chart_layout(fig, height=320):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=TEXT,
        margin=dict(l=15, r=15, t=35, b=35), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    return fig

def empty_fig(message):
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(color=MUTED, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return chart_layout(fig)

platform_options = [{"label": "All platforms", "value": "All"}] + [
    {"label": p, "value": p} for p in sorted(mkt["Platform"].dropna().unique())
]
product_values = sorted(mkt["Product_ID"].dropna().astype(str).unique())
product_options = [{"label": "All products", "value": "All"}] + [
    {"label": f"{pid} — {name}", "value": pid}
    for pid, name in mkt[["Product_ID", "Product_Name"]].drop_duplicates().sort_values("Product_ID").itertuples(index=False, name=None)
]
status_options = [{"label": "All ROAS bands", "value": "All"}] + [
    {"label": x, "value": x} for x in sorted(mkt["Campaign_Status"].unique())
]
min_date = mkt["Start_Date"].min()
max_date = mkt["End_Date"].max()
date_min = min_date.date().isoformat() if pd.notna(min_date) else "2023-01-01"
date_max = max_date.date().isoformat() if pd.notna(max_date) else "2026-12-31"

app.layout = html.Div(style={
    "background": f"linear-gradient(145deg, #020812 0%, {BG} 60%, #020914 100%)",
    "minHeight": "100vh", "padding": "24px", "color": TEXT,
    "fontFamily": "Segoe UI, Arial, sans-serif"
}, children=[
    dbc.Container(fluid=True, children=[
        dbc.Row([
            dbc.Col([
                html.Div("SHARNOUBy ENTERPRISE • APP 05", style={"color": CYAN, "fontSize": "12px", "fontWeight": "bold", "letterSpacing": "2px"}),
                html.H2("Marketing Attribution & Growth Analytics", style={"fontWeight": "800", "marginTop": "8px"}),
                html.P("Which spend creates profitable customers? — Evidence-led view, not an automatic budget decision.",
                       style={"color": MUTED, "marginBottom": "0"})
            ], md=9),
            dbc.Col([
                dbc.Button("Export filtered campaigns CSV", id="btn-export", color="info", className="mt-3", n_clicks=0),
                dcc.Download(id="download-csv")
            ], md=3, className="text-md-end")
        ], className="mb-4 align-items-center"),
        dbc.Alert([
            html.Strong("Interpretation note: "),
            "ROAS measures attributed revenue / marketing spend, not profit. Campaign data is modeled training data. ",
            "Do not treat ROAS bands as validated recommendations or merge attributed revenue with transaction sales."
        ], color="warning", className="mb-4"),
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col([html.Label("Platform", style={"color": MINT}), dcc.Dropdown(id="filter-platform", options=platform_options, value="All", clearable=False)], md=3),
                dbc.Col([html.Label("Product", style={"color": MINT}), dcc.Dropdown(id="filter-product", options=product_options, value="All", clearable=False)], md=3),
                dbc.Col([html.Label("ROAS band (descriptive)", style={"color": MINT}), dcc.Dropdown(id="filter-status", options=status_options, value="All", clearable=False)], md=3),
                dbc.Col([html.Label("Campaign date overlap", style={"color": MINT}),
                         dcc.DatePickerRange(id="filter-dates", min_date_allowed=date_min, max_date_allowed=date_max,
                                             start_date=date_min, end_date=date_max, display_format="YYYY-MM-DD",
                                             style={"backgroundColor": "white", "borderRadius": "6px"})], md=3)
            ], className="g-3")
        ]), style={"background": CARD, "border": "1px solid #19354c", "borderRadius": "12px"}, className="mb-4"),
        dbc.Row([
            dbc.Col(card_kpi("MARKETING SPEND", "kpi-spend", PINK), md=3, className="mb-3"),
            dbc.Col(card_kpi("ATTRIBUTED REVENUE", "kpi-revenue", GOLD), md=3, className="mb-3"),
            dbc.Col(card_kpi("BLENDED ROAS", "kpi-roas", "#c7a2ff", "Attributed revenue ÷ spend"), md=3, className="mb-3"),
            dbc.Col(card_kpi("ATTRIBUTED ORDERS", "kpi-orders", MINT), md=3, className="mb-3"),
        ], className="g-3 mb-2"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Spend vs attributed revenue by platform", style={"color": CYAN}), dcc.Graph(id="chart-revenue")] ), style={"background": CARD, "border": "1px solid #19354c"}), md=6, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Blended ROAS by platform", style={"color": "#c7a2ff"}), dcc.Graph(id="chart-roas")]), style={"background": CARD, "border": "1px solid #19354c"}), md=6, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Cost per attributed order (EGP)", style={"color": PINK}), dcc.Graph(id="chart-cpa")]), style={"background": CARD, "border": "1px solid #19354c"}), md=6, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Campaign response rates", style={"color": MINT}), dcc.Graph(id="chart-rates")]), style={"background": CARD, "border": "1px solid #19354c"}), md=6, className="mb-3"),
        ]),
        dbc.Card(dbc.CardBody([
            html.H5("Campaign explorer", style={"color": MINT}),
            html.P("Bands are descriptive ROAS groupings only; they do not establish profitability.", style={"color": MUTED}),
            dash_table.DataTable(
                id="campaign-table", columns=[
                    {"name": "Campaign ID", "id": "Campaign_ID"},
                    {"name": "Campaign", "id": "Campaign_Name"},
                    {"name": "Platform", "id": "Platform"},
                    {"name": "Product", "id": "Product_Name"},
                    {"name": "Spend (EGP)", "id": "Spend_EGP", "type": "numeric", "format": {"specifier": ",.0f"}},
                    {"name": "Attributed revenue (EGP)", "id": "Attributed_Revenue_EGP", "type": "numeric", "format": {"specifier": ",.0f"}},
                    {"name": "ROAS", "id": "ROAS", "type": "numeric", "format": {"specifier": ".2f"}},
                    {"name": "CPA (EGP)", "id": "CPA_EGP", "type": "numeric", "format": {"specifier": ",.1f"}},
                    {"name": "CTR %", "id": "CTR_Pct", "type": "numeric", "format": {"specifier": ".2f"}},
                    {"name": "ROAS band", "id": "Campaign_Status"},
                ],
                page_size=12, sort_action="native", filter_action="native",
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": "#041324", "color": CYAN, "fontWeight": "bold", "border": "1px solid #24445e"},
                style_cell={"backgroundColor": CARD, "color": TEXT, "border": "1px solid #18334a", "textAlign": "left", "padding": "8px", "minWidth": "90px", "maxWidth": "240px", "whiteSpace": "normal"},
                style_data_conditional=[
                    {"if": {"filter_query": '{Campaign_Status} = "High ROAS (review)"'}, "color": MINT},
                    {"if": {"filter_query": '{Campaign_Status} = "Low ROAS (review)"'}, "color": PINK}
                ]
            )
        ]), style={"background": CARD, "border": "1px solid #19354c"}, className="mb-4"),
        html.Hr(style={"borderColor": "#24445e"}),
        html.H3("Website performance", style={"color": CYAN}),
        html.P("Daily site-level metrics are separate from campaign attribution; they are not directly linked to campaign IDs.", style={"color": MUTED}),
        html.Div(id="web-status"),
        dbc.Row([
            dbc.Col(card_kpi("WEBSITE SESSIONS", "web-sessions", CYAN), md=3, className="mb-3"),
            dbc.Col(card_kpi("WEBSITE ORDERS", "web-orders", MINT), md=3, className="mb-3"),
            dbc.Col(card_kpi("SESSION CONVERSION RATE", "web-cvr", GOLD), md=3, className="mb-3"),
            dbc.Col(card_kpi("AVG PAGE LOAD (SEC)", "web-load", PINK), md=3, className="mb-3"),
        ], className="g-3"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([dcc.Graph(id="chart-web-trend")]), style={"background": CARD, "border": "1px solid #19354c"}), md=8, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([dcc.Graph(id="chart-web-quality")]), style={"background": CARD, "border": "1px solid #19354c"}), md=4, className="mb-3"),
        ]),
        html.Hr(style={"borderColor": "#24445e"}),
        html.H3("Sales & returns context", style={"color": CYAN}),
        html.P("This is transaction-level business context only. It is not attributed to individual campaigns.", style={"color": MUTED}),
        html.Div(id="sales-status"),
        dbc.Row([
            dbc.Col(card_kpi("NET SALES (RECORDED)", "sales-net", GOLD), md=3, className="mb-3"),
            dbc.Col(card_kpi("GROSS PROFIT (RECORDED)", "sales-profit", MINT), md=3, className="mb-3"),
            dbc.Col(card_kpi("RECORDED GROSS MARGIN", "sales-margin", CYAN), md=3, className="mb-3"),
            dbc.Col(card_kpi("RETURNED ROWS", "sales-returns", PINK), md=3, className="mb-3"),
        ], className="g-3"),
        dbc.Alert(id="returns-note", color="warning", className="mt-2"),
        html.Hr(style={"borderColor": "#24445e"}),
        html.H3("Data quality & assumptions", style={"color": CYAN}),
        html.Div(id="quality-summary"),
        html.P("Built for decision support. Validate campaign tracking, attribution windows, margin after returns, and channel costs before reallocating real budgets.",
               style={"color": MUTED, "fontSize": "13px", "marginTop": "18px"})
    ])
])


def apply_filters(platform, product, status, start_date, end_date):
    out = mkt.copy()
    if platform and platform != "All":
        out = out[out["Platform"] == platform]
    if product and product != "All":
        out = out[out["Product_ID"].astype(str) == str(product)]
    if status and status != "All":
        out = out[out["Campaign_Status"] == status]
    if start_date:
        start = pd.to_datetime(start_date, errors="coerce")
        if pd.notna(start):
            out = out[out["End_Date"] >= start]
    if end_date:
        end = pd.to_datetime(end_date, errors="coerce")
        if pd.notna(end):
            out = out[out["Start_Date"] <= end]
    return out


@app.callback(
    [Output("kpi-spend", "children"), Output("kpi-revenue", "children"),
     Output("kpi-roas", "children"), Output("kpi-orders", "children"),
     Output("chart-revenue", "figure"), Output("chart-roas", "figure"),
     Output("chart-cpa", "figure"), Output("chart-rates", "figure"),
     Output("campaign-table", "data")],
    [Input("filter-platform", "value"), Input("filter-product", "value"),
     Input("filter-status", "value"), Input("filter-dates", "start_date"),
     Input("filter-dates", "end_date")]
)
def update_marketing(platform, product, status, start_date, end_date):
    d = apply_filters(platform, product, status, start_date, end_date)
    spend = d["Spend_EGP"].sum(min_count=1)
    rev = d["Attributed_Revenue_EGP"].sum(min_count=1)
    orders = d["Orders_Attributed"].sum(min_count=1)
    imp = d["Impressions"].sum(min_count=1)
    clicks = d["Clicks"].sum(min_count=1)
    sessions = d["Landing_Page_Sessions"].sum(min_count=1)
    roas = rev / spend if pd.notna(spend) and spend > 0 and pd.notna(rev) else np.nan

    k_spend = money(spend) if pd.notna(spend) else "N/A"
    k_rev = money(rev) if pd.notna(rev) else "N/A"
    k_roas = f"{roas:.2f}x" if pd.notna(roas) else "N/A"
    k_orders = f"{orders:,.0f}" if pd.notna(orders) else "N/A"

    if d.empty:
        empty = empty_fig("No campaigns match the selected filters")
        return k_spend, k_rev, k_roas, k_orders, empty, empty, empty, empty, []

    plat = d.groupby("Platform", dropna=False).agg(
        Spend_EGP=("Spend_EGP", "sum"),
        Attributed_Revenue_EGP=("Attributed_Revenue_EGP", "sum"),
        Orders_Attributed=("Orders_Attributed", "sum"),
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
        Landing_Page_Sessions=("Landing_Page_Sessions", "sum")
    ).reset_index()
    plat["ROAS"] = np.where(plat["Spend_EGP"] > 0, plat["Attributed_Revenue_EGP"] / plat["Spend_EGP"], np.nan)
    plat["CPA_EGP"] = np.where(plat["Orders_Attributed"] > 0, plat["Spend_EGP"] / plat["Orders_Attributed"], np.nan)
    plat["CTR_Pct"] = np.where(plat["Impressions"] > 0, 100 * plat["Clicks"] / plat["Impressions"], np.nan)
    plat["Session_to_Order_Pct"] = np.where(plat["Landing_Page_Sessions"] > 0, 100 * plat["Orders_Attributed"] / plat["Landing_Page_Sessions"], np.nan)

    fig_rev = px.bar(plat, x="Platform", y=["Spend_EGP", "Attributed_Revenue_EGP"], barmode="group",
                     labels={"value": "EGP", "variable": "Metric"}, color_discrete_map={"Spend_EGP": PINK, "Attributed_Revenue_EGP": MINT})
    fig_roas = px.bar(plat.sort_values("ROAS", ascending=False), x="Platform", y="ROAS", text="ROAS",
                      labels={"ROAS": "Attributed revenue / spend"}, color_discrete_sequence=["#a98bff"])
    fig_roas.update_traces(texttemplate="%{text:.2f}x", textposition="outside")
    fig_cpa = px.bar(plat.sort_values("CPA_EGP"), x="Platform", y="CPA_EGP", text="CPA_EGP",
                     labels={"CPA_EGP": "Spend / attributed orders (EGP)"}, color_discrete_sequence=[PINK])
    fig_cpa.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    rates = plat.melt(id_vars="Platform", value_vars=["CTR_Pct", "Session_to_Order_Pct"],
                      var_name="Metric", value_name="Percent")
    rates["Metric"] = rates["Metric"].map({"CTR_Pct": "CTR", "Session_to_Order_Pct": "Sessions to attributed orders"})
    fig_rates = px.bar(rates, x="Platform", y="Percent", color="Metric", barmode="group",
                       labels={"Percent": "Percent (%)"}, color_discrete_sequence=[CYAN, GOLD])
    for fig in [fig_rev, fig_roas, fig_cpa, fig_rates]:
        chart_layout(fig)
    table_cols = ["Campaign_ID", "Campaign_Name", "Platform", "Product_Name", "Spend_EGP",
                  "Attributed_Revenue_EGP", "ROAS", "CPA_EGP", "CTR_Pct", "Campaign_Status"]
    table = d[table_cols].replace({np.nan: None}).to_dict("records")
    return k_spend, k_rev, k_roas, k_orders, fig_rev, fig_roas, fig_cpa, fig_rates, table


@app.callback(
    [Output("web-sessions", "children"), Output("web-orders", "children"),
     Output("web-cvr", "children"), Output("web-load", "children"),
     Output("chart-web-trend", "figure"), Output("chart-web-quality", "figure"),
     Output("web-status", "children")],
    [Input("filter-dates", "start_date"), Input("filter-dates", "end_date")]
)
def update_website(start_date, end_date):
    if web is None:
        msg = web_error or "Website dataset unavailable."
        return "N/A", "N/A", "N/A", "N/A", empty_fig(msg), empty_fig(msg), dbc.Alert(msg, color="secondary")
    d = web.copy()
    if start_date:
        d = d[d["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        d = d[d["Date"] <= pd.to_datetime(end_date)]
    if d.empty:
        msg = "No website rows in selected date range."
        return "0", "0", "N/A", "N/A", empty_fig(msg), empty_fig(msg), dbc.Alert(msg, color="warning")
    sessions = d["Sessions"].sum()
    orders = d["Orders"].sum()
    cvr = 100 * orders / sessions if sessions > 0 else np.nan
    load = d["Avg_Page_Load_Sec"].mean()
    # Daily time series: keep true dates (not string month labels) and separate scales
    # because sessions and orders differ greatly in magnitude.
    trend = d.groupby("Date", as_index=False).agg(
        Sessions=("Sessions", "sum"), Orders=("Orders", "sum")
    ).sort_values("Date")
    trend_fig = make_subplots(specs=[[{"secondary_y": True}]])
    trend_fig.add_trace(go.Scatter(
        x=trend["Date"], y=trend["Sessions"], mode="lines", name="Sessions",
        line=dict(color="#8c8cff", width=2),
        hovertemplate="%{x|%d %b %Y}<br>Sessions: %{y:,.0f}<extra></extra>"
    ), secondary_y=False)
    trend_fig.add_trace(go.Scatter(
        x=trend["Date"], y=trend["Orders"], mode="lines", name="Orders",
        line=dict(color="#ff9b72", width=2),
        hovertemplate="%{x|%d %b %Y}<br>Orders: %{y:,.0f}<extra></extra>"
    ), secondary_y=True)
    trend_fig.update_xaxes(title_text="Date", tickformat="%d %b", gridcolor="#1c3448")
    trend_fig.update_yaxes(title_text="Sessions", secondary_y=False, gridcolor="#1c3448")
    trend_fig.update_yaxes(title_text="Orders", secondary_y=True, showgrid=False)
    trend_fig.update_layout(title="Daily website sessions and orders", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hovermode="x unified")
    trend_fig = chart_layout(trend_fig, 330)
    if "Conversion_Rate" in d.columns:
        # Normalize stored rates to percentage points before comparing.
        recorded_series = d["Conversion_Rate"].dropna()
        if not recorded_series.empty:
            recorded_pct = recorded_series * 100 if recorded_series.max() <= 1 else recorded_series
            recorded = recorded_pct.mean()
            q = pd.DataFrame({
                "Metric": ["Overall orders ÷ sessions", "Mean recorded daily rate"],
                "Value": [cvr, recorded]
            })
            quality_fig = px.bar(q, x="Metric", y="Value", text="Value",
                                 labels={"Value": "Conversion rate (%)"},
                                 color_discrete_sequence=[GOLD])
            quality_fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            quality_fig.update_yaxes(rangemode="tozero", gridcolor="#1c3448")
            quality_fig.update_layout(title="Conversion-rate cross-check", showlegend=False)
        else:
            quality_fig = empty_fig("No valid recorded conversion-rate values")
    else:
        quality_fig = empty_fig("Conversion rate column unavailable")
    quality_fig = chart_layout(quality_fig, 330)
    msg = dbc.Alert(f"Loaded {len(d):,} daily rows. Site metrics are aggregated independently of campaign records.", color="info")
    return f"{sessions:,.0f}", f"{orders:,.0f}", f"{cvr:.2f}%" if pd.notna(cvr) else "N/A", f"{load:.2f}" if pd.notna(load) else "N/A", trend_fig, quality_fig, msg


@app.callback(
    [Output("sales-net", "children"), Output("sales-profit", "children"),
     Output("sales-margin", "children"), Output("sales-returns", "children"),
     Output("returns-note", "children"), Output("sales-status", "children")],
    [Input("filter-dates", "start_date"), Input("filter-dates", "end_date")]
)
def update_sales(start_date, end_date):
    if sales is None:
        msg = sales_error or "Sales dataset unavailable."
        return "N/A", "N/A", "N/A", "N/A", msg, dbc.Alert(msg, color="secondary")
    d = sales.copy()
    if start_date:
        d = d[d["Order_Date"] >= pd.to_datetime(start_date)]
    if end_date:
        d = d[d["Order_Date"] <= pd.to_datetime(end_date)]
    net = d["Net_Sales_EGP"].sum(min_count=1)
    profit = d["Gross_Profit_EGP"].sum(min_count=1)
    margin = 100 * profit / net if pd.notna(net) and net != 0 and pd.notna(profit) else np.nan
    returned = d["Returned"].isin(["yes", "true", "1", "y"]).sum()
    refund_sum = d["Refund_Value_EGP"].sum(min_count=1) if "Refund_Value_EGP" in d.columns else np.nan
    note = ("Recorded gross profit may not reflect refunds/returns. Review the business definition before treating it as post-return profit. "
            f"Recorded refund value in this date window: {money(refund_sum)}." if pd.notna(refund_sum) else
            "Recorded gross profit may not reflect refunds/returns; refund value is unavailable.")
    msg = dbc.Alert(f"Loaded {len(d):,} transaction rows in the selected order-date window. Sales are not campaign-attributed.", color="info")
    return money(net), money(profit), f"{margin:.2f}%" if pd.notna(margin) else "N/A", f"{returned:,}", note, msg


@app.callback(
    Output("quality-summary", "children"),
    [Input("filter-platform", "value"), Input("filter-product", "value"),
     Input("filter-status", "value"), Input("filter-dates", "start_date"),
     Input("filter-dates", "end_date")]
)
def show_quality(platform, product, status, start_date, end_date):
    d = apply_filters(platform, product, status, start_date, end_date)
    issues = []
    for col, counts in mkt_quality["numeric_issues"].items():
        if counts["missing"] or counts["non_numeric"]:
            issues.append(f"{col}: {counts['missing']} missing, {counts['non_numeric']} non-numeric")
    items = [
        html.Li(f"Marketing rows in file: {mkt_quality['rows']:,}; rows after filters: {len(d):,}."),
        html.Li(f"Duplicate full rows: {mkt_quality['duplicate_rows']:,}; duplicate Campaign_ID values: {mkt_quality['duplicate_campaign_ids']:,}."),
        html.Li(f"Invalid/missing campaign dates: {mkt_quality['bad_date_rows']:,}; end date before start date: {mkt_quality['end_before_start']:,}."),
        html.Li(f"Negative cells across key numeric columns: {mkt_quality['negative_numeric_cells']:,}."),
        html.Li(f"Rows where Clicks equals Landing_Page_Sessions: {mkt_quality['clicks_equal_sessions_rows']:,} of {mkt_quality['rows']:,}; this may reflect a modeled-data assumption."),
        html.Li("Campaign ROAS bands (5x and 2x thresholds) are descriptive only and are not proof of profitability."),
        html.Li("Marketing.csv is modeled campaign performance, not an actual media-account export.")
    ]
    if issues:
        items.append(html.Li("Numeric parsing issues: " + "; ".join(issues)))
    if web is None:
        items.append(html.Li(web_error or "Website file not loaded."))
    if sales is None:
        items.append(html.Li(sales_error or "Sales file not loaded."))
    return dbc.Card(dbc.CardBody(html.Ul(items, style={"lineHeight": "1.9"})),
                    style={"background": CARD, "border": "1px solid #19354c"})


@app.callback(
    Output("download-csv", "data"),
    Input("btn-export", "n_clicks"),
    [State("filter-platform", "value"), State("filter-product", "value"),
     State("filter-status", "value"), State("filter-dates", "start_date"),
     State("filter-dates", "end_date")],
    prevent_initial_call=True
)
def export_csv(n_clicks, platform, product, status, start_date, end_date):
    d = apply_filters(platform, product, status, start_date, end_date)
    return dcc.send_data_frame(d.to_csv, "app5_filtered_marketing_campaigns.csv", index=False)


if __name__ == "__main__":
    app.run(debug=False, port=8055)
