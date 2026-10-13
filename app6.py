"""
App 06 — Branch Performance & Expansion Intelligence
Sharnouby / LEO MODA | Dash + Plotly
Run: python app_06_branch_expansion.py
Data CSVs should be in the same folder as this file.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from dash import Dash, dcc, html, Input, Output, State, dash_table
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

BASE_DIR = Path(__file__).resolve().parent
FILES = {
    "sales": BASE_DIR / "Sales_Transactions.csv",
    "locations": BASE_DIR / "Locations.csv",
    "customers": BASE_DIR / "Customers.csv",
    "service": BASE_DIR / "Customer_Service.csv",
}

def load_data():
    missing = [str(p.name) for p in FILES.values() if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required CSV file(s): " + ", ".join(missing))
    sales = pd.read_csv(FILES["sales"], low_memory=False)
    locations = pd.read_csv(FILES["locations"], encoding="utf-8-sig")
    customers = pd.read_csv(FILES["customers"], low_memory=False)
    service = pd.read_csv(FILES["service"], low_memory=False)

    for col in ["Order_Date", "Return_Date"]:
        if col in sales:
            sales[col] = pd.to_datetime(sales[col], errors="coerce")
    sales["Net_Sales_EGP"] = pd.to_numeric(sales["Net_Sales_EGP"], errors="coerce").fillna(0)
    sales["Gross_Profit_EGP"] = pd.to_numeric(sales["Gross_Profit_EGP"], errors="coerce").fillna(0)
    sales["Quantity"] = pd.to_numeric(sales["Quantity"], errors="coerce").fillna(0)
    sales["Refund_Value_EGP"] = pd.to_numeric(sales["Refund_Value_EGP"], errors="coerce").fillna(0)
    sales["Gross_Margin_Pct"] = pd.to_numeric(sales["Gross_Margin_Pct"], errors="coerce")
    sales["Returned_Flag"] = sales["Returned"].astype(str).str.strip().str.lower().eq("yes")
    sales["Return_Flag"] = sales["Returned_Flag"].astype(int)
    sales["Month"] = sales["Order_Date"].dt.to_period("M").dt.to_timestamp()
    sales["Month_Label"] = sales["Month"].dt.strftime("%Y-%m")
    sales["Customer_Governorate"] = sales["Customer_Governorate"].fillna("Unknown").astype(str)
    sales["Channel"] = sales["Channel"].fillna("Unknown").astype(str)
    sales = sales.merge(
        locations[["Location_ID", "Location_Name", "Location_Type", "Channel", "Governorate", "City"]],
        on="Location_ID", how="left", suffixes=("", "_Location")
    )
    # Keep transaction channel as the source of truth; location master adds descriptive metadata.
    sales["Location_Name"] = sales["Location_Name"].fillna(sales.get("Location_Name_Location"))
    sales["Location_Type"] = sales["Location_Type"].fillna("Unclassified")
    sales["AOV_proxy"] = sales["Net_Sales_EGP"]  # dataset has one row per invoice in current extract
    service["CSAT_1_to_5"] = pd.to_numeric(service["CSAT_1_to_5"], errors="coerce")
    service["Resolution_Hours"] = pd.to_numeric(service["Resolution_Hours"], errors="coerce")
    service["First_Response_Minutes"] = pd.to_numeric(service["First_Response_Minutes"], errors="coerce")
    return sales, locations, customers, service

SALES, LOCATIONS, CUSTOMERS, SERVICE = load_data()
MIN_DATE = SALES["Order_Date"].min().date()
MAX_DATE = SALES["Order_Date"].max().date()
MONTHS = sorted(SALES["Month_Label"].dropna().unique())
LOCATION_OPTIONS = [{"label": "All selling locations", "value": "ALL"}] + [
    {"label": f'{r.Location_Name} · {r.Channel}', "value": r.Location_ID}
    for r in LOCATIONS.itertuples() if r.Location_ID in set(SALES["Location_ID"])
]
CHANNEL_OPTIONS = [{"label": "All channels", "value": "ALL"}] + [
    {"label": c, "value": c} for c in sorted(SALES["Channel"].dropna().unique())
]

COLORS = {"bg": "#0b1220", "panel": "#111c2f", "text": "#e7eef9", "muted": "#9aabc4",
          "blue": "#5ba8ff", "teal": "#4dd4ac", "orange": "#ffb454", "red": "#ff7373"}

def money(v):
    return f"EGP {v:,.0f}"

def metric_card(label, value, sub=""):
    return dbc.Card(dbc.CardBody([
        html.Div(label, className="metric-label"),
        html.Div(value, className="metric-value"),
        html.Div(sub, className="metric-sub") if sub else html.Div()
    ]), className="metric-card h-100")

def style_fig(fig, height=330):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
        font=dict(family="Arial", color=COLORS["text"]), height=height,
        margin=dict(l=18, r=18, t=48, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=dict(font=dict(size=15)), hoverlabel=dict(bgcolor="#17243a")
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#26364e", zeroline=False)
    return fig

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], title="Branch Performance & Expansion")
app.layout = dbc.Container(fluid=True, className="app-shell", children=[
    html.Div(className="topbar", children=[
        html.Div([
            html.Div("SHARNoubY  /  LEO MODA", className="eyebrow"),
            html.H1("Branch Performance & Expansion Intelligence"),
            html.P("Compare value creation across channels, then identify geographic demand signals for the next expansion decision.")
        ]),
        html.Div([html.Div("APP 06", className="app-pill"), html.Div("DATA-DRIVEN DECISIONS", className="status-text")], className="topbar-right")
    ]),
    dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col([html.Label("Order date range"), dcc.DatePickerRange(
                id="date-range", min_date_allowed=MIN_DATE, max_date_allowed=MAX_DATE,
                start_date=MIN_DATE, end_date=MAX_DATE, display_format="DD MMM YYYY",
                className="date-picker"
            )], md=4),
            dbc.Col([html.Label("Selling location"), dcc.Dropdown(id="location-filter", options=LOCATION_OPTIONS,
                value="ALL", clearable=False, className="dark-dropdown")], md=4),
            dbc.Col([html.Label("Channel"), dcc.Dropdown(id="channel-filter", options=CHANNEL_OPTIONS,
                value="ALL", clearable=False, className="dark-dropdown")], md=4),
        ], className="g-3 align-items-end"),
    ]), className="filter-card mb-4"),
    html.Div(id="kpi-row", className="mb-4"),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="monthly-trend", config={"displayModeBar": False})), className="chart-card"), lg=7, className="mb-4"),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="location-comparison", config={"displayModeBar": False})), className="chart-card"), lg=5, className="mb-4"),
    ]),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="governorate-demand", config={"displayModeBar": False})), className="chart-card"), lg=7, className="mb-4"),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="quality-returns", config={"displayModeBar": False})), className="chart-card"), lg=5, className="mb-4"),
    ]),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("Location scorecard", className="section-title"),
            html.P("Use this table to compare sales channels on revenue, profit and return rate. Wholesale is structurally different from retail and online.", className="helper-text"),
            html.Div(id="location-table")
        ]), className="chart-card"), lg=7, className="mb-4"),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("Expansion signals", className="section-title"),
            html.Div(id="expansion-notes"),
            html.Hr(),
            html.H4("Customer service pulse", className="section-title"),
            html.Div(id="service-pulse"),
            dbc.Button("Export filtered transactions (CSV)", id="export-btn", color="info", outline=True, className="mt-3 w-100"),
            dcc.Download(id="download-data")
        ]), className="chart-card"), lg=5, className="mb-4"),
    ]),
    html.Div([
        html.Span("DATA NOTE", className="note-label"),
        html.Span("Transactions and customer/service records are marked as modeled training data. These outputs are directional analysis, not verified real-world branch forecasts. Only one physical retail store is represented in the location master; candidate-city rankings are demand signals, not proof that a new branch will be profitable.")
    ], className="footnote"),
], style={"maxWidth": "1600px"})

app.index_string = """<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
body{background:#0b1220;color:#e7eef9;font-family:Inter,Arial,sans-serif}
.app-shell{padding:28px 28px 18px;max-width:1600px}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:24px}
.eyebrow{color:#5ba8ff;font-size:12px;font-weight:800;letter-spacing:2px;margin-bottom:10px}
h1{font-weight:750;font-size:clamp(25px,3vw,38px);letter-spacing:-.7px;margin:0 0 8px}
.topbar p,.helper-text{color:#9aabc4;max-width:850px;margin:0;line-height:1.55}
.topbar-right{text-align:right;min-width:145px}.app-pill{display:inline-block;border:1px solid #31517a;color:#83c0ff;padding:7px 12px;border-radius:8px;font-size:12px;font-weight:800;letter-spacing:1px}
.status-text{color:#8294ae;font-size:10px;letter-spacing:1.2px;margin-top:8px}
.card{background:#111c2f!important;border:1px solid #22324a!important;border-radius:15px!important;box-shadow:0 8px 24px #0002}
.filter-card .card-body{padding:18px 20px}label{color:#aebed3;font-size:12px;font-weight:700;margin-bottom:8px}
.metric-card{min-height:124px}.metric-card .card-body{padding:20px}
.metric-label{color:#9aabc4;font-size:12px;font-weight:650;margin-bottom:12px}
.metric-value{font-size:clamp(22px,2.2vw,30px);font-weight:800;letter-spacing:-.6px;line-height:1.15}
.metric-sub{font-size:11px;color:#8194af;margin-top:9px}
.chart-card .card-body{padding:16px}.section-title{font-size:17px;font-weight:750;margin-bottom:12px}
.footnote{display:flex;gap:14px;align-items:flex-start;border:1px solid #283850;background:#101a2b;padding:16px;border-radius:12px;color:#9aabc4;font-size:12px;line-height:1.6;margin:2px 0 16px}
.note-label{color:#ffb454;font-weight:800;letter-spacing:1px;white-space:nowrap}
.DateRangePickerInput,.DateInput,.DateInput_input{background:#17243a!important;color:#e7eef9!important;border:0!important}
.DateInput_input{font-size:13px!important}.DateRangePickerInput{border:1px solid #33445f!important;border-radius:7px!important;padding:4px!important}
.Select-control,.Select-menu-outer,.Select-menu,.Select-option,.Select-value-label,.Select-placeholder,.Select-input>input{background:#17243a!important;color:#e7eef9!important;border-color:#33445f!important}
.dark-dropdown .Select-control{border-radius:7px!important;min-height:38px}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th{background:#1a2940!important;color:#c5d5ea!important;border-color:#2b3b53!important}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td{background:#111c2f!important;color:#e7eef9!important;border-color:#24344c!important}
@media(max-width:768px){.app-shell{padding:15px}.topbar{display:block}.topbar-right{text-align:left;margin-top:16px}.footnote{display:block}.note-label{display:block;margin-bottom:8px}}
</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

@app.callback(
    Output("kpi-row", "children"), Output("monthly-trend", "figure"),
    Output("location-comparison", "figure"), Output("governorate-demand", "figure"),
    Output("quality-returns", "figure"), Output("location-table", "children"),
    Output("expansion-notes", "children"), Output("service-pulse", "children"),
    Input("date-range", "start_date"), Input("date-range", "end_date"),
    Input("location-filter", "value"), Input("channel-filter", "value")
)
def update_dashboard(start_date, end_date, location_id, channel):
    d = SALES.copy()
    if start_date: d = d[d["Order_Date"] >= pd.to_datetime(start_date)]
    if end_date: d = d[d["Order_Date"] < pd.to_datetime(end_date) + pd.Timedelta(days=1)]
    if location_id != "ALL": d = d[d["Location_ID"] == location_id]
    if channel != "ALL": d = d[d["Channel"] == channel]
    total_sales = d["Net_Sales_EGP"].sum()
    profit = d["Gross_Profit_EGP"].sum()
    margin = profit / total_sales * 100 if total_sales else 0
    qty = d["Quantity"].sum()
    returns = d["Return_Flag"].mean() * 100 if len(d) else 0
    orders = d["Invoice_ID"].nunique() if len(d) else 0
    kpis = dbc.Row([
        dbc.Col(metric_card("NET SALES", money(total_sales), f"{orders:,} invoice rows / unique invoices"), md=6, xl=2, className="mb-3"),
        dbc.Col(metric_card("GROSS PROFIT", money(profit), f"Gross margin {margin:.1f}%"), md=6, xl=2, className="mb-3"),
        dbc.Col(metric_card("UNITS SOLD", f"{qty:,.0f}", "Quantity across filtered transactions"), md=6, xl=2, className="mb-3"),
        dbc.Col(metric_card("RETURN RATE", f"{returns:.2f}%", f"{int(d['Return_Flag'].sum()):,} returned transaction rows"), md=6, xl=2, className="mb-3"),
        dbc.Col(metric_card("ACTIVE SELLING LOCATIONS", f"{d['Location_ID'].nunique():,}", "Within current filters"), md=6, xl=2, className="mb-3"),
        dbc.Col(metric_card("AVG ORDER VALUE*", money(total_sales / orders if orders else 0), "*Invoice-level proxy in this extract"), md=6, xl=2, className="mb-3"),
    ], className="g-3")

    monthly = d.groupby("Month", as_index=False).agg(Net_Sales_EGP=("Net_Sales_EGP","sum"), Gross_Profit_EGP=("Gross_Profit_EGP","sum"))
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Net_Sales_EGP"], name="Net sales", mode="lines", line=dict(color=COLORS["blue"], width=3), fill="tozeroy", fillcolor="rgba(91,168,255,.10)"))
    fig_trend.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Gross_Profit_EGP"], name="Gross profit", mode="lines", line=dict(color=COLORS["teal"], width=2)))
    fig_trend.update_layout(title="Monthly sales & gross profit", yaxis_title="EGP", hovermode="x unified")
    fig_trend = style_fig(fig_trend)

    byloc = d.groupby(["Location_Name","Channel"], as_index=False).agg(Net_Sales_EGP=("Net_Sales_EGP","sum"), Gross_Profit_EGP=("Gross_Profit_EGP","sum"))
    fig_loc = px.bar(byloc.sort_values("Net_Sales_EGP"), x="Net_Sales_EGP", y="Location_Name", color="Channel", orientation="h", barmode="group", title="Commercial scale by selling location", labels={"Net_Sales_EGP":"Net sales (EGP)","Location_Name":"Location"})
    fig_loc = style_fig(fig_loc, 330)

    geo = d.groupby("Customer_Governorate", as_index=False).agg(Net_Sales_EGP=("Net_Sales_EGP","sum"), Customers=("Customer_ID","nunique"), Units=("Quantity","sum"))
    geo = geo.sort_values("Net_Sales_EGP", ascending=False).head(12)
    fig_geo = px.bar(geo.sort_values("Net_Sales_EGP"), x="Net_Sales_EGP", y="Customer_Governorate", orientation="h",
                     color="Customers", color_continuous_scale=["#24415f","#5ba8ff"], title="Top customer governorates by attributed transaction sales",
                     labels={"Net_Sales_EGP":"Net sales (EGP)","Customer_Governorate":"Customer governorate","Customers":"Unique customers"})
    fig_geo = style_fig(fig_geo, 360)

    returns_by = d.groupby("Channel", as_index=False).agg(Return_Rate=("Return_Flag","mean"), Refund_Value_EGP=("Refund_Value_EGP","sum"), Rows=("Row_ID","count"))
    returns_by["Return_Rate"] *= 100
    fig_ret = px.bar(returns_by, x="Channel", y="Return_Rate", color="Channel", title="Returned transaction rate by channel", labels={"Return_Rate":"Returned rows (%)"})
    fig_ret = style_fig(fig_ret, 360)
    fig_ret.update_layout(showlegend=False)

    score = d.groupby(["Location_ID","Location_Name","Channel"], as_index=False).agg(
        Transactions=("Invoice_ID","nunique"), Net_Sales_EGP=("Net_Sales_EGP","sum"),
        Gross_Profit_EGP=("Gross_Profit_EGP","sum"), Units=("Quantity","sum"),
        Return_Rate=("Return_Flag","mean"), Refund_Value_EGP=("Refund_Value_EGP","sum"))
    score["Gross_Margin_Pct"] = np.where(score["Net_Sales_EGP"] != 0, score["Gross_Profit_EGP"]/score["Net_Sales_EGP"]*100, 0)
    score["Return_Rate"] *= 100
    score = score.sort_values("Net_Sales_EGP", ascending=False)
    display = score[["Location_Name","Channel","Transactions","Net_Sales_EGP","Gross_Profit_EGP","Gross_Margin_Pct","Return_Rate","Refund_Value_EGP","Units"]].copy()
    for c in ["Net_Sales_EGP","Gross_Profit_EGP","Refund_Value_EGP"]:
        display[c] = display[c].map(lambda x: f"{x:,.0f}")
    display["Gross_Margin_Pct"] = display["Gross_Margin_Pct"].map(lambda x: f"{x:.1f}%")
    display["Return_Rate"] = display["Return_Rate"].map(lambda x: f"{x:.2f}%")
    table = dash_table.DataTable(
        data=display.to_dict("records"), columns=[{"name":c.replace("_"," "), "id":c} for c in display.columns],
        page_size=8, sort_action="native", style_table={"overflowX":"auto"},
        style_cell={"backgroundColor":COLORS["panel"],"color":COLORS["text"],"border":"1px solid #26364e","padding":"9px","fontSize":"11px","textAlign":"left","minWidth":"90px","maxWidth":"220px","whiteSpace":"normal"},
        style_header={"backgroundColor":"#1a2940","fontWeight":"bold","color":"#c5d5ea"},
        style_data_conditional=[{"if":{"column_id":"Gross_Margin_Pct"},"color":COLORS["teal"]}]
    )

    # Expansion demand signal: governorate-level modeled customer base + observed sales.
    # It is a screening indicator, not a store-level forecast or causal estimate.
    all_geo = SALES.groupby("Customer_Governorate", as_index=False).agg(
        Observed_Sales_EGP=("Net_Sales_EGP","sum"), Sales_Customers=("Customer_ID","nunique"), Units=("Quantity","sum"))
    customer_geo = CUSTOMERS.groupby("Governorate", as_index=False).agg(Customer_Records=("Customer_ID","nunique"))
    signals = customer_geo.merge(all_geo, left_on="Governorate", right_on="Customer_Governorate", how="left")
    signals["Observed_Sales_EGP"] = signals["Observed_Sales_EGP"].fillna(0)
    signals["Sales_Customers"] = signals["Sales_Customers"].fillna(0)
    signals["Customer_Records"] = signals["Customer_Records"].fillna(0)
    signals = signals[~signals["Governorate"].isin(["Other","Unknown"])]
    signals = signals.sort_values(["Customer_Records","Observed_Sales_EGP"], ascending=False).head(5)
    expansion_children = [
        html.P("Screening signals from customer records and transaction history—not a forecast of new-branch revenue.", className="helper-text"),
        html.Div([
            html.Div([
                html.Div(str(r.Governorate), className="signal-title"),
                html.Div(f"{int(r.Customer_Records):,} customer records", className="signal-main"),
                html.Div(f"Observed transaction sales: {money(r.Observed_Sales_EGP)}", className="signal-sub"),
            ], className="signal-row") for r in signals.itertuples()
        ]),
        html.Div("Before selecting a site, validate rent, footfall, competition, logistics cost, local demand, and a realistic store-level sales forecast.", className="recommendation-box")
    ]

    service_rows = SERVICE.groupby("Channel", as_index=False).agg(Tickets=("Ticket_ID","count"), Avg_CSAT=("CSAT_1_to_5","mean"), Avg_Response_Min=("First_Response_Minutes","mean"), Avg_Resolution_Hours=("Resolution_Hours","mean"))
    service_rows = service_rows.sort_values("Tickets", ascending=False)
    service_children = [
        html.Div([
            html.Div(f"{r.Channel}", className="service-channel"),
            html.Div(f"CSAT {r.Avg_CSAT:.2f}/5 · {r.Tickets:,} tickets", className="service-main"),
            html.Div(f"First response {r.Avg_Response_Min:.0f} min · resolution {r.Avg_Resolution_Hours:.1f} h", className="signal-sub")
        ], className="service-row") for r in service_rows.itertuples()
    ]
    return kpis, fig_trend, fig_loc, fig_geo, fig_ret, table, expansion_children, service_children


@app.callback(
    Output("download-data", "data"),
    Input("export-btn", "n_clicks"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("location-filter", "value"),
    State("channel-filter", "value"),
    prevent_initial_call=True
)
def export_filtered(n, start_date, end_date, location_id, channel):
    # Start from the original sales data
    d = SALES.copy()

    # Apply the selected date range
    if start_date:
        d = d[d["Order_Date"] >= pd.to_datetime(start_date)]

    if end_date:
        end_exclusive = pd.to_datetime(end_date) + pd.Timedelta(days=1)
        d = d[d["Order_Date"] < end_exclusive]

    # Apply location and channel filters
    if location_id and location_id != "ALL":
        d = d[d["Location_ID"] == location_id]

    if channel and channel != "ALL":
        d = d[d["Channel"] == channel]

    # Remove helper columns before export
    export_df = d.drop(
        columns=["Month", "Month_Label", "Returned_Flag", "Return_Flag"],
        errors="ignore"
    )

    # Return a proper Dash download response
    return dcc.send_data_frame(
        export_df.to_csv,
        "app06_filtered_transactions.csv",
        index=False,
        encoding="utf-8-sig"
    )

app.index_string = app.index_string.replace("</style>", """
.signal-row,.service-row{padding:12px 0;border-bottom:1px solid #26364e}
.signal-row:last-child,.service-row:last-child{border-bottom:0}
.signal-title{font-weight:800;color:#dbeaff;font-size:13px}
.signal-main,.service-main{font-weight:650;font-size:12px;margin-top:5px}
.signal-sub{font-size:11px;color:#91a4be;margin-top:4px;line-height:1.45}
.recommendation-box{background:#1b293d;border-left:3px solid #ffb454;padding:12px;margin-top:14px;color:#bdcce0;font-size:11px;line-height:1.6;border-radius:5px}
</style>""")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8060)
