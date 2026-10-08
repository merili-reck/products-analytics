from pathlib import Path
 
import pandas as pd
 
from transform import (
    clean_data,
    calculate_weekly_aggregates,
    calculate_kpis,
    merge_datasets,
)
 
# csv kaust asub samas kaustas, kus on main.py
CSV_DIR = Path(__file__).parent / "csv"
 
 
def main():
    sales_raw = pd.read_csv(CSV_DIR / "sales.csv")
    customers_raw = pd.read_csv(CSV_DIR / "customers.csv")
 
    # Kontrolli veergude nimesid: transform.py konstandid peavad nendega klappima
    print("sales veerud:", list(sales_raw.columns))
    print("customers veerud:", list(customers_raw.columns))
 
    sales = clean_data(sales_raw)
    customers = clean_data(customers_raw)
 
    weekly = calculate_weekly_aggregates(sales)
    kpis = calculate_kpis(sales)
    merged = merge_datasets(sales, customers)
 
    print("\n=== Nädalased näitajad ===")
    print(weekly)
    print("\n=== KPI-d ===")
    print(kpis)
    print("\n=== Liidetud andmed ===")
    print(merged.head())
 
 
if __name__ == "__main__":
    main()
 