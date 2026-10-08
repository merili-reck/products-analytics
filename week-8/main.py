# main.py: käivitab kogu ahela algusest lõpuni
# Supabase (Roll A) -> puhastamine ja arvutused (Roll B) -> diagrammid ja failid (Roll C)
# Käivita: python main.py

import logging
from pathlib import Path

import pandas as pd

from data_fetcher import fetch_sales, fetch_customers, DataFetchError, DEFAULT_END_DATE
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
    send_notification,
)

logger = logging.getLogger(__name__)

# Varu-CSV kaust (kasutatakse ainult siis, kui Supabase ei vasta)
CSV_DIR = Path(__file__).parent / "csv"
OUTPUT_DIR = Path(__file__).parent / "output"


def _load_from_csv() -> tuple:
    """Varulahendus: loe andmed csv/ kaustast, sama kuupäevapiiranguga kui Supabase'ist."""
    sales_path = CSV_DIR / "sales.csv"
    customers_path = CSV_DIR / "customers.csv"
    if not sales_path.exists() or not customers_path.exists():
        raise FileNotFoundError(
            f"Supabase ei vastanud ja varu-CSV faile ei leitud kaustast {CSV_DIR}. "
            "Lisa sinna sales.csv ja customers.csv."
        )

    sales = pd.read_csv(sales_path)
    customers = pd.read_csv(customers_path)

    # Sama piirang nagu data_fetcher.py-s: ainult müügid enne DEFAULT_END_DATE
    dates = pd.to_datetime(sales["sale_date"], errors="coerce")
    sales = sales[dates < pd.Timestamp(DEFAULT_END_DATE)]
    return sales, customers


def load_data() -> tuple:
    """Päri andmed Supabase'ist; kui see ebaõnnestub, kasuta varu-CSV faile."""
    try:
        sales = fetch_sales()
        customers = fetch_customers()
        logger.info("Andmed päriti Supabase'ist.")
    except DataFetchError as exc:
        logger.warning("Supabase ei vastanud (%s). Kasutan varu-CSV faile.", exc)
        sales, customers = _load_from_csv()
        logger.info("Andmed loeti CSV failidest.")

    logger.info("Müügiridu: %d, kliente: %d", len(sales), len(customers))
    return sales, customers


def main():
    # 1. Andmete pärimine (Roll A)
    sales_raw, customers_raw = load_data()

    # 2. Puhastamine ja arvutused (Roll B)
    sales = clean_data(sales_raw)
    customers = clean_data(customers_raw)
    weekly = calculate_weekly_aggregates(sales)
    kpis = calculate_kpis(sales)
    merged = merge_datasets(sales, customers)

    # 3. Diagrammid ja failid (Roll C)
    fig_weekly = create_weekly_chart(weekly)
    fig_kpi = create_kpi_summary(kpis)
    files = export_results(
        weekly,
        output_dir=str(OUTPUT_DIR),
        figures={"weekly_revenue": fig_weekly, "kpi_summary": fig_kpi},
        name="weekly_results",
    )

    # 4. Teavitus (valikuline, töötab ainult kui .env-is on GOOGLE_CHAT_WEBHOOK)
    send_notification(kpis, success=True)

    # Kokkuvõte terminali
    print("\n=== KPI-d ===")
    print(f"Kogutulu: {kpis['total_revenue']:,.2f} €")
    print(f"Unikaalsed kliendid: {kpis['unique_customers']:,}")
    print(f"Keskmine tellimus: {kpis['avg_order_value']:,.2f} €")
    print(f"\nNädalaid: {len(weekly)}, liidetud ridu: {len(merged)}")
    print("\nLoodud failid:")
    for f in files:
        print(" -", f)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    main()
