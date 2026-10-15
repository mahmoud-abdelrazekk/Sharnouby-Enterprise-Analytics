"""App 02 — AI Multi-Horizon Demand Forecasting & Inventory Optimization Engine

Features:
- Multi-Horizon Forecasting: 30-Day (Oct), 60-Day (Nov), and 90-Day (Dec Peak Season)
- Strategic ABC / XYZ 9-Box Inventory Segmentation Matrix
- Dynamic Safety Stock & Reorder Point (ROP) Calculator with Target Service Level Control
- Inter-Branch Stock Rebalancing (Cross-Location Transfer Diagnostics)
- Interactive 36-Month Time Series Historical vs. AI Forecast Visualizer
- Ultra-Clear High-Contrast Enterprise Theme (Stripe/Linear Aesthetics)
"""
import os
from pathlib import Path
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. Paths & Data Loading
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

def resolve_file(filename):
    candidates = [
        BASE_DIR / filename,
        BASE_DIR / "outputs" / "final_demand_and_inventory_plan" / filename,
        BASE_DIR / "files" / filename,
        BASE_DIR / "data" / filename
    ]
    for c in candidates:
        if c.exists():
            return c
    return BASE_DIR / filename

plan_path = resolve_file("multi_horizon_inventory_forecast_plan.csv")
history_path = resolve_file("Inventory_History.csv")
products_path = resolve_file("Product_Master.csv")
locations_path = resolve_file("Locations.csv")

if plan_path.exists():
    df_plan = pd.read_csv(plan_path)
else:
    df_inv = pd.read_csv(history_path)
    df_plan = df_inv[df_inv['Snapshot_Month'] == df_inv['Snapshot_Month'].max()].copy()
    df_plan['Forecast_M1_Oct'] = (df_plan['Avg_Daily_Sales_90D'] * 30).round().astype(int)
    df_plan['Forecast_M2_Nov'] = (df_plan['Forecast_M1_Oct'] * 1.15).round().astype(int)
    df_plan['Forecast_M3_Dec'] = (df_plan['Forecast_M1_Oct'] * 1.35).round().astype(int)
    df_plan['Forecast_Cumulative_90D'] = df_plan['Forecast_M1_Oct'] + df_plan['Forecast_M2_Nov'] + df_plan['Forecast_M3_Dec']
    df_plan['ABC_XYZ'] = 'AY'
    df_plan['ABC_Class'] = 'A'
    df_plan['XYZ_Class'] = 'Y'

if history_path.exists():
    df_hist = pd.read_csv(history_path)
else:
    df_hist = pd.DataFrame()

if 'Public_Retail_Price_EGP' not in df_plan.columns:
    df_plan['Public_Retail_Price_EGP'] = 500.0

df_plan['Stock_Value_EGP'] = df_plan['Closing_Stock'] * df_plan['Public_Retail_Price_EGP']

# Calculate Cross-Branch Transfer Opportunities
transfer_opps = {}
for p_id in df_plan['Product_ID'].unique():
    p_subset = df_plan[df_plan['Product_ID'] == p_id]
    stockouts = p_subset[p_subset['Closing_Stock'] == 0]
    surpluses = p_subset[p_subset['Days_of_Cover'] > 90]
    if not stockouts.empty and not surpluses.empty:
        best_surplus = surpluses.sort_values(by='Closing_Stock', ascending=False).iloc[0]
        transfer_opps[p_id] = {
            "source_loc": best_surplus['Location_Name'],
            "available_units": int(best_surplus['Closing_Stock'])
        }

df_plan['Transfer_Suggestion'] = df_plan['Product_ID'].apply(
    lambda pid: f"تحويل متاح من {transfer_opps[pid]['source_loc']} ({transfer_opps[pid]['available_units']} قطعة)"
    if pid in transfer_opps else "لا يوجد فائض بالفروع الأخرى"
)

# -----------------------------------------------------------------------------
# 2. Executive Color System (Maximum Contrast, Clarity & Beauty)
# -----------------------------------------------------------------------------
THEME = {
    # Backgrounds & Cards
    "bg": "#080d19",
    "surface": "#0f172a",
    "surface_subtle": "#131f37",
    "surface_hover": "#1c2e4f",
    "border": "#1e3252",
    "border_focus": "#38bdf8",
    
    # Ultra-clear typography hierarchy
    "text_title": "#ffffff",      # Pure crisp white for headings & values
    "text_body": "#f1f5f9",       # Clean bright silver-white for table data
    "text_accent": "#38bdf8",     # Electric Sky Blue for category tags
    "text_muted": "#94a3b8",      # Muted slate silver for subtitles & labels
    
    # Disciplined semantic highlights
    "primary": "#38bdf8",         # Sky Blue
    "success": "#10b981",         # Emerald Green
    "warning": "#f59e0b",         # Warm Amber Gold
    "danger": "#f43f5e",          # Coral Rose Red
    "purple": "#a855f7",          # Violet
}

CARD_STYLE = {
    "background": THEME["surface"],
    "border": f"1px solid {THEME['border']}",
    "borderRadius": "10px",
    "padding": "18px",
    "marginBottom": "16px",
    "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.4)"
}

def kpi_card_custom(title, value_id, subtext, accent_color):
    return html.Div(
        style={
            "background": THEME["surface"],
            "border": f"1px solid {THEME['border']}",
            "borderTop": f"3px solid {accent_color}",
            "borderRadius": "10px",
            "padding": "16px 20px",
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "space-between"
        },
        children=[
            html.Div(title, style={"fontSize": "11px", "color": THEME["text_muted"], "fontWeight": "700", "letterSpacing": "0.6px", "textTransform": "uppercase"}),
            html.Div(id=value_id, style={"fontSize": "26px", "fontWeight": "800", "color": THEME["text_title"], "margin": "8px 0 4px", "letterSpacing": "-0.5px"}),
            html.Div(subtext, style={"fontSize": "12px", "color": THEME["text_muted"]})
        ]
    )

# -----------------------------------------------------------------------------
# 3. Dash App Initialization & Custom Index String
# -----------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
app.title = "AI Demand Forecaster & Inventory Engine | Sharnouby"

app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            html, body {{
                background-color: {THEME['bg']} !important;
                color: {THEME['text_body']} !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            }}
            /* Ultra-clean custom dropdown styles */
            .Select-control {{
                background-color: {THEME['surface_subtle']} !important;
                border: 1px solid {THEME['border']} !important;
                color: {THEME['text_title']} !important;
                border-radius: 6px !important;
            }}
            .Select-placeholder, .Select--single > .Select-control .Select-value {{
                color: {THEME['text_title']} !important;
                line-height: 34px !important;
            }}
            .Select-value-label, .Select-input input {{
                color: {THEME['text_title']} !important;
            }}
            .Select-menu-outer {{
                background-color: {THEME['surface']} !important;
                border: 1px solid {THEME['border']} !important;
                box-shadow: 0 10px 30px rgba(0,0,0,0.7) !important;
                z-index: 9999 !important;
            }}
            .Select-option {{
                background-color: {THEME['surface']} !important;
                color: {THEME['text_body']} !important;
                padding: 10px 14px !important;
            }}
            .Select-option:hover, .Select-option.is-focused {{
                background-color: {THEME['surface_hover']} !important;
                color: {THEME['primary']} !important;
            }}
            .Select-arrow {{
                border-color: {THEME['primary']} transparent transparent !important;
            }}
            /* Radio and Slider styles */
            .form-check-input:checked {{
                background-color: {THEME['primary']} !important;
                border-color: {THEME['primary']} !important;
            }}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
"""

# Filter options
location_opts = [{"label": "All Locations (كافة الفروع والمستودعات)", "value": "All"}] + [
    {"label": f"{r.Location_Name} ({r.Location_ID})", "value": r.Location_ID}
    for r in df_plan[["Location_ID", "Location_Name"]].drop_duplicates().sort_values("Location_Name").itertuples(index=False)
]

family_opts = [{"label": "All Product Families (كافة العائلات)", "value": "All"}] + [
    {"label": fam, "value": fam} for fam in sorted(df_plan["Product_Family"].dropna().unique())
]

abc_xyz_opts = [{"label": "All ABC/XYZ Segments (كافة الشرائح)", "value": "All"}] + [
    {"label": f"{cat} Segment", "value": cat} for cat in sorted(df_plan["ABC_XYZ"].dropna().unique())
]

sku_visualizer_opts = [
    {"label": f"{r.Product_Name} ({r.Product_ID}) - {r.Product_Family}", "value": r.Product_ID}
    for r in df_plan[["Product_ID", "Product_Name", "Product_Family"]].drop_duplicates().sort_values("Product_Name").itertuples(index=False)
]

app.layout = html.Div(
    style={"background": THEME["bg"], "color": THEME["text_body"], "minHeight": "100vh", "padding": "24px 28px"},
    children=[
        # Top Header Bar
        html.Div(
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "paddingBottom": "18px",
                "marginBottom": "22px",
                "borderBottom": f"1px solid {THEME['border']}"
            },
            children=[
                html.Div([
                    html.Div("SHARNOUBY ENTERPRISE • AI SUPPLY CHAIN INTELLIGENCE", style={"fontSize": "11px", "letterSpacing": "1.5px", "color": THEME["primary"], "fontWeight": "700"}),
                    html.H2("Multi-Horizon Demand Forecaster & Replenishment Engine", style={"margin": "4px 0", "fontSize": "24px", "fontWeight": "800", "color": THEME["text_title"]}),
                    html.Div("محرك التنبؤ الذكي بالطلب متعدد الآفاق (30/60/90 يوماً) وإعادة الطلب وحماية الهوامش", style={"color": THEME["text_muted"], "fontSize": "13px"})
                ]),
                html.Div(
                    style={"display": "flex", "gap": "10px", "alignItems": "center"},
                    children=[
                        dbc.Button(
                            "📥 Download Replenishment Plan (CSV)",
                            id="btn-download-plan",
                            color="info",
                            style={"backgroundColor": THEME["surface_subtle"], "borderColor": THEME["border"], "color": THEME["primary"], "fontWeight": "700", "fontSize": "12px", "padding": "8px 16px"}
                        ),
                        dcc.Download(id="download-plan-csv"),
                    ]
                )
            ]
        ),

        # Control Deck: Horizon & Service Level Simulator
        dbc.Row([
            dbc.Col([
                html.Div(
                    style={
                        "background": THEME["surface"],
                        "border": f"1px solid {THEME['border']}",
                        "borderRadius": "10px",
                        "padding": "16px 20px",
                        "marginBottom": "16px"
                    },
                    children=[
                        dbc.Row([
                            # 1. Horizon Selector
                            dbc.Col([
                                html.Label("1. Forecast Horizon (أفق التنبؤ بالطلب)", style={"fontSize": "12px", "fontWeight": "700", "color": "#38bdf8", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                                dcc.RadioItems(
                                    id="sel-horizon",
                                    options=[
                                        {"label": " 30-Day Plan (October 2026)", "value": "30D"},
                                        {"label": " 60-Day Plan (November 2026)", "value": "60D"},
                                        {"label": " 90-Day Peak Season (Dec Cumulative)", "value": "90D"},
                                    ],
                                    value="30D",
                                    inline=True,
                                    inputStyle={"marginRight": "6px", "marginLeft": "16px"},
                                    labelStyle={"color": "#ffffff", "fontWeight": "600"},
                                    style={"fontSize": "13px", "color": THEME["text_body"], "marginTop": "8px"}
                                )
                            ], md=6, className="mb-2"),

                            # 2. Service Level Z-Score Selector
                            dbc.Col([
                                html.Label("2. Target Service Level (مستوى الخدمة وحماية المخزون)", style={"fontSize": "12px", "fontWeight": "700", "color": "#10b981", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                                dcc.RadioItems(
                                    id="sel-service-level",
                                    options=[
                                        {"label": " 90% (Lean Capital / Z=1.28)", "value": 1.28},
                                        {"label": " 95% (Standard Balanced / Z=1.65)", "value": 1.65},
                                        {"label": " 99% (Maximum Protection / Z=2.33)", "value": 2.33},
                                    ],
                                    value=1.65,
                                    inline=True,
                                    inputStyle={"marginRight": "6px", "marginLeft": "16px"},
                                    labelStyle={"color": "#ffffff", "fontWeight": "600"},
                                    style={"fontSize": "13px", "color": THEME["text_body"], "marginTop": "8px"}
                                )
                            ], md=6, className="mb-2"),
                        ])
                    ]
                )
            ], width=12)
        ]),

        # Top Executive KPI Cards (High Contrast, Crisp White Numbers)
        dbc.Row([
            dbc.Col(kpi_card_custom("CURRENT INVENTORY VALUE", "kpi-stock-units", "رصيد المخزون الحالي بالقطع والقيمة", THEME["primary"]), width=12, md=3, className="mb-3"),
            dbc.Col(kpi_card_custom("AI PROJECTED DEMAND", "kpi-forecast-units", "إجمالي الطلب المتوقع للأفق المختار", THEME["text_accent"]), width=12, md=3, className="mb-3"),
            dbc.Col(kpi_card_custom("CRITICAL RISK SKUs (P1 / P2)", "kpi-risk-skus", "نفاذ فوري أو اختراق وشيك لفترة التوريد", THEME["danger"]), width=12, md=3, className="mb-3"),
            dbc.Col(kpi_card_custom("TRAPPED CAPITAL IN EXCESS (>60D)", "kpi-trapped-capital", "سيولة نقدية مجمدة في أصناف راكدة", THEME["warning"]), width=12, md=3, className="mb-3"),
        ], className="mb-2"),

        # Filter Bar
        html.Div(
            style={
                "background": THEME["surface"],
                "border": f"1px solid {THEME['border']}",
                "borderRadius": "10px",
                "padding": "14px 20px",
                "marginBottom": "16px"
            },
            children=[
                dbc.Row([
                    dbc.Col([
                        html.Label("Location (الفرع / المستودع)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                        dcc.Dropdown(
                            id="filter-location",
                            options=location_opts,
                            value="All",
                            clearable=False,
                            style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                        )
                    ], md=4, className="mb-2"),
                    dbc.Col([
                        html.Label("Product Family (فئة المنتج)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                        dcc.Dropdown(
                            id="filter-family",
                            options=family_opts,
                            value="All",
                            clearable=False,
                            style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                        )
                    ], md=4, className="mb-2"),
                    dbc.Col([
                        html.Label("ABC / XYZ Segment (شريحة الأهمية والتذبذب)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                        dcc.Dropdown(
                            id="filter-abc-xyz",
                            options=abc_xyz_opts,
                            value="All",
                            clearable=False,
                            style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                        )
                    ], md=4, className="mb-2"),
                ])
            ]
        ),

        # Section 1: Visual Analytics (9-Box Heatmap & Seasonality Chart)
        dbc.Row([
            # 9-Box Heatmap
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div([
                            html.H4("Strategic ABC / XYZ 9-Box Matrix", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                            html.Div("توزيع المخزون بين القيمة المالية (ABC) وتذبذب الطلب والموسمية (XYZ)", style={"fontSize": "12px", "color": THEME["text_muted"], "marginBottom": "10px"})
                        ]),
                        dcc.Graph(id="chart-abc-xyz-matrix", style={"height": "285px"}, config={"displayModeBar": False})
                    ]
                )
            ], width=12, lg=5),

            # Historical vs Multi-Horizon Forecast Chart
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "8px"},
                            children=[
                                html.Div([
                                    html.H4("SKU Time-Series: 36M History vs AI Multi-Horizon Forecast", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                                    html.Div("الرسم البياني لتاريخ المبيعات الشهري والتنبؤ الذكي لـ (أكتوبر، نوفمبر، ديسمبر 2026)", style={"fontSize": "12px", "color": THEME["text_muted"]})
                                ]),
                                html.Div(
                                    dcc.Dropdown(
                                        id="sel-visualizer-sku",
                                        options=sku_visualizer_opts,
                                        value="P033",
                                        clearable=False,
                                        style={"width": "280px", "backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                                    )
                                )
                            ]
                        ),
                        dcc.Graph(id="chart-sku-time-series", style={"height": "285px"}, config={"displayModeBar": False})
                    ]
                )
            ], width=12, lg=7)
        ]),

        # Section 2: Master Replenishment Action Table (Ultra-Legible)
        dbc.Row([
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
                            children=[
                                html.Div([
                                    html.H4("AI Dynamic Replenishment & Order Execution Table", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                                    html.Div("جدول قرارات إعادة الطلب الذكية، سد النواقص، واقتراحات المناقلة بين الفروع", style={"fontSize": "12px", "color": THEME["text_muted"]})
                                ]),
                                html.Div(id="table-count-badge", style={"fontSize": "12px", "color": THEME["primary"], "fontWeight": "700"})
                            ]
                        ),
                        dash_table.DataTable(
                            id="master-replenishment-table",
                            columns=[
                                {"name": "أولوية التحرك (Priority)", "id": "Priority_Label"},
                                {"name": "الموقع (Location)", "id": "Location_Name"},
                                {"name": "المنتج (Product)", "id": "Product_Name"},
                                {"name": "الفئة (Family)", "id": "Product_Family"},
                                {"name": "شريحة ABC/XYZ", "id": "ABC_XYZ"},
                                {"name": "الرصيد الحالي (Stock)", "id": "Closing_Stock"},
                                {"name": "الطلب المتوقع (Forecast)", "id": "Active_Forecast"},
                                {"name": "أيام التغطية (Cover)", "id": "Days_of_Cover"},
                                {"name": "فترة التوريد (Lead Days)", "id": "Supplier_Lead_Time_Days"},
                                {"name": "مخزون الأمان الذكي (SS)", "id": "Safety_Stock_Calc"},
                                {"name": "نقطة إعادة الطلب (ROP)", "id": "Reorder_Point_Calc"},
                                {"name": "كمية الطلب الموصى بها (Order Units)", "id": "Replenishment_Suggestion"},
                                {"name": "قيمة الطلب (EGP)", "id": "Order_Cost_EGP"},
                                {"name": "مناقلة من الفروع (Inter-Branch)", "id": "Transfer_Suggestion"},
                            ],
                            data=[],
                            page_size=15,
                            sort_action="native",
                            filter_action="native",
                            style_table={"overflowX": "auto", "maxHeight": "600px"},
                            style_header={
                                "backgroundColor": "#131f37",
                                "color": THEME["primary"],
                                "fontWeight": "700",
                                "fontSize": "11px",
                                "border": f"1px solid {THEME['border']}",
                                "textAlign": "center",
                                "padding": "12px 10px",
                                "textTransform": "uppercase"
                            },
                            style_cell={
                                "backgroundColor": "#0b1424",
                                "color": THEME["text_body"],
                                "fontSize": "12px",
                                "padding": "10px 12px",
                                "border": "1px solid rgba(30, 50, 82, 0.4)",
                                "textAlign": "center"
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#0e182b"
                                },
                                {
                                    "if": {"filter_query": '{Priority_Label} contains "P1"'},
                                    "color": THEME["danger"],
                                    "fontWeight": "800",
                                    "backgroundColor": "rgba(244, 63, 94, 0.08)"
                                },
                                {
                                    "if": {"filter_query": '{Priority_Label} contains "P2"'},
                                    "color": THEME["warning"],
                                    "fontWeight": "700",
                                    "backgroundColor": "rgba(245, 158, 11, 0.06)"
                                },
                                {
                                    "if": {"filter_query": '{Priority_Label} contains "P4"'},
                                    "color": THEME["purple"],
                                    "fontWeight": "700"
                                },
                                {
                                    "if": {"column_id": "Replenishment_Suggestion"},
                                    "color": THEME["success"],
                                    "fontWeight": "800"
                                }
                            ]
                        )
                    ]
                )
            ], width=12)
        ])
    ]
)

# -----------------------------------------------------------------------------
# 4. Callbacks: Dynamic Calculation & Interactivity
# -----------------------------------------------------------------------------

@app.callback(
    Output("kpi-stock-units", "children"),
    Output("kpi-forecast-units", "children"),
    Output("kpi-risk-skus", "children"),
    Output("kpi-trapped-capital", "children"),
    Output("chart-abc-xyz-matrix", "figure"),
    Output("master-replenishment-table", "data"),
    Output("table-count-badge", "children"),
    Input("sel-horizon", "value"),
    Input("sel-service-level", "value"),
    Input("filter-location", "value"),
    Input("filter-family", "value"),
    Input("filter-abc-xyz", "value")
)
def update_inventory_engine(horizon, z_score, loc_filter, fam_filter, abc_filter):
    dff = df_plan.copy()

    # Apply Filters
    if loc_filter != "All":
        dff = dff[dff["Location_ID"] == loc_filter]
    if fam_filter != "All":
        dff = dff[dff["Product_Family"] == fam_filter]
    if abc_filter != "All":
        dff = dff[dff["ABC_XYZ"] == abc_filter]

    # Select Active Horizon Forecast
    if horizon == "30D":
        dff["Active_Forecast"] = dff["Forecast_M1_Oct"]
    elif horizon == "60D":
        dff["Active_Forecast"] = dff["Forecast_M1_Oct"] + dff["Forecast_M2_Nov"]
    else:  # 90D
        dff["Active_Forecast"] = dff["Forecast_Cumulative_90D"]

    horizon_days = 30 if horizon == "30D" else (60 if horizon == "60D" else 90)
    dff["Daily_Forecast"] = dff["Active_Forecast"] / horizon_days

    # Dynamic Safety Stock = Z * sqrt(Lead_Time) * Daily_Demand_Std
    dff["Safety_Stock_Calc"] = (
        z_score * np.sqrt(dff["Supplier_Lead_Time_Days"]) * (dff["hist_std"] / 30.0).fillna(1.0)
    ).round().astype(int)

    # Dynamic ROP = (Lead_Time * Daily_Demand) + Safety_Stock
    dff["Lead_Time_Demand"] = (dff["Daily_Forecast"] * dff["Supplier_Lead_Time_Days"]).round().astype(int)
    dff["Reorder_Point_Calc"] = dff["Lead_Time_Demand"] + dff["Safety_Stock_Calc"]

    # Recommended Order = max(0, Target - Closing_Stock)
    dff["Target_Stock"] = dff["Active_Forecast"] + dff["Safety_Stock_Calc"]
    dff["Replenishment_Suggestion"] = np.maximum(0, dff["Target_Stock"] - dff["Closing_Stock"])
    dff["Order_Cost_EGP"] = (dff["Replenishment_Suggestion"] * dff["Public_Retail_Price_EGP"] * 0.6).round().astype(int)

    # Priority Classification
    def classify_priority(row):
        if row["Closing_Stock"] == 0:
            return "P1_STOCKOUT_NOW"
        elif row["Days_of_Cover"] < row["Supplier_Lead_Time_Days"]:
            return "P2_LEAD_TIME_RISK"
        elif row["Closing_Stock"] <= row["Reorder_Point_Calc"]:
            return "P3_BELOW_REORDER_POINT"
        elif row["Days_of_Cover"] > 90:
            return "P4_SLOW_OR_OVERSTOCK"
        else:
            return "P5_HEALTHY_COVERAGE"

    dff["Priority_Label"] = dff.apply(classify_priority, axis=1)

    # KPIs
    total_stock_units = dff["Closing_Stock"].sum()
    total_stock_egp = dff["Stock_Value_EGP"].sum()
    total_forecast_units = dff["Active_Forecast"].sum()
    risk_count = (dff["Priority_Label"].isin(["P1_STOCKOUT_NOW", "P2_LEAD_TIME_RISK"])).sum()

    excess_mask = dff["Days_of_Cover"] > 60
    trapped_capital_egp = (
        (dff.loc[excess_mask, "Closing_Stock"] - (dff.loc[excess_mask, "Daily_Forecast"] * 60))
        .clip(lower=0) * dff.loc[excess_mask, "Public_Retail_Price_EGP"]
    ).sum()

    kpi1 = f"{total_stock_units:,.0f} Units ({total_stock_egp/1e6:.1f}M EGP)"
    kpi2 = f"{total_forecast_units:,.0f} Units"
    kpi3 = f"{risk_count} SKUs at Risk"
    kpi4 = f"{trapped_capital_egp/1e6:.2f}M EGP"

    # ABC/XYZ 9-Box Heatmap Figure
    matrix_counts = df_plan.groupby(["ABC_Class", "XYZ_Class"]).size().unstack(fill_value=0)
    for c in ["A", "B", "C"]:
        if c not in matrix_counts.index:
            matrix_counts.loc[c] = 0
    for c in ["X", "Y", "Z"]:
        if c not in matrix_counts.columns:
            matrix_counts[c] = 0
    matrix_counts = matrix_counts.reindex(index=["A", "B", "C"], columns=["X", "Y", "Z"])

    fig_matrix = go.Figure(
        data=go.Heatmap(
            z=matrix_counts.values,
            x=["Class X (Steady)", "Class Y (Seasonal)", "Class Z (Volatile)"],
            y=["Class A (80% Rev)", "Class B (15% Rev)", "Class C (5% Rev)"],
            colorscale=[[0, "#081324"], [0.5, "#0369a1"], [1, "#38bdf8"]],
            text=matrix_counts.values,
            texttemplate="%{text} SKUs",
            textfont=dict(color="#ffffff", size=13, family="Segoe UI"),
            hoverongaps=False
        )
    )
    fig_matrix.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=10, b=35),
        xaxis=dict(color=THEME["text_muted"], gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(color=THEME["text_muted"], gridcolor="rgba(0,0,0,0)"),
    )

    priority_order = {"P1_STOCKOUT_NOW": 1, "P2_LEAD_TIME_RISK": 2, "P3_BELOW_REORDER_POINT": 3, "P4_SLOW_OR_OVERSTOCK": 4, "P5_HEALTHY_COVERAGE": 5}
    dff["_sort_key"] = dff["Priority_Label"].map(priority_order)
    dff = dff.sort_values(by=["_sort_key", "Replenishment_Suggestion"], ascending=[True, False])

    table_data = dff.to_dict("records")
    badge_text = f"عرض {len(dff)} سجل من أصل {len(df_plan)}"

    return kpi1, kpi2, kpi3, kpi4, fig_matrix, table_data, badge_text


@app.callback(
    Output("chart-sku-time-series", "figure"),
    Input("sel-visualizer-sku", "value"),
    Input("filter-location", "value")
)
def update_sku_chart(sku_id, loc_filter):
    if df_hist.empty or sku_id is None:
        return go.Figure()

    sub_hist = df_hist[df_hist["Product_ID"] == sku_id].copy()
    if loc_filter != "All":
        sub_hist = sub_hist[sub_hist["Location_ID"] == loc_filter]

    monthly_sales = sub_hist.groupby("Snapshot_Month")["Sold_Qty"].sum().reset_index()
    monthly_sales["Snapshot_Month"] = pd.to_datetime(monthly_sales["Snapshot_Month"])
    monthly_sales = monthly_sales.sort_values("Snapshot_Month")

    sub_plan = df_plan[df_plan["Product_ID"] == sku_id]
    if loc_filter != "All":
        sub_plan = sub_plan[sub_plan["Location_ID"] == loc_filter]

    fc_m1 = sub_plan["Forecast_M1_Oct"].sum()
    fc_m2 = sub_plan["Forecast_M2_Nov"].sum()
    fc_m3 = sub_plan["Forecast_M3_Dec"].sum()

    future_dates = [pd.to_datetime("2026-10-01"), pd.to_datetime("2026-11-01"), pd.to_datetime("2026-12-01")]
    future_values = [fc_m1, fc_m2, fc_m3]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=monthly_sales["Snapshot_Month"],
        y=monthly_sales["Sold_Qty"],
        mode="lines+markers",
        name="Historical Demand (36M)",
        line=dict(color=THEME["primary"], width=2.5),
        marker=dict(size=5, color=THEME["primary"])
    ))

    last_hist_date = monthly_sales["Snapshot_Month"].iloc[-1]
    last_hist_val = monthly_sales["Sold_Qty"].iloc[-1]
    bridge_dates = [last_hist_date] + future_dates
    bridge_vals = [last_hist_val] + future_values

    fig.add_trace(go.Scatter(
        x=bridge_dates,
        y=bridge_vals,
        mode="lines+markers",
        name="AI Multi-Horizon Forecast",
        line=dict(color=THEME["success"], width=3, dash="dash"),
        marker=dict(size=8, symbol="diamond", color=THEME["success"])
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=15, b=35),
        xaxis=dict(title="Month", gridcolor="#17253d", color=THEME["text_muted"]),
        yaxis=dict(title="Demand Units", gridcolor="#17253d", color=THEME["text_muted"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color=THEME["text_body"])),
    )
    return fig


@app.callback(
    Output("download-plan-csv", "data"),
    Input("btn-download-plan", "n_clicks"),
    State("master-replenishment-table", "data"),
    prevent_initial_call=True
)
def export_plan_csv(n_clicks, table_data):
    if not table_data:
        return dash.no_update
    export_df = pd.DataFrame(table_data)
    return dcc.send_data_frame(export_df.to_csv, "Sharnouby_AI_Replenishment_Plan_2026.csv", index=False)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8082)
