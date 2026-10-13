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

MODULES = [
    ("overview", "Enterprise Dashboard", "updata_app.py"),
    ("inventory", "Inventory & Replenishment", "app2.py"),
    ("customers", "Customer 360", "app3.py"),
    ("production", "Production & Downtime", "app4.py"),
    ("marketing", "Marketing Analytics", "app5.py"),
    ("branches", "Branch Performance", "app6.py"),
    ("procurement", "Procurement & Supplier Risk", "app7.py"),
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
            "borderRadius": "9px",
            "border": "1px solid #24415b",
            "backgroundColor": "#0b1b2c",
            "color": "#eaf6ff",
            "cursor": "pointer",
            "fontSize": "14px",
        },
    )
    for key, label, _ in MODULES
]

app.layout = html.Div(
    style={
        "minHeight": "100vh",
        "background": "#06111f",
        "color": "#eef7ff",
        "fontFamily": "Arial, sans-serif",
    },
    children=[
        dcc.Location(id="unified-url", refresh=False),
        html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "padding": "16px 24px",
                "borderBottom": "1px solid #18334a",
                "background": "#081827",
            },
            children=[
                html.Div([
                    html.Div("SHARNOUBY  /  LEO MODA", style={"fontSize": "12px", "letterSpacing": "2px", "color": "#45d7ff"}),
                    html.H2("Enterprise Group", style={"margin": "5px 0 0", "fontSize": "22px"}),
                ]),
                html.Div("7 integrated analytics modules", style={"color": "#9ab0c5", "fontSize": "13px"}),
            ],
        ),
        html.Div(
            style={"display": "flex", "alignItems": "stretch", "gap": "18px", "padding": "18px"},
            children=[
                html.Aside(
                    style={
                        "width": "245px",
                        "minWidth": "220px",
                        "padding": "14px",
                        "background": "#091827",
                        "border": "1px solid #18334a",
                        "borderRadius": "12px",
                        "height": "fit-content",
                        "position": "sticky",
                        "top": "15px",
                    },
                    children=[
                        html.Div("WORKSPACES", style={"fontSize": "11px", "letterSpacing": "1.5px", "color": "#7f9bb5", "margin": "3px 0 13px"}),
                        *NAV_ITEMS,
                        html.Hr(style={"borderColor": "#18334a", "marginTop": "16px"}),
                        html.Div("Data source: supplied CSV files", style={"fontSize": "11px", "color": "#7f9bb5", "lineHeight": "1.6"}),
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
