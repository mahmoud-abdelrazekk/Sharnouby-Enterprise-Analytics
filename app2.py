import os
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. Helper Functions & Strict Validation
# ==========================================

def find_and_rename_column(df, candidate_names, target_name):
    """
    البحث عن عمود بين أسماء محتملة وتوحيد اسمه للـ Target Name
    """
    df.columns = df.columns.str.strip()
    for col in candidate_names:
        if col in df.columns:
            if col != target_name:
                df.rename(columns={col: target_name}, inplace=True)
            return True
    return False

def validate_required_columns(df, required_cols, dataset_name):
    """
    التحقق من وجود الأعمدة الإلزامية ورفع الخطأ فوراً في حال غياب أي منها لتجنب البيانات الوهمية
    """
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"CRITICAL ERROR in {dataset_name}: Required column(s) {missing_cols} are missing. "
            f"Cannot proceed with implicit default values."
        )

# ==========================================
# 2. Pipeline & Data Processing
# ==========================================

def load_and_prepare_real_data():
    """
    قراءة البيانات وتطبيق القواعد الصارمة للتأكد من صحتها بدون استخدام قيم افتراضية عشوائية.
    
    BUSINESS LOGIC & ASSUMPTIONS:
    - Mandatory Validation: All core metrics including Safety_Stock and Stockout_Days are strictly required.
    - Target Stock Level Logic:
      Target Stock Level is derived as:
      Target_Level = max(Reorder_Point, (Avg_Daily_Demand * Lead_Time_Days) + Safety_Stock)
      This ensures the target replenishment buffer accounts for both maximum baseline threshold
      and cycle demand exposure during supplier lead time.
    """
    inv_path = "Inventory_History.csv"
    prod_path = "Product_Master.csv"
    loc_path = "Locations.csv"
    
    if os.path.exists(inv_path):
        df_inv = pd.read_csv(inv_path)
        
        # تنظيف أطراف المسميات من المسافات
        df_inv.columns = df_inv.columns.str.strip()
        
        # Mapping دقيق للأعمدة الحقيقية الخاصة بملفك
        find_and_rename_column(df_inv, ["Location_Name", "Location_ID", "Location"], "Location")
        find_and_rename_column(df_inv, ["SKU", "Product_ID", "Product_Name"], "SKU")
        find_and_rename_column(df_inv, ["Closing_Stock", "Opening_Stock", "Current_Stock"], "Current_Stock")
        find_and_rename_column(df_inv, ["Reorder_Point_Units", "Reorder_Point"], "Reorder_Point")
        find_and_rename_column(df_inv, ["Avg_Daily_Sales_90D", "Avg_Daily_Demand"], "Avg_Daily_Demand")
        find_and_rename_column(df_inv, ["Supplier_Lead_Time_Days", "Lead_Time_Days"], "Lead_Time_Days")
        find_and_rename_column(df_inv, ["Safety_Stock_Units", "Safety_Stock"], "Safety_Stock")
        find_and_rename_column(df_inv, ["Stockout_Days_In_Month", "Stockout_Days"], "Stockout_Days")
        
        # التحقق الصارم من وجود جميع الأعمدة الإلزامية لتفادي أي القيم افتراضية (Strict Business Validation)
        mandatory_inventory_cols = [
            "Location", "SKU", "Current_Stock", "Reorder_Point", 
            "Avg_Daily_Demand", "Lead_Time_Days", "Safety_Stock", "Stockout_Days"
        ]
        validate_required_columns(df_inv, mandatory_inventory_cols, "Inventory_History.csv")
        
    else:
        raise FileNotFoundError(f"Main inventory file not found: {inv_path}")

    # تصفية أحدث شهر
    if "Snapshot_Month" in df_inv.columns:
        df_inv["Snapshot_Month"] = pd.to_datetime(df_inv["Snapshot_Month"])
        latest_month = df_inv["Snapshot_Month"].max()
        df = df_inv[df_inv["Snapshot_Month"] == latest_month].copy()
    else:
        df = df_inv.copy()

    # دمج ملف المنتجات إن وجد
    if os.path.exists(prod_path):
        df_prod = pd.read_csv(prod_path)
        find_and_rename_column(df_prod, ["SKU", "Product_ID"], "SKU")
        find_and_rename_column(df_prod, ["Family", "Category", "Product_Family"], "Family")
        if "SKU" in df_prod.columns:
            cols_to_use = [c for c in df_prod.columns if c not in df.columns or c == "SKU"]
            df = df.merge(df_prod[cols_to_use], on="SKU", how="left")

    # دمج ملف المواقع إن وجد
    if os.path.exists(loc_path):
        df_loc = pd.read_csv(loc_path)
        find_and_rename_column(df_loc, ["Location_Name", "Location_ID", "Location"], "Location")
        if "Location" in df_loc.columns:
            cols_to_use = [c for c in df_loc.columns if c not in df.columns or c == "Location"]
            df = df.merge(df_loc[cols_to_use], on="Location", how="left")

    if "Family" not in df.columns:
        df["Family"] = "General"

    # حساب Days of Cover و Target Level
    df["Avg_Daily_Demand"] = np.where(df["Avg_Daily_Demand"] <= 0, 0.0001, df["Avg_Daily_Demand"])
    df["Days_Of_Cover"] = df["Current_Stock"] / df["Avg_Daily_Demand"]
    
    # Target Level Determination Strategy:
    # Target Stock Level is derived as the maximum of Reorder Point and (Lead-Time Demand + Safety Stock)
    if "Target_Stock" in df.columns:
        df["Target_Level"] = df["Target_Stock"]
    else:
        df["Target_Level"] = np.maximum(df["Reorder_Point"], (df["Avg_Daily_Demand"] * df["Lead_Time_Days"]) + df["Safety_Stock"])

    # تصنيف حالة المخزون
    def classify_status(row):
        if row["Current_Stock"] <= 0:
            return "STOCKOUT"
        elif row["Current_Stock"] <= row["Safety_Stock"]:
            return "CRITICAL"
        elif row["Current_Stock"] <= row["Reorder_Point"]:
            return "REPLENISH"
        else:
            return "HEALTHY"

    df["Status"] = df.apply(classify_status, axis=1)

    # حساب الاحتياج والفائض بناءً على المفهوم الدقيق للـ Threshold
    df["Need"] = np.where(df["Current_Stock"] <= df["Reorder_Point"], np.maximum(0, df["Target_Level"] - df["Current_Stock"]), 0)
    df["Surplus"] = np.maximum(0, df["Current_Stock"] - np.maximum(df["Reorder_Point"], df["Target_Level"]))

    return df

def run_transfer_and_replenishment_engine(df):
    """
    محرك النقل الداخلي وإعادة الشراء للتوزيع بين الفائض والعجز
    """
    actions = []
    skus = df["SKU"].unique()

    for sku in skus:
        sku_df = df[df["SKU"] == sku].copy()
        
        needy_locs = sku_df[sku_df["Need"] > 0].sort_values(by="Need", ascending=False)
        surplus_locs = sku_df[sku_df["Surplus"] > 0].sort_values(by="Surplus", ascending=False)
        
        available_surplus = surplus_locs.set_index("Location")["Surplus"].to_dict()

        for _, need_row in needy_locs.iterrows():
            loc_need = need_row["Location"]
            remaining_need = need_row["Need"]
            family = need_row["Family"]
            doc = need_row["Days_Of_Cover"]
            lt = need_row["Lead_Time_Days"]
            status = need_row["Status"]

            if status == "STOCKOUT" or doc < lt:
                priority = "🔴 CRITICAL"
            elif status == "CRITICAL":
                priority = "🟠 HIGH"
            elif status == "REPLENISH":
                priority = "🟡 MEDIUM"
            else:
                priority = "🟢 LOW"

            # المطابقة مع المخزون الفائض من المواقع الأخرى
            for sur_loc, sur_qty in list(available_surplus.items()):
                if remaining_need <= 0:
                    break
                if sur_qty > 0:
                    transfer_qty = min(remaining_need, sur_qty)
                    
                    actions.append({
                        "Priority": priority,
                        "From": sur_loc,
                        "To": loc_need,
                        "SKU": sku,
                        "Family": family,
                        "Current_Stock": need_row["Current_Stock"],
                        "Need": need_row["Need"],
                        "Qty": transfer_qty,
                        "Action_Type": "Internal Transfer"
                    })
                    
                    remaining_need -= transfer_qty
                    available_surplus[sur_loc] -= transfer_qty

            # الشراء الخارجي للمتبقي من النقص
            if remaining_need > 0:
                actions.append({
                    "Priority": priority,
                    "From": "External Vendor",
                    "To": loc_need,
                    "SKU": sku,
                    "Family": family,
                    "Current_Stock": need_row["Current_Stock"],
                    "Need": need_row["Need"],
                    "Qty": remaining_need,
                    "Action_Type": "External Replenishment"
                })

    return pd.DataFrame(actions)

# ==========================================
# 3. Application Setup & UI
# ==========================================

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "App 02 - Production Smart Inventory Engine"

df_inventory = load_and_prepare_real_data()
df_actions = run_transfer_and_replenishment_engine(df_inventory)

# إحداثيات المستودعات للعرض
coords = {
    "Cairo DC": {"lat": 30.0444, "lon": 31.2357},
    "Alexandria DC": {"lat": 31.2001, "lon": 29.9187},
    "Giza DC": {"lat": 30.0131, "lon": 31.2089}
}

app.layout = html.Div(style={
    "background": "linear-gradient(145deg, #020812 0%, #041324 48%, #020914 100%)",
    "minHeight": "100vh", "padding": "25px", "color": "#eef7ff", "fontFamily": "Segoe UI, sans-serif"
}, children=[
    
    # Header
    dbc.Row([
        dbc.Col([
            html.Div("PRODUCTION DECISION ENGINE • APP 02", style={"color": "#45d7ff", "letterSpacing": "2px", "fontSize": "12px", "fontWeight": "bold"}),
            html.H2("SMART INVENTORY & REPLENISHMENT", style={"fontWeight": "800", "color": "#ffffff"}),
            html.P("What should move, where, and when? ", style={"color": "#7f9bb5", "fontSize": "15px"})
        ], md=8),
        dbc.Col([
            dbc.Button("📥 Download Action Plan (CSV)", id="btn-download-csv", color="info", className="float-end mt-2", style={"fontWeight": "bold"}),
            dcc.Download(id="download-dataframe-csv")
        ], md=4)
    ], className="mb-4"),

    # Dynamic Executive KPI Cards
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("TOTAL CURRENT STOCK", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-current-stock", style={"color": "#009dff", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("AT RISK LOC-SKUS", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-at-risk", style={"color": "#ff5c7c", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("PORTFOLIO DAYS OF COVER", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-days-cover", style={"color": "#ffb703", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("STOCKOUT DAYS", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-stockout-days", style={"color": "#e63946", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("INTERNAL TRANSFER", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-internal-transfer", style={"color": "#42e6b5", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("EXTERNAL REPLENISH", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-external-replenish", style={"color": "#9d4edd", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
    ], className="mb-4"),

    # Filters
    dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Label("Location", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-location",
                    options=[{"label": "All Locations", "value": "All"}] + [{"label": str(l), "value": l} for l in df_inventory["Location"].unique()],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3),
            dbc.Col([
                html.Label("Product Family", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-family",
                    options=[{"label": "All Families", "value": "All"}] + [{"label": str(f), "value": f} for f in df_inventory["Family"].unique()],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3),
            dbc.Col([
                html.Label("Status", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-status",
                    options=[{"label": "All Statuses", "value": "All"}] + [{"label": str(s), "value": s} for s in df_inventory["Status"].unique()],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3),
            dbc.Col([
                html.Label("Action Type", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-action",
                    options=[{"label": "All Actions", "value": "All"}, {"label": "Internal Transfer", "value": "Internal Transfer"}, {"label": "External Replenishment", "value": "External Replenishment"}],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3)
        ])
    ]), style={"background": "rgba(8, 27, 48, 0.6)", "border": "1px solid rgba(49, 164, 226, 0.2)", "marginBottom": "20px"}),

    # Charts
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("A. Current Stock by Location", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-stock-location")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("B. Replenishment Need by Product Family", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-risk-family")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
    ]),

    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("C. Days of Cover vs Lead Time Risk", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-cover-reorder")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("D. Recommended Internal Transfer Routes", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-transfer-network")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
    ]),

    # Action Table
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("📋 Recommended Replenishment & Transfer Action Table", style={"color": "#42e6b5", "fontWeight": "bold"}),
            dash_table.DataTable(
                id="action-table",
                columns=[{"name": i, "id": i} for i in ["Priority", "From", "To", "SKU", "Family", "Current_Stock", "Need", "Qty", "Action_Type"]],
                style_header={'backgroundColor': '#041324', 'color': '#45d7ff', 'fontWeight': 'bold', 'border': '1px solid rgba(49, 164, 226, 0.3)'},
                style_cell={'backgroundColor': '#081b30', 'color': '#eef7ff', 'border': '1px solid rgba(49, 164, 226, 0.1)', 'textAlign': 'center', 'padding': '10px'},
                style_data_conditional=[
                    {'if': {'filter_query': '{Action_Type} = "Internal Transfer"'}, 'color': '#42e6b5'},
                    {'if': {'filter_query': '{Action_Type} = "External Replenishment"'}, 'color': '#ff5c7c'}
                ],
                page_size=10
            )
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=12)
    ])
])

# ==========================================
# 4. Reactive Callbacks
# ==========================================

@app.callback(
    [Output("kpi-current-stock", "children"),
     Output("kpi-at-risk", "children"),
     Output("kpi-days-cover", "children"),
     Output("kpi-stockout-days", "children"),
     Output("kpi-internal-transfer", "children"),
     Output("kpi-external-replenish", "children"),
     Output("chart-stock-location", "figure"),
     Output("chart-risk-family", "figure"),
     Output("chart-cover-reorder", "figure"),
     Output("chart-transfer-network", "figure"),
     Output("action-table", "data")],
    [Input("filter-location", "value"),
     Input("filter-family", "value"),
     Input("filter-status", "value"),
     Input("filter-action", "value")]
)
def update_dashboard(loc, family, status, action_type):
    f_inv = df_inventory.copy()
    if loc != "All":
        f_inv = f_inv[f_inv["Location"] == loc]
    if family != "All":
        f_inv = f_inv[f_inv["Family"] == family]
    if status != "All":
        f_inv = f_inv[f_inv["Status"] == status]
        
    f_act = df_actions.copy() if not df_actions.empty else pd.DataFrame(columns=["Priority", "From", "To", "SKU", "Family", "Current_Stock", "Need", "Qty", "Action_Type"])
    if not f_act.empty:
        if loc != "All":
            f_act = f_act[(f_act["From"] == loc) | (f_act["To"] == loc)]
        if family != "All":
            f_act = f_act[f_act["Family"] == family]
        if action_type != "All":
            f_act = f_act[f_act["Action_Type"] == action_type]

    # حساب KPIs بالمعادلة الموزونة Portfolio-Level Days of Cover
    cur_stock_sum = f_inv['Current_Stock'].sum()
    daily_demand_sum = f_inv['Avg_Daily_Demand'].sum()
    
    cur_stock = f"{round(cur_stock_sum):,}"
    at_risk_count = f"{len(f_inv[f_inv['Status'].isin(['STOCKOUT', 'CRITICAL', 'REPLENISH'])]):,}"
    
    # Portfolio-Level Weighted Days of Cover
    portfolio_doc = (cur_stock_sum / daily_demand_sum) if daily_demand_sum > 0 else 0.0
    avg_doc = f"{portfolio_doc:.1f}"
    
    stockout_days = f"{round(f_inv['Stockout_Days'].sum()):,}"
    
    internal_qty = f"{f_act[f_act['Action_Type'] == 'Internal Transfer']['Qty'].sum():,}" if not f_act.empty else "0"
    external_qty = f"{f_act[f_act['Action_Type'] == 'External Replenishment']['Qty'].sum():,}" if not f_act.empty else "0"

    # Chart A
    fig_a = px.bar(
        f_inv.groupby("Location", as_index=False)["Current_Stock"].sum(),
        x="Location", y="Current_Stock", text="Current_Stock",
        template="plotly_dark", color_discrete_sequence=["#009dff"]
    ).update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))

    # Chart B
    risk_df = f_inv[f_inv["Need"] > 0].groupby("Family", as_index=False)["Need"].sum()
    fig_b = px.bar(
        risk_df, x="Family", y="Need", text="Need",
        template="plotly_dark", color_discrete_sequence=["#ff5c7c"]
    ).update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))

    # Chart C
    fig_c = px.scatter(
        f_inv, x="Days_Of_Cover", y="Current_Stock", color="Status", size="Need",
        hover_data=["SKU", "Location", "Lead_Time_Days"], template="plotly_dark",
        labels={"Days_Of_Cover": "Days of Cover", "Current_Stock": "Current Stock Units"},
        color_discrete_map={"STOCKOUT": "#e63946", "CRITICAL": "#ff5c7c", "REPLENISH": "#ffb703", "HEALTHY": "#42e6b5"}
    ).update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))

    # Chart D
    fig_d = go.Figure()
    for loc_name, pos in coords.items():
        fig_d.add_trace(go.Scattergeo(
            lat=[pos["lat"]], lon=[pos["lon"]],
            mode='markers+text', text=loc_name, textposition="top center",
            marker=dict(size=10, color='#009dff')
        ))
    
    if not f_act.empty:
        transfers = f_act[f_act["Action_Type"] == "Internal Transfer"]
        for _, row in transfers.iterrows():
            if row["From"] in coords and row["To"] in coords:
                start = coords[row["From"]]
                end = coords[row["To"]]
                fig_d.add_trace(go.Scattergeo(
                    lat=[start["lat"], end["lat"]],
                    lon=[start["lon"], end["lon"]],
                    mode='lines',
                    line=dict(width=3, color='#42e6b5'),
                    hoverinfo='text',
                    text=f"{row['SKU']}: {row['Qty']} units ({row['From']} -> {row['To']})"
                ))

    fig_d.update_layout(
        geo=dict(scope='africa', center=dict(lat=30.5, lon=30.5), projection_scale=8, showland=True, landcolor="#041324"),
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=280
    )

    return (cur_stock, at_risk_count, avg_doc, stockout_days, internal_qty, external_qty,
            fig_a, fig_b, fig_c, fig_d, f_act.to_dict('records'))

@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn-download-csv", "n_clicks"),
    prevent_initial_call=True
)
def export_csv(n_clicks):
    return dcc.send_data_frame(df_actions.to_csv, "Replenishment_Action_Plan.csv", index=False)

if __name__ == '__main__':
    app.run(debug=True, port=8052)