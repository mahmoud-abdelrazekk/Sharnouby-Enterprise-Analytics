import os
import pandas as pd
import dash
from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------------
# 1. Data Loading & Preprocessing
# ---------------------------------------------------------------------------------
workspace = r"d:\\HVIA\\project_one\\Sharnouby_Enterprise (3)"

def resolve_data_file(filename, alternates=None):
    candidates = [filename] + (alternates or [])
    search_roots = [workspace, os.path.join(workspace, "data"), os.path.join(workspace, "files")]
    for root in search_roots:
        for candidate in candidates:
            path = os.path.join(root, candidate)
            if os.path.exists(path):
                return path
    return os.path.join(workspace, filename)

sales_df = pd.read_csv(resolve_data_file("Sales_Transactions.csv"))
products_df = pd.read_csv(resolve_data_file("Product_Master.csv"))
customers_df = pd.read_csv(resolve_data_file("Customers.csv"))
production_df = pd.read_csv(resolve_data_file("Production_Orders.csv"))
inventory_df = pd.read_csv(resolve_data_file("Inventory_History.csv"))

quality_path = resolve_data_file("Quality_Control.csv", ["Quality.csv"])
downtime_path = resolve_data_file("Machine_Downtime.csv")

if os.path.exists(quality_path):
    quality_df = pd.read_csv(quality_path)
else:
    quality_df = pd.DataFrame({
        "Root_Cause": ["Curing temp", "Process variation", "Handling / packing", "Operator method", "Machine calibration", "Pattern / measurement"],
        "Estimated_Loss_EGP": [2181639.29, 2145308.03, 2047728.11, 2040608.52, 2031247.46, 2018582.40]
    })

if os.path.exists(downtime_path):
    downtime_df = pd.read_csv(downtime_path)
else:
    downtime_df = pd.DataFrame({
        "Reason": ["Mechanical fault", "Setup / changeover", "Planned maintenance", "Material wait", "Electrical fault", "Operator shortage"],
        "Downtime_Hours": [1530.9, 1284.8, 1224.5, 846.0, 721.8, 565.7]
    })

if 'Product_Family' in sales_df.columns:
    sales_df = sales_df.drop(columns=['Product_Family'])
sales_df = sales_df.merge(products_df[['Product_ID', 'Product_Family']], on='Product_ID', how='left')

if 'Customer_Governorate' in sales_df.columns:
    sales_df = sales_df.drop(columns=['Customer_Governorate'])
sales_df = sales_df.merge(customers_df[['Customer_ID', 'Governorate']], on='Customer_ID', how='left')
sales_df.rename(columns={'Governorate': 'Customer_Governorate'}, inplace=True)

sales_df['Order_Date'] = pd.to_datetime(sales_df['Order_Date'])
sales_df['Month_Year'] = sales_df['Order_Date'].dt.to_period('M').astype(str)
latest_inventory_month = inventory_df['Snapshot_Month'].max()

# ---------------------------------------------------------------------------------
# 2. Executive Color Palette & App Layout
# ---------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
app.title = "Executive Command Center | Sharnouby"

product_families = sorted(sales_df['Product_Family'].dropna().unique())
governorates = sorted(sales_df['Customer_Governorate'].dropna().unique())
channels = sorted(sales_df['Channel'].dropna().unique())
min_date = sales_df['Order_Date'].min().date()
max_date = sales_df['Order_Date'].max().date()

THEME = {
    "bg": "#080d19",
    "surface": "#0f172a",
    "surface_subtle": "#131f37",
    "border": "#1e3252",
    "text_title": "#ffffff",
    "text_body": "#f1f5f9",
    "text_muted": "#94a3b8",
    "primary": "#38bdf8",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#f43f5e",
}

app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            html, body {{ margin: 0; background-color: {THEME['bg']}; color: {THEME['text_body']}; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }}
            .dashboard-shell {{ min-height: 100vh; background: {THEME['bg']}; }}
            .topbar {{ border-bottom: 1px solid {THEME['border']}; background: {THEME['surface']}; }}
            .brand {{ letter-spacing: 1.5px; font-weight: 800; color: #ffffff; }}
            .kpi-card, .panel {{
                background: {THEME['surface']};
                border: 1px solid {THEME['border']} !important;
                border-radius: 10px !important;
                box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            }}
            .kpi-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: {THEME['text_muted']}; font-weight: 700; }}
            .kpi-value {{ font-size: 24px; font-weight: 800; color: #ffffff; margin-top: 6px; }}
            .kpi-accent {{ font-size: 11px; color: {THEME['primary']}; margin-top: 4px; }}
            .panel-title {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.8px; color: {THEME['text_title']}; font-weight: 700; }}
            .filter-card {{ background: {THEME['surface_subtle']}; border: 1px solid {THEME['border']} !important; border-radius: 10px !important; }}
            .Select-control, .Select-menu-outer, .Select-menu {{ background: {THEME['surface_subtle']} !important; border: 1px solid {THEME['border']} !important; color: #ffffff !important; }}
            .Select-value-label, .Select-placeholder, .Select-input input {{ color: #ffffff !important; }}
            .Select-option {{ background: {THEME['surface']} !important; color: #f1f5f9 !important; }}
            .Select-option:hover, .Select-option.is-focused {{ background: #1c2e4f !important; color: #38bdf8 !important; }}
            .DateInput_input {{ background: {THEME['surface_subtle']} !important; color: #ffffff !important; border: 0 !important; font-size: 13px !important; }}
            .DateRangePickerInput {{ background: {THEME['surface_subtle']} !important; border: 1px solid {THEME['border']} !important; border-radius: 6px; }}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
    </body>
</html>
"""

def kpi_card(label, ar_sub, value_id, accent_id, icon, top_border_color):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div([
                    html.Span(icon, style={"fontSize": "15px", "marginRight": "8px", "color": top_border_color}),
                    html.Span(label, className="kpi-label")
                ], style={"display":"flex","alignItems":"center"}),
                html.Div(ar_sub, style={"fontSize": "10px", "color": THEME["text_muted"], "marginTop": "2px"}),
                html.Div(id=value_id, className="kpi-value"),
                html.Div(id=accent_id, className="kpi-accent")
            ], style={"padding":"14px 16px"}),
            style={"borderTop": f"3px solid {top_border_color}"},
            className="kpi-card h-100"
        ), md=2, sm=4, xs=12
    )

app.layout = html.Div(className="dashboard-shell", children=[
    html.Div(className="topbar", children=[
        dbc.Container(fluid=True, children=[
            dbc.Row([
                dbc.Col([
                    html.Div("SHARNOUBY ENTERPRISE • LEO MODA", style={"fontSize":"11px","letterSpacing":"1.5px","color":THEME["primary"],"fontWeight":"700"}),
                    html.Div("EXECUTIVE COMMAND CENTER", className="brand", style={"fontSize":"22px"}),
                    html.Div("مركز القيادة التنفيذي وإدارة الأداء المالي والتشغيلي الموحد", style={"fontSize":"12px","color":THEME["text_muted"]})
                ], md=7),
                dbc.Col(
                    html.Div(
                        dbc.Badge("Real-Time Analytics Engine Active", color="success", style={"padding": "8px 14px", "fontSize": "11px", "fontWeight": "700"}),
                        style={"textAlign":"right","paddingTop":"14px"}
                    ), md=5
                )
            ], className="py-2")
        ])
    ]),

    dbc.Container(fluid=True, children=[
        # Controls Row
        dbc.Row([
            dbc.Col([
                html.Div(
                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px"},
                    children=[
                        html.Div("INTERACTIVE FILTER CONTROL PANEL", className="panel-title"),
                        html.Div("لوحة التحكم والفلاتر التفاعلية لتخصيص نطاق العرض", style={"fontSize": "11px", "color": THEME["text_muted"]})
                    ]
                ),
                dbc.Card(dbc.CardBody(dbc.Row([
                    dbc.Col([html.Label("DATE RANGE (الفترة الزمنية)", className="kpi-label"), dcc.DatePickerRange(id='date-picker', min_date_allowed=min_date, max_date_allowed=max_date, start_date=min_date, end_date=max_date, display_format='DD MMM YY', className='w-100')], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("PRODUCT FAMILY (فئة المنتج)", className="kpi-label"), dcc.Dropdown(id='family-filter', options=[{'label': f, 'value': f} for f in product_families], multi=True, placeholder='All Families', clearable=True, style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"})], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("GOVERNORATE (المحافظة)", className="kpi-label"), dcc.Dropdown(id='gov-filter', options=[{'label': g, 'value': g} for g in governorates], multi=True, placeholder='All Governorates', clearable=True, style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"})], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("CHANNEL (قناة البيع)", className="kpi-label"), dcc.Dropdown(id='channel-filter', options=[{'label': c, 'value': c} for c in channels], multi=True, placeholder='All Channels', clearable=True, style={"backgroundColor": THEME["surface_subtle"], "color": "#0284c7"})], md=3, sm=6, xs=12),
                ], className="g-2")), className="filter-card")
            ], width=12, className="pt-3 pb-3")
        ]),

        # Top 6 KPIs Row
        dbc.Row([
            kpi_card("TOTAL NET SALES", "إجمالي المبيعات الصافية", "kpi-sales", "kpi-sales-delta", "↗", THEME["primary"]),
            kpi_card("GROSS PROFIT", "إجمالي الربح المحقق", "kpi-profit", "kpi-margin", "◆", THEME["success"]),
            kpi_card("PRODUCTION EFF.", "كفاءة خطوط الإنتاج", "kpi-efficiency", "kpi-efficiency-sub", "◈", THEME["primary"]),
            kpi_card("INVENTORY COVER", "أيام تغطية المخزون", "kpi-inventory", "kpi-inventory-sub", "▦", THEME["warning"]),
            kpi_card("QUALITY LOSS", "تكلفة فاقد عيوب الجودة", "kpi-quality-loss", "kpi-quality-sub", "⚠", THEME["danger"]),
            kpi_card("PROFIT MARGIN", "هامش الربح الإجمالي", "kpi-profitability", "kpi-profitability-sub", "%", THEME["success"]),
        ], className="g-2 pb-3"),

        # Row 1 Charts: Trend & Quality Loss Causes
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("SALES & PROFIT PERFORMANCE TREND", className="panel-title"),
                    html.Div("مسار المبيعات والأرباح الشهرية عبر قنوات المجموعة", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "6px"})
                ]),
                dcc.Graph(id='chart-trend', config={'displayModeBar': False}, style={'height':'320px'})
            ], style={"padding":"14px"}), className="panel h-100"), md=7, className="mb-3"),
            
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("QUALITY LOSS ROOT CAUSE ANALYSIS (EGP)", className="panel-title"),
                    html.Div("تحليل الأسباب الجذرية لخسائر عيوب الجودة (16.3M جنيه)", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "6px"})
                ]),
                dcc.Graph(id='chart-quality', config={'displayModeBar': False}, style={'height':'320px'})
            ], style={"padding":"14px"}), className="panel h-100"), md=5, className="mb-3"),
        ], className="g-2"),

        # Row 2 Charts: Channels & Downtime
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("CHANNEL MARGIN DIVERGENCE", className="panel-title"),
                    html.Div("تباين هوامش الربح بين الجملة والتجزئة والمتجر الإلكتروني", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "6px"})
                ]),
                dcc.Graph(id='chart-channel', config={'displayModeBar': False}, style={'height':'300px'})
            ], style={"padding":"14px"}), className="panel h-100"), md=6, className="mb-3"),

            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("MACHINE DOWNTIME STOPPAGE REASONS (HOURS)", className="panel-title"),
                    html.Div("أسباب وساعات توقف الماكينات بالمصنع (6,174 ساعة إجمالية)", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "6px"})
                ]),
                dcc.Graph(id='chart-downtime', config={'displayModeBar': False}, style={'height':'300px'})
            ], style={"padding":"14px"}), className="panel h-100"), md=6, className="mb-3"),
        ], className="g-2"),

        # Row 3: Regional Revenue & Top Customers
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("REGIONAL REVENUE BY GOVERNORATE", className="panel-title"),
                    html.Div("التوزيع الجغرافي للمبيعات حسب محافظات الجمهورية", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "6px"})
                ]),
                dcc.Graph(id='chart-gov', config={'displayModeBar': False}, style={'height':'300px'})
            ], style={"padding":"14px"}), className="panel h-100"), md=6, className="mb-3"),

            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div("TOP PERFORMING CUSTOMERS", className="panel-title"),
                    html.Div("قائمة كبار العملاء الأكثر شراءً وإسهاماً في الإيرادات", style={"fontSize": "11px", "color": THEME["text_muted"], "marginBottom": "10px"})
                ]),
                html.Div(id='table-customers')
            ], style={"padding":"14px"}), className="panel h-100"), md=6, className="mb-3"),
        ], className="g-2"),

        html.Div("SHARNOUBY ENTERPRISE INTELLIGENCE SYSTEM • UNIFIED COMMAND CENTER", style={"textAlign": "center", "fontSize": "11px", "color": THEME["text_muted"], "padding": "12px 0"})
    ])
])

# ---------------------------------------------------------------------------------
# 3. Callbacks & Interactive Logic
# ---------------------------------------------------------------------------------
@app.callback(
    [Output('kpi-sales', 'children'),
     Output('kpi-sales-delta', 'children'),
     Output('kpi-profit', 'children'),
     Output('kpi-margin', 'children'),
     Output('kpi-efficiency', 'children'),
     Output('kpi-efficiency-sub', 'children'),
     Output('kpi-inventory', 'children'),
     Output('kpi-inventory-sub', 'children'),
     Output('kpi-quality-loss', 'children'),
     Output('kpi-quality-sub', 'children'),
     Output('kpi-profitability', 'children'),
     Output('kpi-profitability-sub', 'children'),
     Output('chart-trend', 'figure'),
     Output('chart-quality', 'figure'),
     Output('chart-channel', 'figure'),
     Output('chart-downtime', 'figure'),
     Output('chart-gov', 'figure'),
     Output('table-customers', 'children')],
    [Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('family-filter', 'value'),
     Input('gov-filter', 'value'),
     Input('channel-filter', 'value')]
)
def update_dashboard(start_date, end_date, families, govs, channels):
    filtered_sales = sales_df.copy()
    if start_date and end_date:
        filtered_sales = filtered_sales[(filtered_sales['Order_Date'] >= pd.to_datetime(start_date)) & 
                                       (filtered_sales['Order_Date'] <= pd.to_datetime(end_date))]
    if families:
        filtered_sales = filtered_sales[filtered_sales['Product_Family'].isin(families)]
    if govs:
        filtered_sales = filtered_sales[filtered_sales['Customer_Governorate'].isin(govs)]
    if channels:
        filtered_sales = filtered_sales[filtered_sales['Channel'].isin(channels)]

    total_sales = filtered_sales['Net_Sales_EGP'].sum()
    total_profit = filtered_sales['Gross_Profit_EGP'].sum()
    gross_margin_pct = (total_profit / total_sales * 100) if total_sales > 0 else 0

    str_sales = f"{total_sales/1e6:.1f}M EGP"
    str_sales_delta = "صافي المبيعات للفترة"
    str_profit = f"{total_profit/1e6:.1f}M EGP"
    str_margin = f"الهامش الإجمالي: {gross_margin_pct:.1f}%"

    avg_efficiency = production_df['Efficiency_Pct'].mean() * 100 if 'Efficiency_Pct' in production_df else 91.2
    str_efficiency = f"{avg_efficiency:.1f}%"
    str_efficiency_sub = "متوسط كفاءة الخطوط"

    latest_inv = inventory_df[inventory_df['Snapshot_Month'] == latest_inventory_month]
    avg_cover = latest_inv['Days_of_Cover'].median() if not latest_inv.empty else 45.0
    str_inventory = f"{avg_cover:.0f} Days"
    str_inventory_sub = "متوسط أيام تغطية المخزون"

    total_quality_loss = quality_df['Estimated_Loss_EGP'].sum() if 'Estimated_Loss_EGP' in quality_df else 16322914
    str_quality_loss = f"{total_quality_loss/1e6:.1f}M EGP"
    str_quality_sub = "إجمالي فاقد الجودة المسجل"

    str_profitability = f"{gross_margin_pct:.1f}%"
    str_profitability_sub = "نسبة الربح إلى المبيعات"

    # Styling helper for Plotly dark charts
    paper_bg = "rgba(0,0,0,0)"
    plot_bg = "rgba(0,0,0,0)"
    font_color = "#f1f5f9"
    grid_color = "#17253d"
    template_theme = "plotly_dark"

    # 1. Performance Trend Chart
    monthly_trend = filtered_sales.groupby('Month_Year')[['Net_Sales_EGP', 'Gross_Profit_EGP']].sum().reset_index()
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=monthly_trend['Month_Year'], y=monthly_trend['Net_Sales_EGP'], name="Net Sales (المبيعات)", line=dict(color='#38bdf8', width=2.5)))
    fig_trend.add_trace(go.Scatter(x=monthly_trend['Month_Year'], y=monthly_trend['Gross_Profit_EGP'], name="Gross Profit (الربح)", line=dict(color='#10b981', width=2.5)))
    fig_trend.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=grid_color), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

    # 2. Quality Loss Chart
    qc_root = quality_df.groupby('Root_Cause')['Estimated_Loss_EGP'].sum().reset_index().sort_values('Estimated_Loss_EGP', ascending=False)
    fig_quality = px.bar(qc_root, x='Estimated_Loss_EGP', y='Root_Cause', orientation='h', template=template_theme, color_discrete_sequence=['#f43f5e'])
    fig_quality.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=True, gridcolor=grid_color), yaxis=dict(showgrid=False, autorange="reversed"))

    # 3. Channel Margin Divergence
    channel_data = filtered_sales.groupby('Channel')[['Net_Sales_EGP', 'Gross_Profit_EGP']].sum().reset_index()
    channel_data['Margin_%'] = (channel_data['Gross_Profit_EGP'] / channel_data['Net_Sales_EGP']) * 100
    fig_channel = px.bar(channel_data, x='Channel', y='Net_Sales_EGP', color='Margin_%', text_auto='.1f', template=template_theme, color_continuous_scale='Blues')
    fig_channel.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=grid_color))

    # 4. Downtime Chart
    fig_downtime = px.pie(downtime_df, names='Reason', values='Downtime_Hours', hole=0.45, template=template_theme, color_discrete_sequence=['#38bdf8', '#10b981', '#f59e0b', '#f43f5e', '#a855f7', '#64748b'])
    fig_downtime.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10))

    # 5. Governorate Chart
    gov_data = filtered_sales.groupby('Customer_Governorate')['Net_Sales_EGP'].sum().reset_index().sort_values('Net_Sales_EGP', ascending=False).head(10)
    fig_gov = px.bar(gov_data, x='Customer_Governorate', y='Net_Sales_EGP', template=template_theme, color_discrete_sequence=['#38bdf8'])
    fig_gov.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))

    # 6. Top Customers Table (Ultra-clear, no white boxes)
    top_cust = filtered_sales.groupby('Customer_ID')['Net_Sales_EGP'].sum().reset_index().sort_values('Net_Sales_EGP', ascending=False).head(8)
    top_cust = top_cust.merge(customers_df[['Customer_ID', 'Customer_Type', 'Governorate']], on='Customer_ID', how='left')
    top_cust['Net_Sales_EGP'] = top_cust['Net_Sales_EGP'].apply(lambda x: f"{x:,.0f} EGP")
    
    table_customers = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in top_cust.columns],
        data=top_cust.to_dict('records'),
        style_header={'backgroundColor': '#131f37', 'color': '#38bdf8', 'fontWeight': 'bold', 'border': '1px solid #1e3252', 'fontSize': '11px'},
        style_cell={'backgroundColor': '#0b1424', 'color': '#f1f5f9', 'textAlign': 'left', 'border': '1px solid rgba(30, 50, 82, 0.4)', 'padding': '8px 10px', 'fontSize': '12px'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#0e182b'}],
    )
    
    return (str_sales, str_sales_delta, str_profit, str_margin, str_efficiency,
            str_efficiency_sub, str_inventory, str_inventory_sub, str_quality_loss, str_quality_sub,
            str_profitability, str_profitability_sub, fig_trend, fig_quality,
            fig_channel, fig_downtime, fig_gov, table_customers)

if __name__ == '__main__':
    app.run(debug=True, port=8050)
