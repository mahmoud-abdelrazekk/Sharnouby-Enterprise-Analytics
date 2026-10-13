import os
import pandas as pd
import numpy as np
import dash
from dash import Dash, dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. Helper Functions & Strict Validation
# ==========================================

def find_and_rename_column(df, candidate_names, target_name):
    """توحيد أسماء الأعمدة لتفادي KeyError"""
    df.columns = df.columns.str.strip()
    for col in candidate_names:
        if col in df.columns:
            if col != target_name:
                df.rename(columns={col: target_name}, inplace=True)
            return True
    return False

def validate_required_columns(df, required_cols, dataset_name):
    """التحقق الصارم من وجود الأعمدة الأساسية"""
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"CRITICAL ERROR in {dataset_name}: Required column(s) {missing_cols} are missing. "
            f"Cannot proceed with implicit default values."
        )

# ==========================================
# 2. Advanced Customer 360 & Affinity Pipeline
# ==========================================

def safe_mode(series, default="Unknown"):
    """إرجاع أكثر قيمة تكرارًا بأمان حتى لو كانت القيم كلها فارغة."""
    values = series.dropna()
    values = values[values.astype(str).str.strip().ne("")]
    modes = values.mode()
    return str(modes.iloc[0]) if not modes.empty else default


def normalize_customer_id(series):
    """توحيد معرفات العملاء كنصوص لتفادي اختلاف النوع بين ملفات CSV."""
    return series.astype("string").str.strip().replace("", pd.NA)


def build_category_affinity_rules(df_sales):
    """حساب اقتران الفئات داخل الفاتورة، مع فصل الفواتير حسب العميل أيضًا."""
    required = {"Customer_ID", "Invoice_ID", "Product_Family"}
    if not required.issubset(df_sales.columns):
        return {}

    baskets = df_sales.dropna(subset=["Customer_ID", "Invoice_ID"]).groupby(
        ["Customer_ID", "Invoice_ID"]
    )["Product_Family"].unique()

    co_occur = {}
    for basket in baskets:
        clean = list(dict.fromkeys(
            str(f).strip() for f in basket
            if pd.notna(f) and str(f).strip() not in {"", "Unknown", "nan"}
        ))
        for item1 in clean:
            for item2 in clean:
                if item1 != item2:
                    co_occur.setdefault(item1, {})
                    co_occur[item1][item2] = co_occur[item1].get(item2, 0) + 1

    affinity_map = {}
    for primary_cat, targets in co_occur.items():
        # ترتيب ثابت عند التعادل حتى تكون النتيجة قابلة لإعادة الإنتاج
        top_target, count = sorted(targets.items(), key=lambda x: (-x[1], x[0]))[0]
        affinity_map[primary_cat] = (top_target, count)
    return affinity_map


def load_and_prepare_customer_360():
    """تحميل البيانات وتنظيفها وبناء ملف Customer 360 على مستوى العميل."""
    cust_path = "Customers.csv"
    sales_path = "Sales_Transactions.csv"

    if not os.path.exists(sales_path):
        raise FileNotFoundError(f"Sales file not found: {sales_path}")

    # 1) ملف العملاء: نبدأ به للحفاظ على العملاء الذين لم يشتروا
    if os.path.exists(cust_path):
        df_cust = pd.read_csv(cust_path, dtype={"Customer_ID": "string", "Cust_ID": "string", "customer_id": "string"})
        df_cust.columns = df_cust.columns.str.strip()
        find_and_rename_column(df_cust, ["Customer_ID", "Cust_ID", "customer_id"], "Customer_ID")
        find_and_rename_column(df_cust, ["Governorate", "Location", "Region"], "Governorate")
        find_and_rename_column(df_cust, ["Customer_Type", "Type"], "Customer_Type")
        find_and_rename_column(df_cust, ["Loyalty_Tier", "Loyalty"], "Loyalty_Tier")
        validate_required_columns(df_cust, ["Customer_ID"], "Customers.csv")
        df_cust["Customer_ID"] = normalize_customer_id(df_cust["Customer_ID"])
        df_cust = df_cust.dropna(subset=["Customer_ID"])
        duplicate_count = int(df_cust.duplicated(subset=["Customer_ID"]).sum())
        if duplicate_count:
            print(f"WARNING: Customers.csv contains {duplicate_count:,} duplicate Customer_ID rows; keeping the first.")
            df_cust = df_cust.drop_duplicates(subset=["Customer_ID"], keep="first")
    else:
        print("WARNING: Customers.csv not found; Customer 360 will include purchasers only.")
        df_cust = None

    # 2) ملف المبيعات
    df_sales = pd.read_csv(
        sales_path,
        dtype={"Customer_ID": "string", "Cust_ID": "string", "Invoice_ID": "string", "Order_ID": "string"}
    )
    df_sales.columns = df_sales.columns.str.strip()
    find_and_rename_column(df_sales, ["Customer_ID", "Cust_ID", "customer_id"], "Customer_ID")
    find_and_rename_column(df_sales, ["Invoice_ID", "Order_ID"], "Invoice_ID")
    find_and_rename_column(df_sales, ["Order_Date", "Transaction_Date"], "Order_Date")
    find_and_rename_column(df_sales, ["Net_Sales_EGP", "Net_Sales"], "Net_Sales_EGP")
    find_and_rename_column(df_sales, ["Gross_Profit_EGP", "Gross_Profit"], "Gross_Profit_EGP")
    find_and_rename_column(df_sales, ["Channel", "Sales_Channel"], "Channel")
    find_and_rename_column(df_sales, ["Product_Family", "Category"], "Product_Family")

    validate_required_columns(
        df_sales,
        ["Customer_ID", "Invoice_ID", "Order_Date", "Net_Sales_EGP"],
        "Sales_Transactions.csv"
    )

    df_sales["Customer_ID"] = normalize_customer_id(df_sales["Customer_ID"])
    df_sales["Invoice_ID"] = df_sales["Invoice_ID"].astype("string").str.strip().replace("", pd.NA)
    df_sales["Order_Date"] = pd.to_datetime(df_sales["Order_Date"], errors="coerce")

    # تحويل الأعمدة الرقمية صراحةً، مع إظهار عدد القيم غير الصالحة في سجل التشغيل
    df_sales["Net_Sales_EGP"] = pd.to_numeric(df_sales["Net_Sales_EGP"], errors="coerce")
    invalid_net_sales = int(df_sales["Net_Sales_EGP"].isna().sum())
    if invalid_net_sales:
        print(f"WARNING: {invalid_net_sales:,} rows have invalid/missing Net_Sales_EGP and will be excluded.")

    if "Gross_Profit_EGP" in df_sales.columns:
        df_sales["Gross_Profit_EGP"] = pd.to_numeric(df_sales["Gross_Profit_EGP"], errors="coerce")
        invalid_profit = int(df_sales["Gross_Profit_EGP"].isna().sum())
        if invalid_profit:
            print(f"WARNING: {invalid_profit:,} rows have invalid/missing Gross_Profit_EGP; profit aggregation treats them as zero.")
        df_sales["Gross_Profit_EGP"] = df_sales["Gross_Profit_EGP"].fillna(0.0)
    else:
        print("WARNING: Gross_Profit_EGP column not found; Total_Profit is set to 0 and must not be used as a business KPI.")
        df_sales["Gross_Profit_EGP"] = 0.0

    for col in ["Channel", "Product_Family"]:
        if col not in df_sales.columns:
            print(f"WARNING: {col} column not found; using 'Unknown' for this field.")
            df_sales[col] = "Unknown"
        df_sales[col] = df_sales[col].astype("string").str.strip()
        df_sales[col] = df_sales[col].replace(["", "nan", "None", "<NA>"], pd.NA).fillna("Unknown")

    df_sales = df_sales.dropna(subset=["Customer_ID", "Invoice_ID", "Order_Date", "Net_Sales_EGP"])

    # نستخدم أحدث Order_Date صالح في الملف كله كتاريخ مرجعي موحّد للتقرير.
    # هذا تغيير زمني فقط ولا يفترض أي معنى محاسبي لـ Net_Sales_EGP أو Refund_Value_EGP.
    report_reference_date = df_sales["Order_Date"].max()
    if pd.isna(report_reference_date):
        raise ValueError("No valid Order_Date remains after cleaning.")

    # تقرير وصفي للمرتجعات. لا نخصم Refund_Value_EGP ولا نعيد تفسير Net_Sales_EGP.
    if "Returned" in df_sales.columns:
        returned_norm = df_sales["Returned"].astype("string").str.strip().str.lower()
        returned_flags = returned_norm.isin({"yes", "y", "true", "1", "returned"})
        not_returned_flags = returned_norm.isin({"no", "n", "false", "0", "not returned"})
        unknown_return_flags = ~(returned_flags | not_returned_flags) & returned_norm.notna()
        missing_return_flags = returned_norm.isna()

        print("\\nRETURNS AUDIT (descriptive only; no accounting adjustment applied)")
        print(f"Rows flagged as returned: {int(returned_flags.sum()):,}")
        print(f"Rows flagged as not returned: {int(not_returned_flags.sum()):,}")
        print(f"Rows with unknown Returned value: {int(unknown_return_flags.sum()):,}")
        print(f"Rows with missing Returned value: {int(missing_return_flags.sum()):,}")

        if "Refund_Value_EGP" in df_sales.columns:
            refund_values = pd.to_numeric(df_sales["Refund_Value_EGP"], errors="coerce")
            returned_refunds = refund_values[returned_flags]
            print(
                "Refund_Value_EGP on returned rows (descriptive sum only; "
                f"not subtracted from sales): {returned_refunds.sum(min_count=1):,.2f} EGP"
                if returned_refunds.notna().any()
                else "Refund_Value_EGP on returned rows: no numeric values available."
            )

        # نحافظ على المنهجية الحالية: استبعاد الصفوف الموسومة صراحةً كمرتجعة
        # من مؤشرات الشراء، مع إبقاء البيانات الأصلية دون تعديل.
        valid_sales = df_sales.loc[~returned_flags].copy()
        print(f"INFO: Excluded {int(returned_flags.sum()):,} rows explicitly flagged as returned from customer purchase metrics.")
        if unknown_return_flags.any() or missing_return_flags.any():
            print("WARNING: Unknown/missing Returned values are not excluded by the current rule; verify these records.")
    else:
        print("WARNING: Returned column not found; no transactions were excluded as returns.")
        valid_sales = df_sales.copy()

    if valid_sales.empty:
        raise ValueError("No valid sales rows remain after cleaning. Check dates, IDs, Net_Sales_EGP, and return flags.")

    # نفس التاريخ المرجعي لجميع العملاء، حتى لو كان أحدث سجل في الملف مرتجعًا.
    max_date = report_reference_date
    affinity_map = build_category_affinity_rules(valid_sales)
    known_families = valid_sales.loc[valid_sales["Product_Family"] != "Unknown", "Product_Family"]
    top_family = safe_mode(known_families, default="General Catalog")

    # تجميع على مستوى العميل؛ Frequency = عدد الفواتير الفريدة وليس عدد صفوف المنتجات
    sales_agg = valid_sales.groupby("Customer_ID", dropna=False).agg(
        Recency_Days=("Order_Date", lambda x: (max_date - x.max()).days),
        Frequency=("Invoice_ID", "nunique"),
        Total_Monetary=("Net_Sales_EGP", "sum"),
        Total_Profit=("Gross_Profit_EGP", "sum"),
        Preferred_Channel=("Channel", safe_mode),
        Preferred_Family=("Product_Family", safe_mode)
    ).reset_index()

    # 3) الدمج من جدول العملاء الأساسي مع منع تكرار العملاء
    if df_cust is not None:
        c360_df = df_cust.merge(sales_agg, on="Customer_ID", how="left", validate="one_to_one")
    else:
        c360_df = sales_agg.copy()

    c360_df["Frequency"] = c360_df["Frequency"].fillna(0).astype(int)
    for col in ["Total_Monetary", "Total_Profit"]:
        c360_df[col] = pd.to_numeric(c360_df[col], errors="coerce").fillna(0.0)
    c360_df["Preferred_Channel"] = c360_df["Preferred_Channel"].fillna("No Transactions")
    c360_df["Preferred_Family"] = c360_df["Preferred_Family"].fillna("No Transactions")
    if "Governorate" not in c360_df.columns:
        c360_df["Governorate"] = "Unknown"
    c360_df["Governorate"] = c360_df["Governorate"].fillna("Unknown").astype(str)
    if "Loyalty_Tier" not in c360_df.columns:
        c360_df["Loyalty_Tier"] = "Unregistered"
    c360_df["Loyalty_Tier"] = c360_df["Loyalty_Tier"].fillna("Unregistered").astype(str)

    # 4) قواعد التقسيم: قواعد وصفية وليست ناتجة عن نموذج تنبؤي
    purchasing_custs = c360_df[c360_df["Frequency"] > 0]
    avg_active_spend = purchasing_custs["Total_Monetary"].mean() if not purchasing_custs.empty else 0.0

    def classify_segment(row):
        freq, monetary, recency = row["Frequency"], row["Total_Monetary"], row["Recency_Days"]
        if freq == 0 or pd.isna(recency):
            return "NON_PURCHASER"
        if recency <= 60 and freq >= 3:
            return "CHAMPION"
        if recency <= 90 and freq >= 2:
            return "LOYAL"
        if 90 < recency <= 180 and monetary >= avg_active_spend:
            return "AT_RISK"
        if recency > 180:
            return "CHURNED"
        return "POTENTIAL"

    c360_df["Segment"] = c360_df.apply(classify_segment, axis=1)

    def generate_nbo(row):
        family = row["Preferred_Family"]
        if family in affinity_map:
            target_family, count = affinity_map[family]
            return f"Affinity: {target_family} (Co-bought {count} invoices)"
        if family != "No Transactions":
            return f"Popular: {top_family} (Category Leader)"
        return f"Welcome Offer: {top_family} Catalog"

    c360_df["Next_Best_Offer_Category"] = c360_df.apply(generate_nbo, axis=1)

    def generate_action(segment):
        actions = {
            "AT_RISK": "Trigger re-engagement email and feedback survey",
            "CHURNED": "Add to inactive-customer reactivation list",
            "LOYAL": "Offer early access to new-season catalog",
            "CHAMPION": "Consider priority/VIP support",
            "NON_PURCHASER": "Consider a first-purchase offer",
            "POTENTIAL": "Test a cross-category promotional offer"
        }
        return actions.get(segment, "Review customer profile")

    c360_df["Recommended_Action"] = c360_df["Segment"].apply(generate_action)

    # فحص سلامة: عدد العملاء في الناتج يجب أن يساوي عدد معرفات العملاء في المصدر الأساسي
    if df_cust is not None and len(c360_df) != df_cust["Customer_ID"].nunique():
        raise ValueError("Customer 360 row count does not match unique Customers.csv IDs; inspect merge keys.")

    print(f"INFO: Customer 360 contains {len(c360_df):,} customers; {int((c360_df['Frequency'] > 0).sum()):,} have purchases.")
    return valid_sales, c360_df, report_reference_date

# ==========================================
# 3. Application Setup & UI
# ==========================================

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "App 03 - Customer 360 & Retention Engine"

df_sales, df_cust_360, report_reference_date = load_and_prepare_customer_360()

# ==========================================
# DATA VALIDATION REPORT
# ==========================================

print("\n" + "=" * 55)
print("APP 03 - CUSTOMER 360 VALIDATION REPORT")
print("=" * 55)

# 1. Customer master validation
print(f"Customers in Customer 360: {len(df_cust_360):,}")
print(f"Report reference date (max Order_Date in cleaned source rows): {report_reference_date.date()}")
print("Methodology note: customer purchase metrics exclude rows explicitly flagged as Returned.")
print("Methodology note: Refund_Value_EGP is not subtracted; Net_Sales_EGP semantics are unconfirmed.")
print(f"Unique Customer IDs: {df_cust_360['Customer_ID'].nunique():,}")
print(f"Duplicate Customer IDs: {df_cust_360['Customer_ID'].duplicated().sum():,}")

# 2. Revenue validation
buyers = df_cust_360[df_cust_360["Frequency"] > 0]

print(f"\nPurchasing Customers: {len(buyers):,}")
print(f"Non-Purchasers: {(df_cust_360['Frequency'] == 0).sum():,}")
print(f"Total Historical Revenue: {buyers['Total_Monetary'].sum():,.2f} EGP")
print(f"Average Revenue per Buyer: {buyers['Total_Monetary'].mean():,.2f} EGP")

# 3. Segment validation
print("\nCUSTOMER SEGMENTS:")
segment_counts = df_cust_360["Segment"].value_counts(dropna=False)

for segment, count in segment_counts.items():
    print(f"{segment}: {count:,}")

print(f"Total Segment Count: {segment_counts.sum():,}")

# 4. Risk and loyalty KPIs
risk_count = df_cust_360["Segment"].isin(
    ["AT_RISK", "CHURNED"]
).sum()

loyal_count = df_cust_360["Segment"].isin(
    ["CHAMPION", "LOYAL"]
).sum()

print(f"\nAt-Risk + Churned: {risk_count:,}")
print(f"Champions + Loyal: {loyal_count:,}")

# 5. Recency and activity validation
purchasing_recency = df_cust_360.loc[
    df_cust_360["Frequency"] > 0, "Recency_Days"
].dropna()

active_90d = (
    (df_cust_360["Frequency"] > 0)
    & (df_cust_360["Recency_Days"] <= 90)
).sum()

active_rate = (
    active_90d / len(df_cust_360) * 100
    if len(df_cust_360) else 0
)

print(f"Average Recency: {purchasing_recency.mean():.2f} Days")
print(f"Customers Active in 90 Days: {active_90d:,}")
print(f"Customers Active in Last 90 Days (% of all customers): {active_rate:.2f}%")
print("Note: this is an activity rate, not a cohort-based customer-retention rate.")

# 6. Basic consistency checks
assert df_cust_360["Customer_ID"].is_unique, \
    "ERROR: Duplicate Customer IDs detected!"

assert segment_counts.sum() == len(df_cust_360), \
    "ERROR: Segment counts do not reconcile!"

assert (df_cust_360["Frequency"] >= 0).all(), \
    "ERROR: Negative customer frequency detected!"

print("\nBasic validation checks passed.")
print("=" * 55 + "\n")

app.layout = html.Div(style={
    "background": "linear-gradient(145deg, #020812 0%, #041324 48%, #020914 100%)",
    "minHeight": "100vh", "padding": "25px", "color": "#eef7ff", "fontFamily": "Segoe UI, sans-serif"
}, children=[
    
    # Header
    dbc.Row([
        dbc.Col([
            html.Div("PRODUCTION ENGINE • APP 03", style={"color": "#45d7ff", "letterSpacing": "2px", "fontSize": "12px", "fontWeight": "bold"}),
            html.H2("CUSTOMER 360 & RETENTION ENGINE", style={"fontWeight": "800", "color": "#ffffff"}),
            html.P("Who buys, why, and what happens next? (Full Master-Linked Pipeline)", style={"color": "#7f9bb5", "fontSize": "15px"})
        ], md=8),
        dbc.Col([
            dbc.Button("📥 Download Filtered Retention Plan (CSV)", id="btn-download-cust-csv", color="info", className="float-end mt-2", style={"fontWeight": "bold"}),
            dcc.Download(id="download-cust-csv")
        ], md=4)
    ], className="mb-4"),

    # Dynamic Executive KPIs
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("TOTAL BASE CUSTOMERS", style={"fontSize": "10px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-total-cust", style={"color": "#009dff", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("AVG REVENUE (BUYERS)", style={"fontSize": "10px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-avg-clv", style={"color": "#42e6b5", "fontWeight": "800", "margin": "0"}),
            html.Small("Historical average; not lifetime value (CLV)", style={"color": "#7f9bb5"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("AT-RISK & CHURNED", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-at-risk-cust", style={"color": "#ff5c7c", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("CHAMPIONS & LOYAL", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-champions", style={"color": "#ffb703", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("AVG RECENCY (DAYS)", style={"fontSize": "11px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-avg-recency", style={"color": "#45d7ff", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("CUSTOMERS ACTIVE IN LAST 90 DAYS", style={"fontSize": "10px", "color": "#7f9bb5", "fontWeight": "bold"}),
            html.H3(id="kpi-retention-rate", style={"color": "#9d4edd", "fontWeight": "800", "margin": "0"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=2),
    ], className="mb-4"),

    # Filter Panel
    dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Label("Filter Segment", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-segment",
                    options=[{"label": "All Segments", "value": "All"}] + [{"label": str(s), "value": s} for s in df_cust_360["Segment"].unique()],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3),
            dbc.Col([
                html.Label("Preferred Channel", style={"fontSize": "12px", "color": "#42e6b5"}),
                dcc.Dropdown(
                    id="filter-channel",
                    options=[{"label": "All Channels", "value": "All"}] + [{"label": str(c), "value": c} for c in df_cust_360["Preferred_Channel"].unique()],
                    value="All", clearable=False, style={"color": "#000"}
                )
            ], md=3),
            dbc.Col([
                html.Label("Select Individual Customer Profile (Filtered Scope)", style={"fontSize": "12px", "color": "#45d7ff", "fontWeight": "bold"}),
                dcc.Dropdown(
                    id="select-customer",
                    options=[],
                    value=None, clearable=False, style={"color": "#000"}
                )
            ], md=6)
        ])
    ]), style={"background": "rgba(8, 27, 48, 0.6)", "border": "1px solid rgba(49, 164, 226, 0.2)", "marginBottom": "20px"}),

    # Customer Profile & Next Best Offer Showcase
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("👤 Customer 360 Profile", style={"color": "#45d7ff", "fontWeight": "bold"}),
            html.Div(id="customer-profile-card")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)", "height": "340px"}), md=6, className="mb-3"),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("🎯 Next Best Offer (NBO) Recommendations", style={"color": "#42e6b5", "fontWeight": "bold"}),
            html.Div(id="nbo-showcase-card")
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)", "height": "340px"}), md=6, className="mb-3"),
    ]),

    # Analytical Charts Section
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("A. Customer Distribution by Segment", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-segment-dist", style={"height": "280px"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("B. Historical Revenue vs Recency (RFM Risk Scatter)", style={"color": "#45d7ff"}),
            dcc.Graph(id="chart-rfm-scatter", style={"height": "280px"})
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=6, className="mb-3"),
    ]),

    # Retention Action Table
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("📋 Customer Retention Action Table", style={"color": "#42e6b5", "fontWeight": "bold"}),
            dash_table.DataTable(
                id="table-retention",
                columns=[{"name": i, "id": i} for i in ["Customer_ID", "Segment", "Governorate", "Recency_Days", "Total_Monetary", "Preferred_Channel", "Next_Best_Offer_Category", "Recommended_Action"]],
                style_header={'backgroundColor': '#041324', 'color': '#45d7ff', 'fontWeight': 'bold', 'border': '1px solid rgba(49, 164, 226, 0.3)'},
                style_cell={'backgroundColor': '#081b30', 'color': '#eef7ff', 'border': '1px solid rgba(49, 164, 226, 0.1)', 'textAlign': 'center', 'padding': '8px'},
                style_data_conditional=[
                    {'if': {'filter_query': '{Segment} = "AT_RISK"'}, 'color': '#ff5c7c'},
                    {'if': {'filter_query': '{Segment} = "CHURNED"'}, 'color': '#e63946'},
                    {'if': {'filter_query': '{Segment} = "CHAMPION"'}, 'color': '#ffb703'},
                    {'if': {'filter_query': '{Segment} = "LOYAL"'}, 'color': '#42e6b5'},
                    {'if': {'filter_query': '{Segment} = "NON_PURCHASER"'}, 'color': '#7f9bb5'}
                ],
                page_size=8
            )
        ]), style={"background": "rgba(8, 27, 48, 0.85)", "border": "1px solid rgba(49, 164, 226, 0.3)"}), md=12)
    ])
])

# ==========================================
# 4. Reactive Callbacks & Strict Scope Linking
# ==========================================

# 4.1 ربط الاختيار المنسدل للعميل بالفلاتر النشطة حصراً
@app.callback(
    [Output("select-customer", "options"),
     Output("select-customer", "value")],
    [Input("filter-segment", "value"),
     Input("filter-channel", "value")]
)
def update_customer_dropdown(segment_filter, channel_filter):
    f_cust = df_cust_360.copy()
    if segment_filter != "All":
        f_cust = f_cust[f_cust["Segment"] == segment_filter]
    if channel_filter != "All":
        f_cust = f_cust[f_cust["Preferred_Channel"] == channel_filter]
        
    options = [{"label": f"Customer: {c}", "value": c} for c in f_cust["Customer_ID"].unique()]
    default_val = f_cust["Customer_ID"].iloc[0] if not f_cust.empty else None
    return options, default_val

# 4.2 تحديث الشاشة الرئيسية والتجميعات
@app.callback(
    [Output("kpi-total-cust", "children"),
     Output("kpi-avg-clv", "children"),
     Output("kpi-at-risk-cust", "children"),
     Output("kpi-champions", "children"),
     Output("kpi-avg-recency", "children"),
     Output("kpi-retention-rate", "children"),
     Output("customer-profile-card", "children"),
     Output("nbo-showcase-card", "children"),
     Output("chart-segment-dist", "figure"),
     Output("chart-rfm-scatter", "figure"),
     Output("table-retention", "data")],
    [Input("filter-segment", "value"),
     Input("filter-channel", "value"),
     Input("select-customer", "value")]
)
def update_customer_dashboard(segment_filter, channel_filter, selected_cust):
    # 1. تصفية نطاق التقرير بالكامل
    f_cust = df_cust_360.copy()
    if segment_filter != "All":
        f_cust = f_cust[f_cust["Segment"] == segment_filter]
    if channel_filter != "All":
        f_cust = f_cust[f_cust["Preferred_Channel"] == channel_filter]

    # 2. حساب KPIs الدقيقة
    tot_cust = f"{len(f_cust):,}"
    
    # متوسط الإيراد التاريخي للمشترين فقط؛ ليس Customer Lifetime Value (CLV).
    buyers = f_cust[f_cust["Frequency"] > 0]
    avg_revenue_per_buyer = f"{buyers['Total_Monetary'].mean():,.0f} EGP" if not buyers.empty else "0 EGP"
    
    at_risk_cnt = f"{len(f_cust[f_cust['Segment'].isin(['AT_RISK', 'CHURNED'])]):,}"
    champions_cnt = f"{len(f_cust[f_cust['Segment'].isin(['CHAMPION', 'LOYAL'])]):,}"
    
    purchasing_recency = f_cust.dropna(subset=["Recency_Days"])
    avg_rec = f"{purchasing_recency['Recency_Days'].mean():.0f} Days" if not purchasing_recency.empty else "N/A"
    
    # نسبة العملاء المشترين النشطين خلال آخر 90 يومًا من إجمالي نطاق الفلتر.
    # هذا مؤشر نشاط، وليس مقياس Retention cohort-based.
    active_90d_count = int(((f_cust["Frequency"] > 0) & (f_cust["Recency_Days"] <= 90)).sum())
    active_ratio = f"{(active_90d_count / len(f_cust) * 100):.1f}%" if not f_cust.empty else "0%"

    # 3. عرض بطاقات العميل المنسق ضمن النطاق المفلتر فقط
    cust_info = f_cust[f_cust["Customer_ID"] == selected_cust] if selected_cust else pd.DataFrame()
    if not cust_info.empty:
        c = cust_info.iloc[0]
        rec_display = f"{int(c['Recency_Days'])} Days ago" if pd.notna(c['Recency_Days']) else "No Purchase Yet"
        
        profile_ui = html.Div([
            dbc.Row([
                dbc.Col(html.Div("💳 Customer ID:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(f"{c['Customer_ID']}", style={"fontWeight": "bold", "color": "#45d7ff"}), md=8),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(html.Div("📍 Governorate:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(f"{c['Governorate']}", style={"fontWeight": "bold", "color": "#ffb703"}), md=8),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(html.Div("📊 Segment:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(f"{c['Segment']}", style={"fontWeight": "bold", "color": "#42e6b5"}), md=8),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(html.Div("🛒 Spend & Orders:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(f"{int(c['Frequency'])} Orders ({c['Total_Monetary']:,.0f} EGP)", style={"fontWeight": "bold"}), md=8),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(html.Div("🛍️ Preferred Channel:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(f"{c['Preferred_Channel']}", style={"fontWeight": "bold"}), md=8),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col(html.Div("⏱️ Recency:", style={"color": "#7f9bb5"}), md=4),
                dbc.Col(html.Div(rec_display, style={"fontWeight": "bold", "color": "#ff5c7c" if pd.notna(c['Recency_Days']) and c['Recency_Days']>180 else "#42e6b5"}), md=8),
            ])
        ], style={"padding": "10px"})
        
        nbo_ui = html.Div([
            html.Div(f"Targeted Recommendation Strategy for {c['Customer_ID']}", style={"color": "#7f9bb5", "marginBottom": "10px", "fontSize": "13px"}),
            dbc.Card(dbc.CardBody([
                html.H6("RECOMMENDED NBO CATEGORY", style={"color": "#45d7ff", "fontSize": "11px", "letterSpacing": "1px"}),
                html.H4(f"{c['Next_Best_Offer_Category']}", style={"color": "#ffffff", "fontWeight": "bold"}),
                html.P("Derived from basket co-occurrence and category affinity metrics.", style={"color": "#7f9bb5", "fontSize": "12px"}),
                html.Div(f"Action: {c['Recommended_Action']}", style={"color": "#42e6b5", "fontWeight": "bold", "fontSize": "13px", "marginTop": "10px"})
            ]), style={"background": "#06182b", "border": "1px solid rgba(0, 157, 255, 0.3)"})
        ], style={"padding": "10px"})
    else:
        profile_ui = html.Div("Please select a valid customer within the active scope.", style={"color": "#7f9bb5", "padding": "20px"})
        nbo_ui = html.Div("No customer selected.", style={"color": "#7f9bb5", "padding": "20px"})

    # 4. الرسوم البيانية
    seg_df = f_cust.groupby("Segment", as_index=False)["Customer_ID"].count().rename(columns={"Customer_ID": "Count"})
    fig_a = px.pie(seg_df, names="Segment", values="Count", hole=0.4, template="plotly_dark",
                   color_discrete_sequence=px.colors.qualitative.Bold)
    fig_a.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))

    fig_b = px.scatter(f_cust.dropna(subset=["Recency_Days"]), x="Recency_Days", y="Total_Monetary", color="Segment", size="Frequency",
                       hover_data=["Customer_ID", "Preferred_Channel"], template="plotly_dark",
                       labels={"Recency_Days": "Recency (Days)", "Total_Monetary": "Historical Net Sales (EGP)"})
    fig_b.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))

    # 5. تجهيز جدول الاستعراض وعرض القيم المالية بصيغة دقيقة
    f_cust_display = f_cust.copy()
    f_cust_display["Total_Monetary"] = f_cust_display["Total_Monetary"].apply(lambda x: f"{x:,.0f} EGP")
    f_cust_display["Recency_Days"] = f_cust_display["Recency_Days"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "N/A")
    
    table_data = f_cust_display[["Customer_ID", "Segment", "Governorate", "Recency_Days", "Total_Monetary", "Preferred_Channel", "Next_Best_Offer_Category", "Recommended_Action"]].to_dict('records')

    return (tot_cust, avg_revenue_per_buyer, at_risk_cnt, champions_cnt, avg_rec, active_ratio,
            profile_ui, nbo_ui, fig_a, fig_b, table_data)

# 4.3 تصدير التقرير المفلتر ديناميكياً لتطابق الفلاتر النشطة
@app.callback(
    Output("download-cust-csv", "data"),
    Input("btn-download-cust-csv", "n_clicks"),
    [dash.State("filter-segment", "value"),
     dash.State("filter-channel", "value")],
    prevent_initial_call=True
)
def export_filtered_cust_csv(n_clicks, segment_filter, channel_filter):
    f_cust = df_cust_360.copy()
    if segment_filter != "All":
        f_cust = f_cust[f_cust["Segment"] == segment_filter]
    if channel_filter != "All":
        f_cust = f_cust[f_cust["Preferred_Channel"] == channel_filter]
        
    return dcc.send_data_frame(f_cust.to_csv, "Filtered_Customer_360_Plan.csv", index=False)

if __name__ == '__main__':
    app.run(debug=True, port=8053)