"""App 07 - Procurement, Cost & Supplier Risk Intelligence
Sharnouby / LEO MODA | Dash + Plotly
Run: python app7.py
Required CSV files in the same folder: Purchase_Orders.csv, Suppliers.csv, Quality.csv, Materials.csv
Note: source records are modeled/anonymized training data; supplier identity is anonymized.
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
    "orders": BASE_DIR / "Purchase_Orders.csv",
    "suppliers": BASE_DIR / "Suppliers.csv",
    "quality": BASE_DIR / "Quality.csv",
    "materials": BASE_DIR / "Materials.csv",
}
missing_files = [p.name for p in FILES.values() if not p.exists()]
if missing_files:
    raise FileNotFoundError("Missing required CSV file(s): " + ", ".join(missing_files))

orders = pd.read_csv(FILES["orders"], low_memory=False)
suppliers = pd.read_csv(FILES["suppliers"], low_memory=False)
quality = pd.read_csv(FILES["quality"], low_memory=False)
materials = pd.read_csv(FILES["materials"], low_memory=False)

# Normalize source types
for col in ["Order_Date", "Promised_Date", "Actual_Receipt_Date"]:
    orders[col] = pd.to_datetime(orders[col], errors="coerce")
quality["Inspection_Date"] = pd.to_datetime(quality["Inspection_Date"], errors="coerce")
for col in ["Ordered_Qty", "Unit_Cost_EGP", "Accepted_Qty", "Rejected_Qty"]:
    orders[col] = pd.to_numeric(orders[col], errors="coerce").fillna(0)
for col in ["Inspected_Qty", "Passed_Qty", "Rejected_Qty", "Estimated_Loss_EGP"]:
    quality[col] = pd.to_numeric(quality[col], errors="coerce").fillna(0)

orders["PO_Value_EGP"] = orders["Ordered_Qty"] * orders["Unit_Cost_EGP"]
orders["Delay_Days"] = (orders["Actual_Receipt_Date"] - orders["Promised_Date"]).dt.days
orders["Late_Flag"] = orders["Delay_Days"].gt(0)
orders["On_Time_Flag"] = orders["Delay_Days"].le(0)
orders["Receipt_Qty"] = orders["Accepted_Qty"] + orders["Rejected_Qty"]
orders["Reject_Rate_Pct"] = np.where(orders["Receipt_Qty"] > 0, orders["Rejected_Qty"] / orders["Receipt_Qty"] * 100, 0)
orders["Order_Month"] = orders["Order_Date"].dt.to_period("M").dt.to_timestamp()
orders["Order_Month_Label"] = orders["Order_Date"].dt.strftime("%b %Y")
orders = orders.merge(suppliers, on="Supplier_ID", how="left", suffixes=("", "_Supplier"))
orders = orders.merge(materials[["Material_ID", "Material_Category", "Standard_Lead_Time_Days"]], on="Material_ID", how="left")
quality["Reject_Rate_Pct"] = np.where(quality["Inspected_Qty"] > 0, quality["Rejected_Qty"] / quality["Inspected_Qty"] * 100, 0)

DATE_MIN = orders["Order_Date"].min().date()
DATE_MAX = orders["Order_Date"].max().date()
SUPPLIER_OPTIONS = [{"label": "All suppliers", "value": "ALL"}] + [
    {"label": f"{r.Supplier_Name} ({r.Supplier_ID})", "value": r.Supplier_ID}
    for r in suppliers.sort_values("Supplier_ID").itertuples()
]
CATEGORY_OPTIONS = [{"label": "All material categories", "value": "ALL"}] + [
    {"label": str(x), "value": str(x)} for x in sorted(orders["Material_Category"].dropna().unique())
]

BG = "#0b1220"
PANEL = "#111d30"
BORDER = "#263a56"
TEXT = "#e7eefb"
MUTED = "#91a6c7"
ACCENT = "#5aa7ff"
TEAL = "#2dd4bf"

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], title="Procurement & Supplier Risk")
app.layout = html.Div(style={"backgroundColor": BG, "minHeight": "100vh", "color": TEXT, "padding": "18px 22px", "fontFamily": "Arial, sans-serif"}, children=[
    html.Div(style={"display":"flex", "justifyContent":"space-between", "alignItems":"start", "marginBottom":"16px"}, children=[
        html.Div(children=[
            html.Div("SHARNOUBy / LEO MODA", style={"fontSize":"10px","letterSpacing":"2px","color":TEAL,"fontWeight":"700"}),
            html.H1("Procurement, Cost & Supplier Risk", style={"fontSize":"29px","fontWeight":"800","margin":"6px 0"}),
            html.Div("Where do cost, delay, and quality risk begin?", style={"color":"#a9c7f7","fontSize":"13px"}),
        ]),
        html.Div("APP 07\nDATA-DRIVEN DECISIONS", style={"whiteSpace":"pre-line","textAlign":"right","fontSize":"10px","lineHeight":"1.8","color":MUTED,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"8px 12px"})
    ]),
    dbc.Card(style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}","borderRadius":"12px","marginBottom":"14px"}, body=True, children=[
        dbc.Row([
            dbc.Col([html.Label("Order date range", style={"fontSize":"11px","color":MUTED}), dcc.DatePickerRange(id="date-range", min_date_allowed=DATE_MIN, max_date_allowed=DATE_MAX, start_date=DATE_MIN, end_date=DATE_MAX, display_format="DD MMM YYYY", style={"backgroundColor":"white","borderRadius":"5px"})], md=4),
            dbc.Col([html.Label("Supplier", style={"fontSize":"11px","color":MUTED}), dcc.Dropdown(id="supplier-filter", options=SUPPLIER_OPTIONS, value="ALL", clearable=False)], md=4),
            dbc.Col([html.Label("Material category", style={"fontSize":"11px","color":MUTED}), dcc.Dropdown(id="category-filter", options=CATEGORY_OPTIONS, value="ALL", clearable=False)], md=4),
        ], className="g-3")
    ]),
    dbc.Row(id="kpi-row", className="g-2", style={"marginBottom":"14px"}),
    dbc.Row([
        dbc.Col(dbc.Card([dbc.CardBody([html.Div("Monthly procurement spend", className="panel-title"), dcc.Graph(id="spend-trend", config={"displayModeBar":False})])], style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}"}), md=7),
        dbc.Col(dbc.Card([dbc.CardBody([html.Div("Supplier delivery performance", className="panel-title"), dcc.Graph(id="supplier-delivery", config={"displayModeBar":False})])], style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}"}), md=5),
    ], className="g-3", style={"marginBottom":"14px"}),
    dbc.Row([
        dbc.Col(dbc.Card([dbc.CardBody([html.Div("Weighted average unit cost by material", className="panel-title"), dcc.Graph(id="material-cost", config={"displayModeBar":False})])], style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}"}), md=6),
        dbc.Col(dbc.Card([dbc.CardBody([html.Div("Quality inspection overview — date-filtered; not linked to supplier IDs", className="panel-title"), dcc.Graph(id="quality-overview", config={"displayModeBar":False})])], style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}"}), md=6),
    ], className="g-3", style={"marginBottom":"14px"}),
    dbc.Card([dbc.CardBody([
        html.Div("Supplier risk scorecard", className="panel-title"),
        html.Div("Screening index: 50% late-order rate + 35% rejection rate normalized to 5% + 15% average late days normalized to 10 days. High ≥ 60; Medium ≥ 35; Low < 35. These are configurable screening thresholds, not a formal audit or forecast.", style={"fontSize":"11px","color":MUTED,"marginBottom":"8px"}),
        dash_table.DataTable(id="supplier-table", page_size=12, sort_action="native", filter_action="native", style_as_list_view=True,
            style_header={"backgroundColor":"#172943","color":"#b9d8ff","fontWeight":"700","border":"1px solid #263a56","fontSize":"11px","whiteSpace":"normal"},
            style_cell={"backgroundColor":PANEL,"color":TEXT,"border":"1px solid #263a56","fontSize":"11px","padding":"8px","textAlign":"left","maxWidth":"220px","whiteSpace":"normal"},
            style_data_conditional=[{"if":{"filter_query":"{Risk Level} = 'High'","column_id":"Risk Level"},"backgroundColor":"#7f1d1d","color":"#fff"},{"if":{"filter_query":"{Risk Level} = 'Medium'","column_id":"Risk Level"},"backgroundColor":"#78350f","color":"#fff"}]),
        html.Div(style={"display":"flex","gap":"10px","marginTop":"12px","flexWrap":"wrap"}, children=[
            dbc.Button("Export filtered purchase orders (CSV)", id="export-btn", color="primary", outline=True, size="sm"),
            dcc.Download(id="download-data"),
            dbc.Button("Export supplier scorecard (CSV)", id="export-score-btn", color="info", outline=True, size="sm"),
            dcc.Download(id="download-score"),
        ])
    ])], style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}","marginBottom":"14px"}),
    html.Div("DATA NOTE: Procurement, supplier, and QC records are modeled training data. Supplier names are anonymized. Quality.csv has no Supplier_ID, so quality defects are reported separately and are not attributed to individual suppliers.", style={"backgroundColor":"#152338","borderLeft":f"3px solid {TEAL}","padding":"10px 12px","fontSize":"10px","color":"#afc3e2","borderRadius":"5px"})
])

# Common chart styling

def style_fig(fig, height=300):
    fig.update_layout(template="plotly_dark", paper_bgcolor=PANEL, plot_bgcolor=PANEL, font={"color":TEXT,"size":10}, margin={"l":35,"r":15,"t":25,"b":45}, height=height, legend={"orientation":"h","y":1.08,"x":0})
    fig.update_xaxes(gridcolor="#24364e", zerolinecolor="#24364e")
    fig.update_yaxes(gridcolor="#24364e", zerolinecolor="#24364e")
    return fig

def get_filtered(start, end, supplier, category):
    d = orders.copy()
    if start:
        d = d[d["Order_Date"] >= pd.to_datetime(start)]
    if end:
        d = d[d["Order_Date"] < pd.to_datetime(end) + pd.Timedelta(days=1)]
    if supplier and supplier != "ALL":
        d = d[d["Supplier_ID"] == supplier]
    if category and category != "ALL":
        d = d[d["Material_Category"] == category]
    return d

def make_kpi(title, value, note):
    return dbc.Col(dbc.Card(dbc.CardBody([
        html.Div(title.upper(), style={"fontSize":"9px","letterSpacing":".7px","color":MUTED,"fontWeight":"700"}),
        html.Div(value, style={"fontSize":"23px","fontWeight":"800","color":TEXT,"marginTop":"6px","lineHeight":"1.15"}),
        html.Div(note, style={"fontSize":"9px","color":TEAL,"marginTop":"6px"}),
    ]), style={"backgroundColor":PANEL,"border":f"1px solid {BORDER}","borderRadius":"9px","minHeight":"105px"}), md=2, sm=4, xs=6)

@app.callback(
    Output("kpi-row","children"), Output("spend-trend","figure"), Output("supplier-delivery","figure"),
    Output("material-cost","figure"), Output("quality-overview","figure"), Output("supplier-table","data"), Output("supplier-table","columns"),
    Input("date-range","start_date"), Input("date-range","end_date"), Input("supplier-filter","value"), Input("category-filter","value")
)
def update_dashboard(start, end, supplier, category):
    d = get_filtered(start, end, supplier, category)
    total_spend = d["PO_Value_EGP"].sum()
    po_count = d["PO_ID"].nunique()
    late_rate = d["Late_Flag"].mean()*100 if len(d) else 0
    received = d["Receipt_Qty"].sum()
    reject_rate = d["Rejected_Qty"].sum()/received*100 if received else 0
    avg_delay = d.loc[d["Delay_Days"] > 0, "Delay_Days"].mean() if (d["Delay_Days"] > 0).any() else 0
    kpis = [
        make_kpi("Procurement spend", f"EGP {total_spend/1e6:,.1f}M", "Ordered quantity × unit cost"),
        make_kpi("Purchase orders", f"{po_count:,}", "Unique PO records"),
        make_kpi("Late order rate", f"{late_rate:.1f}%", "Actual receipt after promised date"),
        make_kpi("Qty rejection rate", f"{reject_rate:.2f}%", "Rejected ÷ received quantity"),
        make_kpi("Avg late days", f"{avg_delay:.1f}", "Among late orders only"),
        make_kpi("Suppliers in view", f"{d['Supplier_ID'].nunique():,}", "Within current filters"),
    ]
    # Spend trend by order month
    if len(d):
        monthly = d.groupby("Order_Month", as_index=False).agg(Spend_EGP=("PO_Value_EGP","sum"))
        fig_spend = px.line(monthly, x="Order_Month", y="Spend_EGP", markers=True, labels={"Order_Month":"Order month","Spend_EGP":"Spend (EGP)"})
    else:
        fig_spend = px.line(title="No data for selected filters")
    style_fig(fig_spend, 300)
    fig_spend.update_traces(line={"color":ACCENT,"width":3}, marker={"size":5})
    fig_spend.update_yaxes(tickformat="~s")

    # Supplier scorecard; do not mix categories with different units in cost comparisons
    if len(d):
        sg = d.groupby(["Supplier_ID","Supplier_Name"], as_index=False).agg(
            Purchase_Orders=("PO_ID","nunique"), Spend_EGP=("PO_Value_EGP","sum"),
            Late_Order_Rate_Pct=("Late_Flag", lambda x: x.mean()*100),
            Rejected_Qty=("Rejected_Qty","sum"), Received_Qty=("Receipt_Qty","sum"),
            Avg_Positive_Delay_Days=("Delay_Days", lambda x: x[x>0].mean() if (x>0).any() else 0)
        )
        sg["Rejection_Rate_Pct"] = np.where(sg["Received_Qty"]>0, sg["Rejected_Qty"]/sg["Received_Qty"]*100, 0)
        # Risk index = 50% late-order rate + 35% rejection rate normalized against 5% + 15% delay severity normalized against 10 days.
        sg["Risk_Score"] = (0.50*sg["Late_Order_Rate_Pct"] + 0.35*np.clip(sg["Rejection_Rate_Pct"]/5*100,0,100) + 0.15*np.clip(sg["Avg_Positive_Delay_Days"]/10*100,0,100)).clip(0,100)
        sg["Risk Level"] = np.select([sg["Risk_Score"]>=60, sg["Risk_Score"]>=35], ["High","Medium"], default="Low")
        sg = sg.sort_values("Risk_Score", ascending=False)
        fig_delivery = px.bar(sg.sort_values("Late_Order_Rate_Pct"), x="Late_Order_Rate_Pct", y="Supplier_ID", orientation="h", color="Late_Order_Rate_Pct", color_continuous_scale="Tealrose", hover_data={"Supplier_Name":True,"Purchase_Orders":True,"Spend_EGP":":,.0f","Avg_Positive_Delay_Days":":.1f"}, labels={"Late_Order_Rate_Pct":"Late orders (%)","Supplier_ID":"Supplier"})
        fig_delivery.update_layout(coloraxis_showscale=False)
        table = sg.copy()
        table["Spend_EGP"] = table["Spend_EGP"].round(2)
        for c in ["Late_Order_Rate_Pct","Rejection_Rate_Pct","Avg_Positive_Delay_Days","Risk_Score"]:
            table[c] = table[c].round(2)
        table = table.rename(columns={"Supplier_ID":"Supplier ID","Supplier_Name":"Supplier","Purchase_Orders":"POs","Spend_EGP":"Spend (EGP)","Late_Order_Rate_Pct":"Late Orders %","Rejection_Rate_Pct":"Rejected Qty %","Avg_Positive_Delay_Days":"Avg Late Days","Risk_Score":"Risk Score"})
        table = table[["Supplier ID","Supplier","POs","Spend (EGP)","Late Orders %","Rejected Qty %","Avg Late Days","Risk Score","Risk Level"]]
        table_data = table.to_dict("records")
        table_cols = [{"name":c,"id":c} for c in table.columns]
    else:
        fig_delivery = px.bar(title="No data for selected filters")
        table_data, table_cols = [], []
    style_fig(fig_delivery, 300)
    fig_delivery.update_layout(margin={"l":55,"r":10,"t":25,"b":40})
    fig_delivery.update_xaxes(range=[0, max(10, float(d.groupby('Supplier_ID')['Late_Flag'].mean().max()*100 if len(d) else 10)*1.1)])

    # Weighted average unit cost by material, grouped by material to avoid mixing units
    if len(d):
        cost = d.groupby(["Material_Name","Unit"], as_index=False).apply(lambda g: pd.Series({"Weighted_Avg_Cost_EGP": (g["Ordered_Qty"]*g["Unit_Cost_EGP"]).sum()/g["Ordered_Qty"].sum() if g["Ordered_Qty"].sum() else np.nan, "POs":g["PO_ID"].nunique()}), include_groups=False).reset_index(drop=True)
        cost = cost.dropna(subset=["Weighted_Avg_Cost_EGP"]).sort_values("Weighted_Avg_Cost_EGP", ascending=True)
        fig_cost = px.bar(cost, x="Weighted_Avg_Cost_EGP", y="Material_Name", color="Unit", orientation="h", hover_data={"POs":True}, labels={"Weighted_Avg_Cost_EGP":"Weighted average unit cost (EGP)","Material_Name":"Material"})
    else:
        fig_cost = px.bar(title="No data for selected filters")
    style_fig(fig_cost, 300)

    # Quality is intentionally independent because there is no supplier key in Quality.csv
    q = quality.copy()
    if start:
        q = q[q["Inspection_Date"] >= pd.to_datetime(start)]
    if end:
        q = q[q["Inspection_Date"] < pd.to_datetime(end) + pd.Timedelta(days=1)]
    qsum = q.groupby("Root_Cause", as_index=False).agg(Estimated_Loss_EGP=("Estimated_Loss_EGP","sum"), Rejected_Qty=("Rejected_Qty","sum"))
    qsum = qsum.sort_values("Estimated_Loss_EGP", ascending=True).tail(8)
    fig_quality = px.bar(qsum, x="Estimated_Loss_EGP", y="Root_Cause", orientation="h", color="Estimated_Loss_EGP", color_continuous_scale="Reds", labels={"Estimated_Loss_EGP":"Estimated loss (EGP)","Root_Cause":"Root cause"})
    fig_quality.update_layout(coloraxis_showscale=False)
    style_fig(fig_quality, 300)
    return kpis, fig_spend, fig_delivery, fig_cost, fig_quality, table_data, table_cols

@app.callback(
    Output("download-data","data"),
    Input("export-btn","n_clicks"),
    State("date-range","start_date"), State("date-range","end_date"), State("supplier-filter","value"), State("category-filter","value"),
    prevent_initial_call=True
)
def export_filtered(n, start, end, supplier, category):
    d = get_filtered(start, end, supplier, category)
    export_df = d.drop(columns=["Order_Month","Order_Month_Label","Late_Flag","On_Time_Flag","Receipt_Qty","Reject_Rate_Pct","PO_Value_EGP","Delay_Days"], errors="ignore")
    return dcc.send_string("\ufeff" + export_df.to_csv(index=False), "app07_filtered_purchase_orders.csv", type="text/csv")

@app.callback(
    Output("download-score","data"),
    Input("export-score-btn","n_clicks"),
    State("date-range","start_date"), State("date-range","end_date"), State("supplier-filter","value"), State("category-filter","value"),
    prevent_initial_call=True
)
def export_scorecard(n, start, end, supplier, category):
    d = get_filtered(start, end, supplier, category)
    if d.empty:
        score = pd.DataFrame(columns=["Supplier_ID","Supplier_Name","Purchase_Orders","Spend_EGP","Late_Order_Rate_Pct","Rejection_Rate_Pct","Avg_Positive_Delay_Days","Risk_Score","Risk Level"])
    else:
        score = d.groupby(["Supplier_ID","Supplier_Name"], as_index=False).agg(
            Purchase_Orders=("PO_ID","nunique"), Spend_EGP=("PO_Value_EGP","sum"),
            Late_Order_Rate_Pct=("Late_Flag", lambda x:x.mean()*100),
            Rejected_Qty=("Rejected_Qty","sum"), Received_Qty=("Receipt_Qty","sum"),
            Avg_Positive_Delay_Days=("Delay_Days", lambda x:x[x>0].mean() if (x>0).any() else 0))
        score["Rejection_Rate_Pct"] = np.where(score["Received_Qty"]>0, score["Rejected_Qty"]/score["Received_Qty"]*100, 0)
        score["Risk_Score"] = (0.50*score["Late_Order_Rate_Pct"] + 0.35*np.clip(score["Rejection_Rate_Pct"]/5*100,0,100) + 0.15*np.clip(score["Avg_Positive_Delay_Days"]/10*100,0,100)).clip(0,100)
        score["Risk Level"] = np.select([score["Risk_Score"]>=60, score["Risk_Score"]>=35],["High","Medium"],default="Low")
        score = score.drop(columns=["Rejected_Qty","Received_Qty"]).sort_values("Risk_Score",ascending=False)
    return dcc.send_string("\ufeff" + score.to_csv(index=False), "app07_supplier_risk_scorecard.csv", type="text/csv")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8070)
