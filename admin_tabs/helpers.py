"""Shared utilities for Admin tabs."""
import html as _html
import time

from shiny import ui
from sqlalchemy import text

try:
    from database.connection import get_db
    _DB_OK = True
except Exception:
    _DB_OK = False

# ── Security ─────────────────────────────────────────────────────────────────

_FORBIDDEN = {
    "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE", "CALL",
}


def _run_query(sql: str, limit: int = 100):
    sql = sql.strip().rstrip(";").strip()
    sql_up = sql.upper()
    if not (sql_up.startswith("SELECT") or sql_up.startswith("EXPLAIN")):
        raise ValueError("Apenas queries SELECT são permitidas.")
    for kw in _FORBIDDEN:
        if kw in sql_up:
            raise ValueError(f"Palavra-chave proibida: {kw}")
    if "LIMIT" not in sql_up:
        sql = f"{sql} LIMIT {limit}"
    db = get_db()
    t0 = time.perf_counter()
    with db.session() as session:
        result = session.execute(text(sql))
        columns = list(result.keys())
        rows = result.fetchall()
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return columns, rows, ms


def _html_table(columns, rows):
    ths = "".join(f"<th>{_html.escape(str(c))}</th>" for c in columns)
    trs = "".join(
        "<tr>" + "".join(
            f"<td>{_html.escape('' if v is None else str(v))}</td>"
            for v in row
        ) + "</tr>"
        for row in rows
    )
    return (
        "<div style='overflow-x:auto'>"
        "<table class='table table-sm table-striped table-bordered'"
        " style='font-size:13px;font-family:monospace'>"
        f"<thead class='table-dark'><tr>{ths}</tr></thead>"
        f"<tbody>{trs}</tbody></table></div>"
    )


def _fmt(v, decimals=1):
    """Format a numeric value for display."""
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def _stat_card(value, label, color="#34d399"):
    return ui.div(
        ui.div(str(value), class_="val", style=f"color:{color}"),
        ui.div(label, class_="lbl"),
        class_="stat-card",
    )


def _no_db():
    return ui.p("Banco não conectado.", style="color:#f87171")


# ── Constants ────────────────────────────────────────────────────────────────

VALID_GROWTH_FORMS = [
    "graminoid", "forb", "subshrub", "shrub", "tree",
    "scrambler", "vine", "liana", "palm", "bamboo", "other",
]

BIO_LABELS = {
    "bio1":  "Annual Mean Temp (°C)",
    "bio2":  "Mean Diurnal Range (°C)",
    "bio3":  "Isothermality (%)",
    "bio4":  "Temp Seasonality (×100)",
    "bio5":  "Max Temp Warmest Month (°C)",
    "bio6":  "Min Temp Coldest Month (°C)",
    "bio7":  "Temp Annual Range (°C)",
    "bio8":  "Mean Temp Wettest Quarter (°C)",
    "bio9":  "Mean Temp Driest Quarter (°C)",
    "bio10": "Mean Temp Warmest Quarter (°C)",
    "bio11": "Mean Temp Coldest Quarter (°C)",
    "bio12": "Annual Precipitation (mm)",
    "bio13": "Precip Wettest Month (mm)",
    "bio14": "Precip Driest Month (mm)",
    "bio15": "Precip Seasonality (CV)",
    "bio16": "Precip Wettest Quarter (mm)",
    "bio17": "Precip Driest Quarter (mm)",
    "bio18": "Precip Warmest Quarter (mm)",
    "bio19": "Precip Coldest Quarter (mm)",
}

STATE_TO_TDWG = {
    "BR-SC": "BZS", "BR-PR": "BZS", "BR-RS": "BZS",
    "BR-SP": "BZL", "BR-RJ": "BZL", "BR-ES": "BZL", "BR-MG": "BZL",
    "BR-BA": "BZE", "BR-SE": "BZE", "BR-AL": "BZE",
    "BR-PE": "BZE", "BR-PB": "BZE", "BR-RN": "BZE",
    "BR-CE": "BZN", "BR-PI": "BZN", "BR-MA": "BZN",
    "BR-PA": "BZN", "BR-AM": "BZN", "BR-RR": "BZN",
    "BR-AP": "BZN", "BR-TO": "BZN", "BR-AC": "BZN", "BR-RO": "BZN",
    "BR-GO": "BZC", "BR-MT": "BZC", "BR-MS": "BZC", "BR-DF": "BZC",
}

# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """
body { background: #0f0f0f; color: #e0e0e0; font-family: system-ui, sans-serif; }
.qe-header { background: linear-gradient(135deg, #111 0%, #1a1a1a 100%);
             border-bottom: 1px solid #2a2a2a; padding: 18px 32px;
             display: flex; align-items: center; gap: 14px; margin-bottom: 0; }
.qe-header h1 { margin: 0; font-size: 1.3em; font-weight: 700;
                background: linear-gradient(90deg, #34d399, #22d3ee);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.qe-header .sub { color: #666; font-size: 0.8em; margin-top: 2px; }
.qe-dot { width: 10px; height: 10px; border-radius: 50%; background: #22c55e;
           box-shadow: 0 0 8px #22c55e; flex-shrink: 0; }
.qe-dot.err { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
.qe-body { padding: 28px 32px; max-width: 1280px; margin: 0 auto; }
.nav-tabs { border-bottom: 1px solid #2a2a2a !important; }
.nav-tabs .nav-link { color: #888 !important; border: none !important;
                      border-bottom: 2px solid transparent !important; background: none !important; }
.nav-tabs .nav-link.active { color: #34d399 !important;
                              border-bottom-color: #34d399 !important; }
.nav-tabs .nav-link:hover { color: #ccc !important; }
.tab-content { padding-top: 24px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; }
.stat-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px;
             padding: 18px; text-align: center; }
.stat-card .val { font-size: 2em; font-weight: 700; color: #34d399; line-height: 1; }
.stat-card .lbl { font-size: 0.75em; color: #666; margin-top: 6px;
                  text-transform: uppercase; letter-spacing: 0.06em; }
.qe-section-title { color: #aaa; font-size: 0.85em; font-weight: 600;
                    text-transform: uppercase; letter-spacing: 0.08em;
                    margin: 24px 0 12px; }
.qe-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 20px; }
.table { color: #ccc !important; }
.table thead th { background: #222 !important; color: #aaa !important;
                  border-color: #333 !important; font-size: 0.8em; }
.table td { border-color: #2a2a2a !important; font-size: 0.85em; }
.table-striped > tbody > tr:nth-of-type(odd) > * { background-color: rgba(255,255,255,0.03) !important; }
.table-hover > tbody > tr:hover > * { background-color: rgba(52,211,153,0.06) !important; }
textarea.form-control { background: #111 !important; color: #d4d4d4 !important;
                        border: 1px solid #333 !important;
                        font-family: 'Menlo','Monaco','Courier New',monospace !important;
                        font-size: 13px !important; }
textarea.form-control:focus { border-color: #34d399 !important;
                              box-shadow: 0 0 0 2px rgba(52,211,153,0.15) !important; }
select.form-select, input.form-control { background: #1a1a1a !important; color: #ccc !important;
                                          border-color: #333 !important; }
label { color: #888 !important; font-size: 0.85em !important; }
.btn-success { background: #059669 !important; border-color: #059669 !important; }
.btn-success:hover { background: #047857 !important; }
.btn-outline-secondary { color: #888 !important; border-color: #444 !important; }
.btn-outline-secondary:hover { background: #1a1a1a !important; color: #ccc !important; }
.qe-meta { color: #666; font-size: 0.8em; margin-bottom: 10px; }
.qe-err { color: #f87171; background: #1a0a0a; border: 1px solid #7f1d1d;
          padding: 12px 16px; border-radius: 8px; font-family: monospace; font-size: 13px; }
.health-ok { color: #34d399; font-weight: 600; }
.health-err { color: #f87171; font-weight: 600; }

/* Climate cards */
.climate-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 16px; }
.climate-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 16px; }
.climate-card .val { font-size: 1.6em; font-weight: 700; color: #22d3ee; line-height: 1; }
.climate-card .lbl { font-size: 0.72em; color: #666; margin-top: 4px; }

/* Bio variables grid */
.bio-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin-top: 12px; }
.bio-item { display: flex; justify-content: space-between; padding: 6px 10px;
            background: #151515; border: 1px solid #222; border-radius: 6px; font-size: 0.82em; }
.bio-item .bio-lbl { color: #888; }
.bio-item .bio-val { color: #34d399; font-weight: 600; font-family: monospace; }

/* Quick buttons */
.qe-quick-btns { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.qe-quick-btns .btn { font-size: 0.8em; padding: 4px 14px; }

/* Leaflet map */
.qe-map { height: 360px; border-radius: 10px; border: 1px solid #2a2a2a; margin-bottom: 16px; }

/* Metrics row */
.metrics-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.metric-card { background: linear-gradient(135deg, #1a1a1a, #151520); border: 1px solid #2a2a2a;
               border-radius: 10px; padding: 16px; text-align: center; }
.metric-card .val { font-size: 1.8em; font-weight: 700; line-height: 1; }
.metric-card .lbl { font-size: 0.72em; color: #666; margin-top: 4px; text-transform: uppercase; }

/* Upload */
.upload-zone { border: 2px dashed #333; border-radius: 10px; padding: 30px; text-align: center;
               background: #111; margin-bottom: 16px; }
.upload-zone:hover { border-color: #34d399; }

/* Checkbox group inline */
.checkbox-inline { display: flex; gap: 14px; flex-wrap: wrap; }
.checkbox-inline .form-check { margin: 0; }
"""
