# pipeline.py
# Roll D – kogu UrbanStyle'i pipeline'i käivitamine
#
# A: Supabase'ist andmete pärimine
# B: andmete puhastamine ja arvutused
# C: diagrammid ja tulemuste salvestamine
#
# Käivitamine:
# python pipeline.py

import logging
import time
from pathlib import Path

from data_fetcher import fetch_sales, fetch_customers
from transform import (
    clean_data,
    calculate_weekly_aggregates,
    calculate_kpis,
    merge_datasets,
)
from visualize_export import (
    create_weekly_chart,
    create_kpi_summary,
    export_results,
)


# ---------------------------------------------------------
# LOGIMINE
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------

def run_pipeline():
    """Käivita kogu UrbanStyle'i pipeline algusest lõpuni."""

    start_time = time.time()

    try:
        # -------------------------------------------------
        # 1. EXTRACT – Roll A
        # -------------------------------------------------

        logger.info("=== PIPELINE START ===")
        logger.info("EXTRACT: toon andmed Supabase'ist")

        sales_raw = fetch_sales()
        customers_raw = fetch_customers()

        logger.info(
            "EXTRACT valmis: %d müüki, %d klienti",
            len(sales_raw),
            len(customers_raw),
        )

        # -------------------------------------------------
        # 2. TRANSFORM – Roll B
        # -------------------------------------------------

        logger.info("TRANSFORM: puhastan ja töötlen andmeid")

        sales = clean_data(sales_raw)
        customers = clean_data(customers_raw)

        weekly = calculate_weekly_aggregates(sales)
        kpis = calculate_kpis(sales)
        merged = merge_datasets(sales, customers)

        logger.info(
            "TRANSFORM valmis: %d puhastatud müüki",
            len(sales),
        )

        # -------------------------------------------------
        # 3. VISUALIZE – Roll C
        # -------------------------------------------------

        logger.info("VISUALIZE: loon diagrammid")

        weekly_chart = create_weekly_chart(weekly)
        kpi_chart = create_kpi_summary(kpis)

        logger.info("VISUALIZE valmis")

        # -------------------------------------------------
        # 4. EXPORT – Roll C
        # -------------------------------------------------

        logger.info("EXPORT: salvestan tulemused")

        files = export_results(
            weekly,
            output_dir=OUTPUT_DIR,
            figures={
                "weekly_revenue": weekly_chart,
                "kpi_summary": kpi_chart,
            },
            name="weekly_results",
        )

        logger.info("EXPORT valmis")

        # -------------------------------------------------
        # 5. KOKKUVÕTE
        # -------------------------------------------------

        elapsed = time.time() - start_time

        print("\n" + "=" * 50)
        print("PIPELINE EDUKALT LÕPETATUD")
        print("=" * 50)

        print(f"Kogutulu:          {kpis['total_revenue']:,.2f} €")
        print(f"Unikaalsed kliendid: {kpis['unique_customers']:,}")
        print(f"Keskmine tellimus: {kpis['avg_order_value']:,.2f} €")
        print(f"Nädalaid:          {len(weekly)}")
        print(f"Liidetud ridu:     {len(merged)}")
        print(f"Käivitusaeg:       {elapsed:.2f} sekundit")

        print("\nLoodud failid:")
        for file_path in files:
            print(f" - {file_path}")

        print("=" * 50)

        return {
            "sales": sales,
            "customers": customers,
            "weekly": weekly,
            "kpis": kpis,
            "merged": merged,
            "files": files,
            "elapsed": elapsed,
        }

    except Exception as exc:
        elapsed = time.time() - start_time

        logger.error("PIPELINE EBAÕNNESTUS: %s", exc)

        print("\n" + "=" * 50)
        print("PIPELINE EBAÕNNESTUS")
        print("=" * 50)
        print(f"Viga: {exc}")
        print(f"Aeg kuni veani: {elapsed:.2f} sekundit")
        print("=" * 50)

        return None


# ---------------------------------------------------------
# KÄIVITAMINE
# ---------------------------------------------------------

if __name__ == "__main__":
    run_pipeline()