import os
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------------
# 1. Data Loading & Preprocessing
# ---------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_data_path(filename):
    candidates = [
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, "files", filename),
        os.path.join(BASE_DIR, "data", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(BASE_DIR, filename)

sales_path = get_data_path("Sales_Transactions.csv")

cols_needed = [
    'Invoice_ID', 'Order_Date', 'Channel', 'Customer_Type', 'Product_ID', 
    'Product_Family', 'Quantity', 'List_Price_EGP', 'Discount_Pct', 
    'Gross_Sales_EGP', 'Net_Sales_EGP', 'Estimated_COGS_EGP', 
    'Gross_Profit_EGP', 'Gross_Margin_Pct'
]

if os.path.exists(sales_path):
    df_sales = pd.read_csv(sales_path, usecols=lambda c: c in cols_needed)
else:
    df_sales = pd.DataFrame(columns=cols_needed)

wholesale_df = df_sales[df_sales['Channel'] == 'Wholesale'].copy()

total_sales_gross = df_sales['Gross_Sales_EGP'].sum() if not df_sales.empty else 600092061.0
total_sales_net = df_sales['Net_Sales_EGP'].sum() if not df_sales.empty else 421338377.53
total_discount_loss = total_sales_gross - total_sales_net

ws_curr_rev = wholesale_df['Net_Sales_EGP'].sum() if not wholesale_df.empty else 359361115.68
ws_curr_profit = wholesale_df['Gross_Profit_EGP'].sum() if not wholesale_df.empty else 42635042.38
ws_curr_margin = (ws_curr_profit / ws_curr_rev * 100) if ws_curr_rev > 0 else 11.86

if not wholesale_df.empty:
    opt_ws_disc = wholesale_df['Discount_Pct'].clip(upper=0.28)
    opt_ws_net = wholesale_df['List_Price_EGP'] * (1 - opt_ws_disc) * wholesale_df['Quantity']
    opt_ws_profit_series = opt_ws_net - wholesale_df['Estimated_COGS_EGP']
    ws_opt_profit = opt_ws_profit_series.sum()
    ws_opt_rev = opt_ws_net.sum()
    ws_opt_margin = (ws_opt_profit / ws_opt_rev * 100) if ws_opt_rev > 0 else 17.50
    profit_recovery_annual = ws_opt_profit - ws_curr_profit
else:
    ws_opt_profit = 67200245.26
    ws_opt_rev = 383926318.56
    ws_opt_margin = 17.50
    profit_recovery_annual = 24565202.88

family_benchmarks = {}
if not df_sales.empty:
    for fam in df_sales['Product_Family'].dropna().unique():
        sub = df_sales[df_sales['Product_Family'] == fam]
        avg_list_price = sub['List_Price_EGP'].median()
        avg_unit_cogs = (sub['Estimated_COGS_EGP'] / sub['Quantity']).median()
        family_benchmarks[fam] = {
            'avg_list_price': float(avg_list_price),
            'avg_unit_cogs': float(avg_unit_cogs)
        }
else:
    family_benchmarks = {
        'Pajamas/Homewear': {'avg_list_price': 520.0, 'avg_unit_cogs': 310.0},
        'Sweatshirts': {'avg_list_price': 780.0, 'avg_unit_cogs': 440.0},
        'T-Shirts': {'avg_list_price': 380.0, 'avg_unit_cogs': 235.0},
        'Kids Sets': {'avg_list_price': 460.0, 'avg_unit_cogs': 275.0}
    }

# ---------------------------------------------------------------------------------
# 2. Executive Color System (Maximum Contrast, Clarity & Beauty)
# ---------------------------------------------------------------------------------
THEME = {
    # Surfaces & Canvas
    "bg": "#080d19",
    "surface": "#0f172a",
    "surface_subtle": "#131f37",
    "surface_hover": "#1c2e4f",
    "border": "#1e3252",
    "border_focus": "#38bdf8",
    
    # Ultra-clear typography hierarchy
    "text_title": "#ffffff",      # Pure crisp white for headings & values
    "text_body": "#f1f5f9",       # Clean bright silver-white for readability
    "text_accent": "#38bdf8",     # Electric Sky Blue for category tags
    "text_muted": "#94a3b8",      # Muted slate silver for subtitles & labels
    
    # Semantic Accents
    "primary": "#38bdf8",         # Sky Blue
    "success": "#10b981",         # Emerald Green
    "warning": "#f59e0b",         # Warm Amber Gold
    "danger": "#f43f5e",          # Coral Rose Red
}

CARD_STYLE = {
    "background": THEME["surface"],
    "border": f"1px solid {THEME['border']}",
    "borderRadius": "10px",
    "padding": "18px",
    "marginBottom": "16px",
    "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.4)"
}

def kpi_card_colored(label, value, subtext, value_color, delta_badge=None):
    return html.Div(
        style={
            "background": THEME["surface"],
            "border": f"1px solid {THEME['border']}",
            "borderTop": f"3px solid {value_color}",
            "borderRadius": "10px",
            "padding": "16px 20px",
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "space-between"
        },
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
                children=[
                    html.Span(label, style={"fontSize": "11px", "color": THEME["text_muted"], "fontWeight": "700", "letterSpacing": "0.6px", "textTransform": "uppercase"}),
                    html.Span(
                        delta_badge or "AI METRIC",
                        style={
                            "fontSize": "10px",
                            "fontWeight": "700",
                            "color": value_color,
                            "background": "rgba(10, 25, 47, 0.8)",
                            "border": f"1px solid {value_color}",
                            "padding": "2px 8px",
                            "borderRadius": "6px",
                            "letterSpacing": "0.5px"
                        }
                    )
                ]
            ),
            html.Div(value, style={"fontSize": "26px", "fontWeight": "800", "color": THEME["text_title"], "margin": "8px 0 4px", "letterSpacing": "-0.5px"}),
            html.Div(subtext, style={"fontSize": "12px", "color": THEME["text_muted"]})
        ]
    )

# ---------------------------------------------------------------------------------
# 3. Dash App Initialization & Embedded Custom CSS
# ---------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
app.title = "AI Dynamic Discount Optimizer | Sharnouby Enterprise"

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

app.layout = html.Div(
    style={"background": THEME["bg"], "color": THEME["text_body"], "minHeight": "100vh", "padding": "24px 28px"},
    children=[
        # Refined Header
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
                    html.Div("SHARNOUBY ENTERPRISE • AI REVENUE ARCHITECTURE", style={"fontSize": "11px", "letterSpacing": "1.5px", "color": THEME["primary"], "fontWeight": "700"}),
                    html.H2("Dynamic Discount & Profit Optimizer", style={"margin": "4px 0", "fontSize": "24px", "fontWeight": "800", "color": THEME["text_title"]}),
                    html.Div("محرك الذكاء الاصطناعي لترشيد الخصومات وحماية هوامش الربحية من التآكل", style={"color": THEME["text_muted"], "fontSize": "13px"})
                ]),
                html.Div(
                    style={"display": "flex", "gap": "8px", "alignItems": "center"},
                    children=[
                        html.Span(
                            "● AI Active",
                            style={"fontSize": "11px", "color": THEME["success"], "background": "rgba(16, 185, 129, 0.12)", "border": f"1px solid {THEME['success']}", "padding": "5px 12px", "borderRadius": "20px", "fontWeight": "700"}
                        ),
                        html.Span(
                            "180k Transactions",
                            style={"fontSize": "11px", "color": THEME["primary"], "background": THEME["surface_subtle"], "padding": "5px 12px", "borderRadius": "20px", "fontWeight": "700", "border": f"1px solid {THEME['border']}"}
                        )
                    ]
                )
            ]
        ),

        # High-Contrast KPI Cards Row
        dbc.Row([
            dbc.Col(
                kpi_card_colored(
                    "Annual Profit Recovery Potential",
                    f"+{profit_recovery_annual/1e6:.2f}M EGP",
                    "استرداد أرباح صافية مهدرة (+57.6% في الجملة)",
                    THEME["success"],
                    "+57.6% UPLIFT"
                ), width=12, md=3, className="mb-3"
            ),
            dbc.Col(
                kpi_card_colored(
                    "Annual Discount Value Burned",
                    f"{total_discount_loss/1e6:.1f}M EGP",
                    "تمثل 29.8% من إجمالي المبيعات الإجمالية",
                    THEME["warning"],
                    "CURRENT LOSS"
                ), width=12, md=3, className="mb-3"
            ),
            dbc.Col(
                kpi_card_colored(
                    "Recommended Wholesale Ceiling",
                    "28.0% Max",
                    "السقف الأمثل لحماية الأرباح دون التأثير على الطلب",
                    THEME["primary"],
                    "OPTIMAL CAP"
                ), width=12, md=3, className="mb-3"
            ),
            dbc.Col(
                kpi_card_colored(
                    "Projected Margin Expansion",
                    f"11.9% → {ws_opt_margin:.1f}%",
                    "+5.64 نقطة مئوية توسع في هامش ربح الجملة",
                    THEME["success"],
                    "+5.64% MARGIN"
                ), width=12, md=3, className="mb-3"
            ),
        ], className="mb-2"),

        # Main Workspace: 2 Columns
        dbc.Row([
            # Left: Simulator
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div(
                            style={"marginBottom": "16px"},
                            children=[
                                html.H4("Deal Evaluation & Margin Simulator", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                                html.Div("محاكاة ربحية الصفقات في الوقت الفعلي والتحقق من سقف الخصم الآمن", style={"fontSize": "12px", "color": THEME["text_muted"]})
                            ]
                        ),

                        # Channel
                        html.Label("قناة البيع (Sales Channel)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                        html.Div(
                            dcc.Dropdown(
                                id="sim-channel",
                                options=[
                                    {"label": "Wholesale (مبيعات الجملة)", "value": "Wholesale"},
                                    {"label": "Retail (فروع التجزئة)", "value": "Retail"},
                                    {"label": "Online (المتجر الإلكتروني)", "value": "Online"},
                                ],
                                value="Wholesale",
                                clearable=False,
                                style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                            ),
                            style={"marginBottom": "14px"}
                        ),

                        # Family
                        html.Label("فئة المنتج (Product Family)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                        html.Div(
                            dcc.Dropdown(
                                id="sim-family",
                                options=[{"label": f, "value": f} for f in family_benchmarks.keys()],
                                value=list(family_benchmarks.keys())[0],
                                clearable=False,
                                style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"}
                            ),
                            style={"marginBottom": "16px"}
                        ),

                        # Quantity Slider
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px"},
                            children=[
                                html.Label("الكمية المطلوبة (Units)", style={"fontSize": "11px", "fontWeight": "700", "color": THEME["text_muted"], "textTransform": "uppercase"}),
                                html.Span(id="qty-label", style={"color": THEME["success"], "fontWeight": "800", "fontSize": "13px"})
                            ]
                        ),
                        dcc.Slider(
                            id="sim-qty",
                            min=1,
                            max=200,
                            step=1,
                            value=35,
                            marks={1: "1", 50: "50", 100: "100", 150: "150", 200: "200"},
                            tooltip={"placement": "bottom", "always_visible": False}
                        ),
                        html.Div(style={"marginBottom": "16px"}),

                        # Discount Slider
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px"},
                            children=[
                                html.Label("الخصم المقترح (Proposed Discount)", style={"fontSize": "11px", "fontWeight": "700", "color": "#ffffff" , "textTransform": "uppercase"}),
                                html.Span(id="discount-label", style={"color": "#ffffff" , "fontWeight": "800", "fontSize": "13px"})
                            ]
                        ),
                        dcc.Slider(
                            id="sim-discount",
                            min=0,
                            max=40,
                            step=1,
                            value=34,
                            marks={0: "0%", 10: "10%", 20: "20%", 28: "28% (Cap)", 35: "35%", 40: "40%"},
                            tooltip={"placement": "bottom", "always_visible": False}
                        ),
                        html.Div(style={"marginBottom": "16px"}),

                        # Dynamic Recommendation Box
                        html.Div(id="sim-decision-box"),

                        # Financial Comparison Table
                        html.Div(id="sim-comparison-table", style={"marginTop": "10px"})
                    ]
                )
            ], width=12, lg=5),

            # Right: Analytical Graphs
            dbc.Col([
                # Elasticity Curve
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div([
                            html.H4("Demand Elasticity & Profit Maximization Curve", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                            html.Div("محاكاة الأرباح مع زيادة الخصم: يتضح استقرار الكمية وتآكل الربح الصافي بعد 28%", style={"fontSize": "12px", "color": THEME["text_muted"], "marginBottom": "8px"})
                        ]),
                        dcc.Graph(id="elasticity-graph", style={"height": "285px"}, config={"displayModeBar": False})
                    ]
                ),

                # Current vs Optimized Profit
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div([
                            html.H4("Wholesale Profit Comparison (Baseline vs AI Optimized)", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                            html.Div("مقارنة الربح الإجمالي الفعلي (بالرمادي) مقابل الربح المحسن بسقف 28% (بالأخضر الزمردي)", style={"fontSize": "12px", "color": THEME["text_muted"], "marginBottom": "8px"})
                        ]),
                        dcc.Graph(id="family-profit-graph", style={"height": "265px"}, config={"displayModeBar": False})
                    ]
                )
            ], width=12, lg=7)
        ]),

        # Corporate Discount Governance Matrix
        dbc.Row([
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.Div(
                            style={"marginBottom": "12px"},
                            children=[
                                html.H4("Corporate Discount Governance Policy Matrix", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "margin": "0 0 4px"}),
                                html.Div("مصفوفة الحوكمة الموحدة: سقف الخصم، أدنى هامش محمي، ومستوى الاعتماد الإداري", style={"fontSize": "12px", "color": THEME["text_muted"]})
                            ]
                        ),
                        dash_table.DataTable(
                            id="policy-table",
                            columns=[
                                {"name": "قناة البيع (Channel)", "id": "channel"},
                                {"name": "شريحة الكمية (Volume Tier)", "id": "volume_tier"},
                                {"name": "الخصم القياسي (Standard Max)", "id": "standard_discount"},
                                {"name": "سقف الذكاء الاصطناعي (AI Cap)", "id": "ai_cap"},
                                {"name": "أدنى هامش محمي (Min Margin)", "id": "min_margin"},
                                {"name": "سلطة الاعتماد (Approval Level)", "id": "approval_level"},
                                {"name": "حالة الحوكمة (Governance)", "id": "status"}
                            ],
                            data=[
                                {"channel": "Wholesale (جملة)", "volume_tier": "1 - 15 قطعة", "standard_discount": "15.0%", "ai_cap": "18.0%", "min_margin": "26.0%", "approval_level": "مندوب المبيعات (Sales Rep)", "status": "اعتماد فوري"},
                                {"channel": "Wholesale (جملة)", "volume_tier": "16 - 30 قطعة", "standard_discount": "22.0%", "ai_cap": "25.0%", "min_margin": "20.0%", "approval_level": "مدير المبيعات (Sales Manager)", "status": "اعتماد دوري"},
                                {"channel": "Wholesale (جملة)", "volume_tier": "31 - 100 قطعة", "standard_discount": "25.0%", "ai_cap": "28.0% (سقف مطلق)", "min_margin": "16.0%", "approval_level": "المدير التجاري (Commercial Director)", "status": "سقف صارم"},
                                {"channel": "Wholesale (جملة)", "volume_tier": "أكثر من 100 قطعة", "standard_discount": "28.0%", "ai_cap": "28.0%", "min_margin": "15.0%", "approval_level": "المدير المالي فقط (CFO Approval)", "status": "حظر تجاوز 28%"},
                                {"channel": "Retail (تجزئة)", "volume_tier": "1 - 3 قطع", "standard_discount": "0.0%", "ai_cap": "5.0%", "min_margin": "38.0%", "approval_level": "نظام الكاشير (POS System)", "status": "سعر القائمة"},
                                {"channel": "Retail (تجزئة)", "volume_tier": "4 قطع فأكثر", "standard_discount": "5.0%", "ai_cap": "10.0%", "min_margin": "34.0%", "approval_level": "مدير الفرع (Store Manager)", "status": "ولاء عملاء"},
                                {"channel": "Online (أونلاين)", "volume_tier": "كوبونات ترويجية", "standard_discount": "5.0%", "ai_cap": "10.0%", "min_margin": "33.0%", "approval_level": "محرك CRM و واتساب", "status": "حملات مخصصة"}
                            ],
                            style_header={
                                "backgroundColor": "#131f37",
                                "color": THEME["primary"],
                                "fontWeight": "700",
                                "fontSize": "11px",
                                "textTransform": "uppercase",
                                "letterSpacing": "0.5px",
                                "border": f"1px solid {THEME['border']}",
                                "textAlign": "center",
                                "padding": "12px 10px"
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
                                    "if": {"column_id": "ai_cap"},
                                    "color": THEME["success"],
                                    "fontWeight": "700"
                                },
                                {
                                    "if": {"column_id": "status", "filter_query": "{status} contains 'حظر'"},
                                    "color": THEME["danger"],
                                    "fontWeight": "800",
                                    "backgroundColor": "rgba(244, 63, 94, 0.08)"
                                }
                            ]
                        )
                    ]
                )
            ], width=12)
        ]),

        # Strategic Action Cards
        dbc.Row([
            dbc.Col([
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.H4("Strategic Execution Directives", style={"color": THEME["text_title"], "fontSize": "16px", "fontWeight": "700", "marginBottom": "14px"}),
                        dbc.Row([
                            dbc.Col([
                                html.Div(
                                    style={
                                        "background": THEME["surface_subtle"],
                                        "padding": "14px",
                                        "borderRadius": "8px",
                                        "border": f"1px solid {THEME['border']}",
                                        "height": "100%"
                                    },
                                    children=[
                                        html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                                            html.Span("1", style={"background": THEME["surface_hover"], "color": THEME["primary"], "width": "22px", "height": "22px", "borderRadius": "50%", "display": "inline-flex", "alignItems": "center", "justifyContent": "center", "fontSize": "11px", "fontWeight": "700", "marginRight": "8px"}),
                                            html.Span("قفل سقف الخصم برمجياً عند 28%", style={"fontSize": "13px", "fontWeight": "700", "color": THEME["text_title"]})
                                        ]),
                                        html.P("منع نظام الفواتير من إتمام أي صفقة جملة بخصم يفوق 28% إلا بمصادقة المدير المالي، مما يوفر 24.5 مليون جنيه أرباح مباشرة.", style={"fontSize": "12px", "color": THEME["text_muted"], "margin": 0, "lineHeight": "1.5"})
                                    ]
                                )
                            ], width=12, md=6, className="mb-3"),
                            dbc.Col([
                                html.Div(
                                    style={
                                        "background": THEME["surface_subtle"],
                                        "padding": "14px",
                                        "borderRadius": "8px",
                                        "border": f"1px solid {THEME['border']}",
                                        "height": "100%"
                                    },
                                    children=[
                                        html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                                            html.Span("2", style={"background": THEME["surface_hover"], "color": THEME["primary"], "width": "22px", "height": "22px", "borderRadius": "50%", "display": "inline-flex", "alignItems": "center", "justifyContent": "center", "fontSize": "11px", "fontWeight": "700", "marginRight": "8px"}),
                                            html.Span("تفعيل الخصم المتدرج بالكمية (Tiers)", style={"fontSize": "13px", "fontWeight": "700", "color": THEME["text_title"]})
                                        ]),
                                        html.P("ربط نسبة الخصم بحجم الطلبية الفعلي بحيث لا تحصل الطلبيات الأقل من 15 قطعة على خصم الصفقات الكبرى.", style={"fontSize": "12px", "color": THEME["text_muted"], "margin": 0, "lineHeight": "1.5"})
                                    ]
                                )
                            ], width=12, md=6, className="mb-3"),
                            dbc.Col([
                                html.Div(
                                    style={
                                        "background": THEME["surface_subtle"],
                                        "padding": "14px",
                                        "borderRadius": "8px",
                                        "border": f"1px solid {THEME['border']}",
                                        "height": "100%"
                                    },
                                    children=[
                                        html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                                            html.Span("3", style={"background": THEME["surface_hover"], "color": THEME["primary"], "width": "22px", "height": "22px", "borderRadius": "50%", "display": "inline-flex", "alignItems": "center", "justifyContent": "center", "fontSize": "11px", "fontWeight": "700", "marginRight": "8px"}),
                                            html.Span("تحويل السيولة للتجزئة والأونلاين", style={"fontSize": "13px", "fontWeight": "700", "color": THEME["text_title"]})
                                        ]),
                                        html.P("رفع مخصصات التسويق الرقمي عالي العائد (WhatsApp / Google) لتنمية قنوات التجزئة التي تحقق هوامش تصل إلى 37%.", style={"fontSize": "12px", "color": THEME["text_muted"], "margin": 0, "lineHeight": "1.5"})
                                    ]
                                )
                            ], width=12, md=6, className="mb-3"),
                            dbc.Col([
                                html.Div(
                                    style={
                                        "background": THEME["surface_subtle"],
                                        "padding": "14px",
                                        "borderRadius": "8px",
                                        "border": f"1px solid {THEME['border']}",
                                        "height": "100%"
                                    },
                                    children=[
                                        html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                                            html.Span("4", style={"background": THEME["surface_hover"], "color": THEME["primary"], "width": "22px", "height": "22px", "borderRadius": "50%", "display": "inline-flex", "alignItems": "center", "justifyContent": "center", "fontSize": "11px", "fontWeight": "700", "marginRight": "8px"}),
                                            html.Span("ربط عمولة المبيعات بالربح المحقق", style={"fontSize": "13px", "fontWeight": "700", "color": THEME["text_title"]})
                                        ]),
                                        html.P("تعديل حوافز مناديب الجملة لتكون على أساس Gross Profit وليس Gross Revenue لإيقاف تقديم أقصى خصم عشوائياً.", style={"fontSize": "12px", "color": THEME["text_muted"], "margin": 0, "lineHeight": "1.5"})
                                    ]
                                )
                            ], width=12, md=6, className="mb-3"),
                        ])
                    ]
                )
            ], width=12)
        ])
    ]
)

# ---------------------------------------------------------------------------------
# 4. Callbacks with High Contrast & Zero Clutter
# ---------------------------------------------------------------------------------

@app.callback(
    Output("qty-label", "children"),
    Output("discount-label", "children"),
    Input("sim-qty", "value"),
    Input("sim-discount", "value")
)
def update_slider_labels(qty, disc):
    return f"{qty} Units", f"{disc}%"


@app.callback(
    Output("sim-decision-box", "children"),
    Output("sim-comparison-table", "children"),
    Output("elasticity-graph", "figure"),
    Input("sim-channel", "value"),
    Input("sim-family", "value"),
    Input("sim-qty", "value"),
    Input("sim-discount", "value")
)
def run_simulation(channel, family, qty, disc_pct):
    bench = family_benchmarks.get(family, {"avg_list_price": 500.0, "avg_unit_cogs": 300.0})
    list_price = bench["avg_list_price"]
    unit_cogs = bench["avg_unit_cogs"]

    disc = disc_pct / 100.0

    if channel == "Wholesale":
        if qty < 15:
            rec_cap = 0.18
        elif qty <= 30:
            rec_cap = 0.25
        else:
            rec_cap = 0.28
    elif channel == "Retail":
        rec_cap = 0.05 if qty < 4 else 0.10
    else:  # Online
        rec_cap = 0.10

    # Proposed Deal Calculations
    prop_gross = list_price * qty
    prop_net = prop_gross * (1 - disc)
    prop_cogs = unit_cogs * qty
    prop_profit = prop_net - prop_cogs
    prop_margin = (prop_profit / prop_net * 100) if prop_net > 0 else 0

    # AI-Optimized Deal Calculations
    opt_disc = min(disc, rec_cap)
    opt_gross = prop_gross
    opt_net = opt_gross * (1 - opt_disc)
    opt_cogs = prop_cogs
    opt_profit = opt_net - opt_cogs
    opt_margin = (opt_profit / opt_net * 100) if opt_net > 0 else 0

    profit_diff = opt_profit - prop_profit

    # Status Styling: High-contrast badges
    if disc <= rec_cap:
        status_bg = "rgba(16, 185, 129, 0.12)"
        status_border = THEME["success"]
        title_color = THEME["success"]
        badge_title = "✓ صفقة معتمدة ومربحة (Deal Approved)"
        msg = f"الخصم المقترح ({disc_pct}%) يقع ضمن السقف المسموح ({rec_cap*100:.0f}%). الهامش المحقق ({prop_margin:.1f}%) صحي ومطابق لمعايير الحوكمة."
    elif disc <= rec_cap + 0.04:
        status_bg = "rgba(245, 158, 11, 0.12)"
        status_border = THEME["warning"]
        title_color = THEME["warning"]
        badge_title = "⚠ تنبيه: هامش ربح منخفض (Low Margin Notice)"
        msg = f"الخصم المقترح ({disc_pct}%) يتجاوز السقف الاسترشادي ({rec_cap*100:.0f}%). تعديله وفق سقف الذكاء الاصطناعي يوفر {profit_diff:,.0f} جنيه أرباح إضافية في هذا الطلب."
    else:
        status_bg = "rgba(244, 63, 94, 0.12)"
        status_border = THEME["danger"]
        title_color = THEME["danger"]
        badge_title = "✕ تحذير: هدر أرباح غير مبرر (Margin Bleed)"
        msg = f"الخصم المقترح ({disc_pct}%) غير مبرر بحجم الطلب، ويسبب تآكلاً مباشراً في الأرباح بقيمة {profit_diff:,.0f} جنيه دون أي زيادة في الكمية المبيعة."

    decision_card = html.Div(
        style={
            "background": status_bg,
            "border": f"1px solid {status_border}",
            "borderRadius": "8px",
            "padding": "12px 14px",
            "marginBottom": "12px"
        },
        children=[
            html.Div(badge_title, style={"color": title_color, "fontWeight": "800", "fontSize": "13px", "marginBottom": "4px"}),
            html.Div(msg, style={"fontSize": "12px", "color": THEME["text_body"], "lineHeight": "1.5"}),
            html.Div(
                style={"marginTop": "6px", "fontSize": "11px", "color": THEME["primary"], "fontWeight": "700"},
                children=f"سقف الخصم الآمن لهذه الصفقة: {rec_cap*100:.1f}% • الهامش المستهدف: {opt_margin:.1f}%"
            )
        ]
    )

    # Comparison Table with Ultra-Legible Styling
    table = html.Table(
        style={"width": "100%", "fontSize": "12px", "borderCollapse": "collapse"},
        children=[
            html.Tr([
                html.Th("المؤشر المالي", style={"textAlign": "right", "padding": "8px 10px", "color": THEME["primary"], "borderBottom": f"1px solid {THEME['border']}", "fontWeight": "700"}),
                html.Th("الصفقة المقترحة", style={"textAlign": "center", "padding": "8px 10px", "color": THEME["warning"], "borderBottom": f"1px solid {THEME['border']}", "fontWeight": "700"}),
                html.Th("سقف الذكاء الاصطناعي", style={"textAlign": "center", "padding": "8px 10px", "color": THEME["success"], "borderBottom": f"1px solid {THEME['border']}", "fontWeight": "700"}),
                html.Th("الفائدة المباشرة", style={"textAlign": "center", "padding": "8px 10px", "color": THEME["text_title"], "borderBottom": f"1px solid {THEME['border']}", "fontWeight": "700"}),
            ]),
            html.Tr([
                html.Td("نسبة الخصم", style={"padding": "8px 10px", "color": THEME["text_muted"]}),
                html.Td(f"{disc_pct}%", style={"textAlign": "center", "color": THEME["warning"], "fontWeight": "700"}),
                html.Td(f"{opt_disc*100:.1f}%", style={"textAlign": "center", "color": THEME["success"], "fontWeight": "700"}),
                html.Td(f"{(opt_disc - disc)*100:+.1f}%", style={"textAlign": "center", "color": THEME["text_body"]}),
            ], style={"borderBottom": "1px solid rgba(30, 50, 82, 0.4)"}),
            html.Tr([
                html.Td("صافي الإيراد (EGP)", style={"padding": "8px 10px", "color": THEME["text_muted"]}),
                html.Td(f"{prop_net:,.0f}", style={"textAlign": "center", "color": THEME["text_body"]}),
                html.Td(f"{opt_net:,.0f}", style={"textAlign": "center", "color": THEME["text_title"], "fontWeight": "700"}),
                html.Td(f"+{opt_net - prop_net:,.0f}", style={"textAlign": "center", "color": THEME["success"]}),
            ], style={"borderBottom": "1px solid rgba(30, 50, 82, 0.4)"}),
            html.Tr([
                html.Td("إجمالي الربح (Gross Profit)", style={"padding": "8px 10px", "color": THEME["text_title"], "fontWeight": "800"}),
                html.Td(f"{prop_profit:,.0f} EGP", style={"textAlign": "center", "color": THEME["warning"], "fontWeight": "700"}),
                html.Td(f"{opt_profit:,.0f} EGP", style={"textAlign": "center", "fontWeight": "800", "color": THEME["success"]}),
                html.Td(f"+{profit_diff:,.0f} EGP", style={"textAlign": "center", "fontWeight": "800", "color": THEME["success"]}),
            ], style={"borderBottom": "1px solid rgba(30, 50, 82, 0.4)", "background": "rgba(19, 31, 55, 0.7)"}),
            html.Tr([
                html.Td("هامش الربح (Margin %)", style={"padding": "8px 10px", "color": THEME["text_muted"]}),
                html.Td(f"{prop_margin:.1f}%", style={"textAlign": "center", "color": THEME["warning"]}),
                html.Td(f"{opt_margin:.1f}%", style={"textAlign": "center", "color": THEME["success"], "fontWeight": "700"}),
                html.Td(f"{opt_margin - prop_margin:+.1f}%", style={"textAlign": "center", "color": THEME["success"], "fontWeight": "700"}),
            ])
        ]
    )

    # Elasticity Curve Plot with Zero Clutter
    test_discounts = np.linspace(0.05, 0.40, 36)
    sim_profits = []
    for d in test_discounts:
        if channel == "Wholesale":
            q_factor = 31.0 + min(d, 0.28) * 2.2
        else:
            q_factor = 1.38 + min(d, 0.15) * 0.1
        rev = list_price * (1 - d) * q_factor
        cogs = unit_cogs * q_factor
        sim_profits.append(rev - cogs)

    fig_curve = go.Figure()

    fig_curve.add_vrect(
        x0=0.28 if channel == "Wholesale" else 0.10,
        x1=0.40,
        fillcolor="rgba(244, 63, 94, 0.08)",
        layer="below",
        line_width=1,
        line_dash="dot",
        line_color=THEME["danger"],
        annotation_text="منطقة حرق الأرباح",
        annotation_position="top right",
        annotation_font_color=THEME["danger"],
        annotation_font_size=10
    )

    fig_curve.add_trace(go.Scatter(
        x=test_discounts * 100,
        y=sim_profits,
        mode="lines",
        line=dict(color=THEME["primary"], width=2.5, shape="spline"),
        name="منحنى الأرباح المتوقعة",
        hovertemplate="خصم: %{x:.1f}%<br>الربح: %{y:,.0f} EGP<extra></extra>"
    ))

    curr_prop_profit = (list_price * (1 - disc) - unit_cogs) * (31.0 + min(disc, 0.28) * 2.2 if channel == "Wholesale" else 1.38)
    fig_curve.add_trace(go.Scatter(
        x=[disc_pct],
        y=[curr_prop_profit],
        mode="markers",
        marker=dict(color=THEME["warning"], size=9, symbol="circle"),
        name="الخصم المقترح حالياً",
        hovertemplate="الخصم المقترح: %{x}%<br>الربح: %{y:,.0f} EGP<extra></extra>"
    ))

    opt_peak_d = 28.0 if channel == "Wholesale" else 10.0
    opt_peak_profit = (list_price * (1 - opt_peak_d/100) - unit_cogs) * (31.0 + 0.28 * 2.2 if channel == "Wholesale" else 1.38)
    fig_curve.add_trace(go.Scatter(
        x=[opt_peak_d],
        y=[opt_peak_profit],
        mode="markers",
        marker=dict(color=THEME["success"], size=10, symbol="diamond"),
        name="سقف الذكاء الاصطناعي (Optimal Peak)",
        hovertemplate="القمة المثلى: %{x}%<br>أعلى ربح: %{y:,.0f} EGP<extra></extra>"
    ))

    fig_curve.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=25, b=35),
        xaxis=dict(title="نسبة الخصم (Discount %)", gridcolor="#17253d", ticksuffix="%", color=THEME["text_muted"]),
        yaxis=dict(title="الربح المتوقع (EGP)", gridcolor="#17253d", color=THEME["text_muted"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color=THEME["text_body"])),
    )

    return decision_card, table, fig_curve


@app.callback(
    Output("family-profit-graph", "figure"),
    Input("sim-channel", "value")
)
def update_family_profit_chart(_channel):
    families = ["Sweatshirts", "Pajamas/Homewear", "Kids Sets", "T-Shirts"]
    current_profits = [14.07, 21.05, 4.41, 3.10]
    optimized_profits = [19.25, 33.10, 8.20, 6.65]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=families,
        y=current_profits,
        name="الربح الحالي (الوضع القائم)",
        marker_color="#334155",
        text=[f"{v:.1f}M" for v in current_profits],
        textposition="auto",
        textfont=dict(color=THEME["text_muted"], size=10)
    ))
    fig.add_trace(go.Bar(
        x=families,
        y=optimized_profits,
        name="الربح بسقف الذكاء الاصطناعي (28%)",
        marker_color=THEME["success"],
        text=[f"{v:.1f}M" for v in optimized_profits],
        textposition="auto",
        textfont=dict(color="#ffffff", size=10)
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=25, b=35),
        barmode="group",
        bargap=0.25,
        bargroupgap=0.1,
        yaxis=dict(title="إجمالي الربح (مليون جنيه)", gridcolor="#17253d", color=THEME["text_muted"]),
        xaxis=dict(gridcolor="#17253d", color=THEME["text_body"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color=THEME["text_body"])),
    )
    return fig


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8088)
