# visualize_export.py: Roll C (Visualization + Saving / Visualiseerimine ja salvestamine)
# Loob Plotly diagrammid Roll B töödeldud andmetest ja salvestab tulemused
# output/ kausta: CSV (ajatempliga failinimi) + diagrammid HTML-ina.

# --- Impordid -------------------------------------------------------------
import os
import json
import logging
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# Veerunimed, mida transform.py calculate_weekly_aggregates() tagastab
WEEK_COL = "week"
REVENUE_COL = "total_revenue"


# --- SAMM 1: create_weekly_chart(df_weekly) — nädalase tulu joondiagramm ---
def create_weekly_chart(df_weekly: pd.DataFrame) -> go.Figure:
    """Joondiagramm nädalasest tulust (x = nädal, y = tulu)."""
    for col in (WEEK_COL, REVENUE_COL):
        if col not in df_weekly.columns:
            raise KeyError(
                f"Veerg '{col}' puudub. Leitud veerud: {list(df_weekly.columns)}"
            )

    fig = px.line(
        df_weekly,
        x=WEEK_COL,
        y=REVENUE_COL,
        title="Nädalane tulu",
        markers=True,
    )
    fig.update_layout(
        xaxis_title="Nädal",
        yaxis_title="Tulu (€)",
        template="plotly_white",
    )
    fig.update_traces(hovertemplate="Nädal: %{x}<br>Tulu: %{y:,.2f} €")
    return fig


# --- SAMM 2: create_kpi_summary(kpis) — KPI indicator kaardid ---------------
def create_kpi_summary(kpis: dict) -> go.Figure:
    """Kolm KPI kaarti kõrvuti: kogutulu, unikaalsed kliendid, keskmine tellimus."""
    cards = [
        ("total_revenue", "Kogutulu (€)", ",.2f"),
        ("unique_customers", "Unikaalsed kliendid", ",d"),
        ("avg_order_value", "Keskmine tellimus (€)", ",.2f"),
    ]

    fig = go.Figure()
    for i, (key, title, fmt) in enumerate(cards):
        if key not in kpis:
            raise KeyError(f"KPI '{key}' puudub. Leitud: {list(kpis)}")
        fig.add_trace(go.Indicator(
            mode="number",
            value=kpis[key],
            title={"text": title},
            number={"valueformat": fmt},
            domain={"row": 0, "column": i},
        ))

    fig.update_layout(
        grid={"rows": 1, "columns": len(cards)},
        title="Peamised KPI-d",
        template="plotly_white",
    )
    return fig


# --- SAMM 3 + 4: export_results(df, output_dir) — CSV + HTML failidesse -----
def export_results(
    df: pd.DataFrame,
    output_dir: str | Path = "output",
    figures: dict[str, go.Figure] | None = None,
    name: str = "results",
) -> list[str]:
    """
    Salvestab DataFrame'i CSV-sse ja diagrammid HTML-ina output_dir kausta.
    Failinimedes on ajatempel, et korduvad käivitused faile üle ei kirjutaks.

    figures: {"failinimi": fig}, nt {"weekly_revenue": fig_weekly}
    Tagastab loodud failide teed.
    """
    # Suhteline output-kaust asub selle skriptiga samas kaustas.
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved: list[str] = []

    try:
        csv_path = output_path / f"{name}_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # õ/ä/ö/ü korras ka Excelis
        saved.append(str(csv_path))
        logger.info("CSV salvestatud: %s (%d rida)", csv_path, len(df))

        for fig_name, fig in (figures or {}).items():
            html_path = output_path / f"{fig_name}_{timestamp}.html"
            fig.write_html(str(html_path))
            saved.append(str(html_path))
            logger.info("Diagramm salvestatud: %s", html_path)
    except OSError as exc:
        logger.error("Faili salvestamine ebaõnnestus: %s", exc)
        raise

    return saved


# --- Edasijõudnute tase: teavitus Google Chati (webhook) --------------------
def send_notification(kpis: dict, success: bool = True, webhook_url: str = None) -> bool:
    """
    Saadab pipeline'i tulemuse Google Chati.
    Webhooki URL tuleb .env failist (GOOGLE_CHAT_WEBHOOK). Kui seda pole,
    jäetakse teavitus vahele ja pipeline töötab edasi.
    """
    webhook_url = webhook_url or os.getenv("GOOGLE_CHAT_WEBHOOK")
    if not webhook_url:
        logger.info("GOOGLE_CHAT_WEBHOOK puudub, teavitus jäeti vahele.")
        return False

    if success:
        text = (
            "✅ UrbanStyle pipeline õnnestus\n"
            f"Kogutulu: {kpis.get('total_revenue', 0):,.2f} €\n"
            f"Unikaalsed kliendid: {kpis.get('unique_customers', 0):,}\n"
            f"Keskmine tellimus: {kpis.get('avg_order_value', 0):,.2f} €"
        )
    else:
        text = "❌ UrbanStyle pipeline ebaõnnestus. Vaata logi."

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("Teavitus saadetud Google Chati.")
        return True
    except Exception as exc:
        # Teavituse viga ei tohi kogu pipeline'i peatada
        logger.warning("Teavituse saatmine ebaõnnestus: %s", exc)
        return False


# --- SAMM 5: Testi — käivita ja kontrolli, et failid tekivad output/ kausta --
# Käivita: python visualize_export.py
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Näidisandmed kontrollivad diagrammide loomist ja eksporti ilma projektimooduliteta.
    weekly = pd.DataFrame({
        "week": ["2026-W01", "2026-W02", "2026-W03"],
        "total_revenue": [12000, 13500, 14200],
    })
    kpis = {
        "total_revenue": 39700,
        "unique_customers": 42,
        "avg_order_value": 186.38,
    }

    fig_weekly = create_weekly_chart(weekly)
    fig_kpi = create_kpi_summary(kpis)

    files = export_results(
        weekly,
        output_dir=Path(__file__).resolve().parent / "output",
        figures={"weekly_revenue": fig_weekly, "kpi_summary": fig_kpi},
        name="weekly_results",
    )

    print("\nLoodud failid:")
    for f in files:
        print(" -", f)
