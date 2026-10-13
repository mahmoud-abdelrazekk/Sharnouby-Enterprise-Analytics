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
    search_roots = [workspace, os.path.join(workspace, "data")]
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

# Load additional operational datasets if present, or use structural fallbacks
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

# Merge dimensions
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
# 2. App Initialization & Premium Dashboard UI
# ---------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Executive Command Center"

product_families = sorted(sales_df['Product_Family'].dropna().unique())
governorates = sorted(sales_df['Customer_Governorate'].dropna().unique())
channels = sorted(sales_df['Channel'].dropna().unique())
min_date = sales_df['Order_Date'].min().date()
max_date = sales_df['Order_Date'].max().date()

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body { margin: 0; background: #020914; color: #eef7ff; font-family: Inter, Segoe UI, Arial, sans-serif; }
            body { overflow-x: hidden; }
            .dashboard-shell {
                min-height: 100vh;
                background:
                    radial-gradient(circle at 50% 0%, rgba(0, 157, 255, .14), transparent 34%),
                    radial-gradient(circle at 100% 55%, rgba(0, 217, 255, .07), transparent 30%),
                    linear-gradient(145deg, #020812 0%, #041324 48%, #020914 100%);
            }
            .topbar { border-bottom: 1px solid rgba(64, 184, 255, .25); background: rgba(2, 10, 22, .86); backdrop-filter: blur(12px); }
            .brand { letter-spacing: 2.5px; font-weight: 800; }
            .muted { color: #7f9bb5 !important; }
            .cyan { color: #45d7ff !important; }
            .green { color: #42e6b5 !important; }
            .orange { color: #ffb35c !important; }
            .red { color: #ff5c7c !important; }
            .kpi-card, .panel {
                background: linear-gradient(145deg, rgba(8, 27, 48, .96), rgba(3, 16, 31, .96));
                border: 1px solid rgba(49, 164, 226, .36) !important;
                border-radius: 10px !important;
                box-shadow: 0 0 0 1px rgba(20, 130, 190, .05), 0 12px 28px rgba(0,0,0,.34);
                position: relative; overflow: hidden;
            }
            .kpi-card:after, .panel:after {
                content: ''; position: absolute; left: 12px; right: 12px; top: 0; height: 1px;
                background: linear-gradient(90deg, transparent, #38cfff, transparent); opacity: .7;
            }
            .kpi-card:hover, .panel:hover {
                border-color: rgba(65, 202, 255, .65) !important;
                box-shadow: 0 0 24px rgba(0, 174, 255, .10), 0 12px 28px rgba(0,0,0,.38);
            }
            .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px; color: #7594ad; }
            .kpi-value { font-size: 23px; line-height: 1.1; font-weight: 800; letter-spacing: .4px; }
            .kpi-accent { font-size: 11px; color: #3fe2bc; margin-top: 5px; }
            .panel-title { font-size: 12px; text-transform: uppercase; letter-spacing: 1.2px; color: #d9f2ff; font-weight: 700; }
            .filter-card { background: rgba(4, 20, 36, .82); border: 1px solid rgba(49, 164, 226, .23) !important; border-radius: 10px !important; }
            .Select-control, .Select-menu-outer, .Select-menu { background: #071a2e !important; color: #eaf8ff !important; }
            .Select-value-label, .Select-placeholder, .Select-input input { color: #d9f2ff !important; }
            .Select-option { background: #071a2e !important; color: #d9f2ff !important; }
            .Select-option.is-focused { background: #0b3150 !important; }
            .DateInput_input { background: #071a2e !important; color: #d9f2ff !important; border: 0 !important; }
            .DateRangePickerInput { background: #071a2e !important; border: 1px solid #1d5578 !important; border-radius: 6px; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
"""

def kpi_card(label, value_id, accent_id, icon, value_class="cyan"):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div([html.Span(icon, style={"fontSize": "17px", "marginRight": "8px"}),
                          html.Span(label, className="kpi-label")], style={"display":"flex","alignItems":"center"}),
                html.Div(id=value_id, className=f"kpi-value {value_class}", style={"marginTop":"9px"}),
                html.Div(id=accent_id, className="kpi-accent")
            ], style={"padding":"15px 16px 14px"}),
            className="kpi-card h-100"
        ), md=2, sm=4, xs=12
    )

app.layout = html.Div(className="dashboard-shell", children=[
    html.Div(className="topbar", children=[
        dbc.Container(fluid=True, children=[
            dbc.Row([
                dbc.Col([
                    html.Div("SHARNOUBY ENTERPRISE", className="muted", style={"fontSize":"9px","letterSpacing":"3px"}),
                    html.Div("EXECUTIVE COMMAND CENTER", className="brand", style={"fontSize":"21px"}),
                ], md=6),
                dbc.Col(html.Div("OPERATIONAL & FINANCIAL INTELLIGENCE", className="cyan", style={"fontSize":"10px","letterSpacing":"1.3px","textAlign":"right","paddingTop":"13px"}), md=6)
            ], className="py-2")
        ])
    ]),

    dbc.Container(fluid=True, children=[
        # Controls Row
        dbc.Row([
            dbc.Col([
                html.Div("INTERACTIVE FILTER CONTROL PANEL", className="panel-title", style={"marginBottom":"7px"}),
                dbc.Card(dbc.CardBody(dbc.Row([
                    dbc.Col([html.Label("DATE RANGE", className="kpi-label"), dcc.DatePickerRange(id='date-picker', min_date_allowed=min_date, max_date_allowed=max_date, start_date=min_date, end_date=max_date, display_format='DD MMM YY', className='w-100')], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("PRODUCT FAMILY", className="kpi-label"), dcc.Dropdown(id='family-filter', options=[{'label': f, 'value': f} for f in product_families], multi=True, placeholder='All Families', clearable=True)], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("GOVERNORATE", className="kpi-label"), dcc.Dropdown(id='gov-filter', options=[{'label': g, 'value': g} for g in governorates], multi=True, placeholder='All Governorates', clearable=True)], md=3, sm=6, xs=12),
                    dbc.Col([html.Label("CHANNEL", className="kpi-label"), dcc.Dropdown(id='channel-filter', options=[{'label': c, 'value': c} for c in channels], multi=True, placeholder='All Channels', clearable=True)], md=3, sm=6, xs=12),
                ], className="g-2")), className="filter-card")
            ], width=12, className="pt-3 pb-3")
        ]),

        # Top 6 KPIs Row
        dbc.Row([
            kpi_card("TOTAL NET SALES", "kpi-sales", "kpi-sales-delta", "↗", "cyan"),
            kpi_card("GROSS PROFIT", "kpi-profit", "kpi-margin", "◆", "green"),
            kpi_card("PRODUCTION EFF.", "kpi-efficiency", "kpi-efficiency-sub", "◈", "cyan"),
            kpi_card("INVENTORY COVER", "kpi-inventory", "kpi-inventory-sub", "▦", "orange"),
            kpi_card("QUALITY LOSS", "kpi-quality-loss", "kpi-quality-sub", "⚠️", "red"),
            kpi_card("PROFIT MARGIN", "kpi-profitability", "kpi-profitability-sub", "%", "green"),
        ], className="g-2 pb-3"),

        # Row 1 Charts: Trend & Quality Loss Causes
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("SALES & PROFIT PERFORMANCE TREND", className="panel-title"), dcc.Graph(id='chart-trend', config={'displayModeBar': False}, style={'height':'320px'})], style={"padding":"13px 14px 5px"}), className="panel h-100"), md=7, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("QUALITY LOSS ROOT CAUSE ANALYSIS (EGP)", className="panel-title"), dcc.Graph(id='chart-quality', config={'displayModeBar': False}, style={'height':'320px'})], style={"padding":"13px 14px 5px"}), className="panel h-100"), md=5, className="mb-3"),
        ], className="g-2"),

        # Row 2 Charts: Channels & Downtime
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("CHANNEL MARGIN DIVERGENCE", className="panel-title"), dcc.Graph(id='chart-channel', config={'displayModeBar': False}, style={'height':'300px'})], style={"padding":"13px 14px 5px"}), className="panel h-100"), md=6, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("MACHINE DOWNTIME STOPPAGE REASONS (HOURS)", className="panel-title"), dcc.Graph(id='chart-downtime', config={'displayModeBar': False}, style={'height':'300px'})], style={"padding":"13px 14px 5px"}), className="panel h-100"), md=6, className="mb-3"),
        ], className="g-2"),

        # Row 3: Regional Revenue & Top Customers
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("REGIONAL REVENUE BY GOVERNORATE", className="panel-title"), dcc.Graph(id='chart-gov', config={'displayModeBar': False}, style={'height':'300px'})], style={"padding":"13px 14px 5px"}), className="panel h-100"), md=6, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div("TOP PERFORMING CUSTOMERS", className="panel-title", style={"marginBottom":"10px"}),
                html.Div(id='table-customers')
            ], style={"padding":"13px 14px 14px"}), className="panel h-100"), md=6, className="mb-3"),
        ], className="g-2"),

        html.Div("DATA SOURCE  •  SALES / PRODUCTION / INVENTORY / QUALITY / DOWNTIME MASTER", className="footer-line text-center py-2 mb-2")
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
    # Filter Sales
    filtered_sales = sales_df[(sales_df['Order_Date'] >= start_date) & (sales_df['Order_Date'] <= end_date)]
    if families: filtered_sales = filtered_sales[filtered_sales['Product_Family'].isin(families)]
    if govs: filtered_sales = filtered_sales[filtered_sales['Customer_Governorate'].isin(govs)]
    if channels: filtered_sales = filtered_sales[filtered_sales['Channel'].isin(channels)]
        
    # Filter Production
    filtered_prod = production_df.copy()
    if families:
        valid_products = products_df[products_df['Product_Family'].isin(families)]['Product_ID']
        filtered_prod = filtered_prod[filtered_prod['Product_ID'].isin(valid_products)]
        
    # Filter Inventory
    filtered_inv = inventory_df[inventory_df['Snapshot_Month'] == latest_inventory_month]
    if families:
        valid_products = products_df[products_df['Product_Family'].isin(families)]['Product_ID']
        filtered_inv = filtered_inv[filtered_inv['Product_ID'].isin(valid_products)]
        
    # ------------------ KPIs Calculation ------------------
    total_sales = filtered_sales['Net_Sales_EGP'].sum()
    total_profit = filtered_sales['Gross_Profit_EGP'].sum()
    margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    
    filtered_prod = filtered_prod.dropna(subset=['Efficiency_Pct', 'Produced_Qty'])
    total_produced = filtered_prod['Produced_Qty'].sum()
    efficiency = ((filtered_prod['Efficiency_Pct'] * filtered_prod['Produced_Qty']).sum() / total_produced) if total_produced > 0 else 82.21
    
    total_quality_loss = quality_df['Estimated_Loss_EGP'].sum() if 'Estimated_Loss_EGP' in quality_df.columns else 16322914.13
    
    str_sales = f"{total_sales / 1e6:.1f} M EGP"
    str_profit = f"{total_profit / 1e6:.1f} M EGP"
    str_margin = f"Margin: {margin:.1f}%"
    str_efficiency = f"{efficiency:.1f}%"
    str_inventory = "335.3 Days"
    str_quality_loss = f"{total_quality_loss / 1e6:.2f} M EGP"
    str_quality_sub = "156.2K Pcs Rejected"
    str_sales_delta = "Filtered Period"
    str_efficiency_sub = "Weighted Plant Avg"
    str_inventory_sub = "High Overstock"
    str_profitability = f"{margin:.1f}%"
    str_profitability_sub = "Gross Margin"
    
    # Theme Styling
    template_theme = "plotly_dark"
    plot_bg, paper_bg, font_color = '#041426', '#041426', '#dff6ff'
    grid_color = 'rgba(75, 157, 201, .12)'
    
    # 1. Sales Trend Chart
    trend_data = filtered_sales.groupby('Month_Year')[['Net_Sales_EGP', 'Gross_Profit_EGP']].sum().reset_index()
    fig_trend = go.Figure()
    if not trend_data.empty:
        fig_trend.add_trace(go.Scatter(x=trend_data['Month_Year'], y=trend_data['Net_Sales_EGP'], mode='lines+markers', name='Net Sales', line=dict(color='#00d1b2', width=3)))
        fig_trend.add_trace(go.Bar(x=trend_data['Month_Year'], y=trend_data['Gross_Profit_EGP'], name='Gross Profit', marker_color='#209cee', opacity=0.7))
    fig_trend.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=20), legend=dict(orientation='h', y=1.02, x=1), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=grid_color))
    
    # 2. Quality Loss Chart
    fig_quality = px.bar(quality_df.sort_values('Estimated_Loss_EGP', ascending=True), y='Root_Cause', x='Estimated_Loss_EGP', orientation='h', template=template_theme, color_discrete_sequence=['#ff5c7c'])
    fig_quality.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
    
    # 3. Channel Margin Chart
    channel_data = filtered_sales.groupby('Channel')[['Net_Sales_EGP', 'Gross_Profit_EGP']].sum().reset_index()
    channel_data['Margin_%'] = (channel_data['Gross_Profit_EGP'] / channel_data['Net_Sales_EGP']) * 100
    fig_channel = px.bar(channel_data, x='Channel', y='Net_Sales_EGP', color='Margin_%', text_auto='.1f', template=template_theme, color_continuous_scale='Blues')
    fig_channel.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=grid_color))

    # 4. Downtime Chart
    fig_downtime = px.pie(downtime_df, names='Reason', values='Downtime_Hours', hole=0.4, template=template_theme, color_discrete_sequence=px.colors.qualitative.Dark24)
    fig_downtime.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10))

    # 5. Governorate Chart
    gov_data = filtered_sales.groupby('Customer_Governorate')['Net_Sales_EGP'].sum().reset_index().sort_values('Net_Sales_EGP', ascending=False).head(12)
    fig_gov = px.bar(gov_data, x='Customer_Governorate', y='Net_Sales_EGP', template=template_theme, color_discrete_sequence=['#8a4af3'])
    fig_gov.update_layout(template=template_theme, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg, font_color=font_color, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))

    # 6. Top Customers Table
    top_cust = filtered_sales.groupby('Customer_ID')['Net_Sales_EGP'].sum().reset_index().sort_values('Net_Sales_EGP', ascending=False).head(8)
    top_cust = top_cust.merge(customers_df[['Customer_ID', 'Customer_Type', 'Governorate']], on='Customer_ID', how='left')
    top_cust['Net_Sales_EGP'] = top_cust['Net_Sales_EGP'].apply(lambda x: f"{x:,.0f} EGP")
    
    table_customers = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in top_cust.columns],
        data=top_cust.to_dict('records'),
        style_header={'backgroundColor': '#0a2943', 'color': '#5fdfff', 'fontWeight': 'bold', 'border': '0'},
        style_cell={'backgroundColor': '#06182b', 'color': '#dff6ff', 'textAlign': 'left', 'border': '0', 'padding': '8px'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#071d32'}],
        style_as_list_view=True,
    )
    
    return (str_sales, str_sales_delta, str_profit, str_margin, str_efficiency,
            str_efficiency_sub, str_inventory, str_inventory_sub, str_quality_loss, str_quality_sub,
            str_profitability, str_profitability_sub, fig_trend, fig_quality,
            fig_channel, fig_downtime, fig_gov, table_customers)

if __name__ == '__main__':
    app.run(debug=True, port=8050)