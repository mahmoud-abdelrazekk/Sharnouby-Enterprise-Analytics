"""
Unified Sharnouby Enterprise Analytics Dashboard
Run: python unified_app.py
"""
from pathlib import Path
import os
import re
import traceback

import dash
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="Sharnouby | Enterprise Intelligence",
    suppress_callback_exceptions=True,
)
app.config.suppress_callback_exceptions = True

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                margin: 0;
                background-color: #080d19 !important;
                color: #f1f5f9 !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            /* High-contrast custom dropdowns across all modules */
            .Select-control {
                background-color: #131f37 !important;
                border: 1px solid #1e3252 !important;
                color: #ffffff !important;
                border-radius: 6px !important;
            }
            .Select-value-label, .Select-placeholder, .Select-input input, .Select--single > .Select-control .Select-value {
                color: #ffffff !important;
                line-height: 34px !important;
            }
            .Select-menu-outer, .Select-menu {
                background-color: #0f172a !important;
                border: 1px solid #1e3252 !important;
                box-shadow: 0 10px 30px rgba(0,0,0,0.7) !important;
                z-index: 9999 !important;
            }
            .Select-option {
                background-color: #0f172a !important;
                color: #f1f5f9 !important;
                padding: 10px 14px !important;
            }
            .Select-option:hover, .Select-option.is-focused {
                background-color: #1c2e4f !important;
                color: #38bdf8 !important;
            }
            .Select-arrow {
                border-color: #38bdf8 transparent transparent !important;
            }
            /* Elegant scrollbar */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #080d19;
            }
            ::-webkit-scrollbar-thumb {
                background: #1e3252;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #38bdf8;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

MODULES = [
    ("overview", "Enterprise Dashboard", "updata_app.py"),
    ("inventory", "Inventory & Replenishment", "app2.py"),
    ("customers", "Customer 360", "app3.py"),
    ("production", "Production & Downtime", "app4.py"),
    ("marketing", "Marketing Analytics", "app5.py"),
    ("branches", "Branch Performance", "app6.py"),
    ("procurement", "Procurement & Supplier Risk", "app7.py"),
    ("discount_optimizer", "AI Discount Optimizer", "app8_discount_optimizer.py"),
]

PAGES = {}

def load_page(page_key, label, filename):
    source_path = BASE_DIR / filename
    if not source_path.exists():
        raise FileNotFoundError(f"Application file missing: {filename}")
    source = source_path.read_text(encoding="utf-8-sig")

    # Keep each original application's component IDs isolated to prevent
    # collisions when all seven callback sets share one Dash instance.
    ids = set(re.findall(r'\bid\s*=\s*([\'"])(.*?)\1', source))
    id_names = {name for quote, name in ids}
    for old_id in sorted(id_names, key=len, reverse=True):
        new_id = f"{page_key}__{old_id}"
        source = re.sub(
            r"(['\"])"+re.escape(old_id)+r"\1",
            lambda m: m.group(1) + new_id + m.group(1),
            source,
        )

    # Reuse the single master Dash app, while retaining each app's layout.
    source = re.sub(
        r'^\s*app\s*=\s*(?:dash\.)?Dash\([^\n]*\)\s*$',
        'app = shared_app',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    source = re.sub(r'^\s*app\.layout\s*=', 'page_layout =', source, count=1, flags=re.MULTILINE)

    # The original scripts' run blocks must not start independent servers.
    source = re.sub(r"(?m)^if __name__\s*==\s*['\"]__main__['\"]:\s*\n(?:[ \t]+.*(?:\n|$))*", "", source)

    # The original overview used a machine-specific absolute directory.
    source = re.sub(
        r'(?m)^workspace\s*=\s*r?["\'][^"\']*["\']\s*$',
        'workspace = str(BASE_DIR)',
        source,
        count=1,
    )

    namespace = {
        "__name__": f"_embedded_{page_key}",
        "__file__": str(source_path),
        "shared_app": app,
        "BASE_DIR": str(BASE_DIR),
    }
    try:
        exec(compile(source, str(source_path), "exec"), namespace)
    except Exception as exc:
        raise RuntimeError(f"Could not load {label} ({filename}): {exc}") from exc

    layout = namespace.get("page_layout")
    if layout is None:
        raise RuntimeError(f"No layout found in {filename}; expected app.layout assignment.")
    PAGES[page_key] = {"label": label, "layout": layout}

for module in MODULES:
    load_page(*module)

NAV_ITEMS = [
    html.Button(
        label,
        id={"type": "nav-item", "page": key},
        n_clicks=0,
        className="nav-button",
        style={
            "width": "100%",
            "textAlign": "left",
            "padding": "12px 14px",
            "marginBottom": "7px",
            "borderRadius": "8px",
            "border": "1px solid #1e3252",
            "backgroundColor": "#131f37",
            "color": "#f1f5f9",
            "cursor": "pointer",
            "fontSize": "13px",
            "fontWeight": "600",
            "transition": "all 0.15s ease",
        },
    )
    for key, label, _ in MODULES
]

app.layout = html.Div(
    style={
        "minHeight": "100vh",
        "background": "#080d19",
        "color": "#f1f5f9",
        "fontFamily": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    },
    children=[
        dcc.Location(id="unified-url", refresh=False),
        html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "padding": "16px 28px",
                "borderBottom": "1px solid #1e3252",
                "background": "#0f172a",
            },
            children=[
                html.Div([
                    html.Div("SHARNOUBY  /  LEO MODA", style={"fontSize": "11px", "letterSpacing": "1.5px", "color": "#38bdf8", "fontWeight": "700"}),
                    html.H2("Enterprise Group", style={"margin": "3px 0 0", "fontSize": "22px", "fontWeight": "800", "color": "#ffffff"}),
                ]),
                html.Div("8 integrated analytics & AI modules", style={"color": "#94a3b8", "fontSize": "12px", "fontWeight": "500"}),
            ],
        ),
        html.Div(
            style={"display": "flex", "alignItems": "stretch", "gap": "18px", "padding": "20px 24px"},
            children=[
                html.Aside(
                    style={
                        "width": "250px",
                        "minWidth": "230px",
                        "padding": "14px",
                        "background": "#0f172a",
                        "border": "1px solid rgba(255, 255, 255, 0.08)",
                        "borderRadius": "10px",
                        "height": "fit-content",
                        "position": "sticky",
                        "top": "15px",
                    },
                    children=[
                        html.Div("WORKSPACES", style={"fontSize": "11px", "letterSpacing": "1.2px", "color": "#64748b", "fontWeight": "600", "margin": "4px 0 12px 4px"}),
                        *NAV_ITEMS,
                        html.Hr(style={"borderColor": "rgba(255, 255, 255, 0.08)", "marginTop": "14px"}),
                        html.Div("Data source: Sharnouby Group CSVs", style={"fontSize": "11px", "color": "#64748b", "lineHeight": "1.5", "padding": "0 4px"}),
                    ],
                ),
                html.Main(
                    id="unified-page-content",
                    style={"flex": "1", "minWidth": "0", "overflow": "hidden"},
                ),
            ],
        ),
    ],
)

from dash import Input, Output, ALL, ctx

@app.callback(
    Output("unified-page-content", "children"),
    Input({"type": "nav-item", "page": ALL}, "n_clicks"),
    prevent_initial_call=False,
)
def render_selected_page(_clicks):  
    triggered = ctx.triggered_id
    page_key = triggered.get("page") if isinstance(triggered, dict) else None
    if page_key not in PAGES:
        page_key = "overview"
    return PAGES[page_key]["layout"]

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8090)
