import pandas as pd

DATE_COL = "sale_date"
CUSTOMER_COL = "customer_id"
QTY_COL = "quantity"
PRICE_COL = "unit_price"
# Kui müügitabelis on valmis tulu veerg, kasutatakse esimest leitud:
REVENUE_COLS = ["total_amount", "revenue", "total", "amount", "total_price", "line_total"]
 
 
def _revenue(df: pd.DataFrame) -> pd.Series:
    """Tulu rea kohta: valmis tulu veerg või quantity * unit_price."""
    for col in REVENUE_COLS:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0)
    if QTY_COL in df.columns and PRICE_COL in df.columns:
        qty = pd.to_numeric(df[QTY_COL], errors="coerce").fillna(0)
        price = pd.to_numeric(df[PRICE_COL], errors="coerce").fillna(0)
        return qty * price
    raise KeyError(
        f"Tulu arvutamiseks puudub veerg. Leitud veerud: {list(df.columns)}. "
        "Muuda transform.py alguses REVENUE_COLS / QTY_COL / PRICE_COL."
    )
 
 
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Eemalda duplikaadid, käsitle NULL-id, teisenda kuupäevad datetime'iks."""
    df = df.copy()
    df = df.drop_duplicates()
 
    # Kuupäevad: vigased väärtused muutuvad NaT-iks
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
 
    # Ridu, kus võtmeväljad puuduvad, ei saa kasutada
    required = [c for c in (DATE_COL, CUSTOMER_COL) if c in df.columns]
    df = df.dropna(subset=required)
 
    # Arvuliste veergude NULL -> 0, tekstiliste NULL -> "unknown"
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].fillna("unknown")
 
    return df.reset_index(drop=True)
 
 
def calculate_weekly_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Grupeeri nädalate kaupa: tulu, tellimuste arv, keskmine tellimus."""
    df = df.copy()
    df["revenue"] = _revenue(df)
    df["week"] = df[DATE_COL].dt.to_period("W").dt.start_time
 
    return (
        df.groupby("week")
        .agg(
            total_revenue=("revenue", "sum"),
            order_count=("revenue", "count"),
            avg_order_value=("revenue", "mean"),
        )
        .reset_index()
    )
 
 
def calculate_kpis(df: pd.DataFrame) -> dict:
    """Tagasta KPI-d: kogutulu, unikaalsed kliendid, keskmine tellimuse väärtus."""
    revenue = _revenue(df)
    return {
        "total_revenue": float(revenue.sum()),
        "unique_customers": int(df[CUSTOMER_COL].nunique()),
        "avg_order_value": float(revenue.mean()) if len(df) else 0.0,
    }
 
 
def merge_datasets(df_sales: pd.DataFrame, df_customers: pd.DataFrame) -> pd.DataFrame:
    """Liida müügi- ja kliendiandmed customer_id järgi."""
    return pd.merge(
        df_sales, df_customers, on=CUSTOMER_COL, how="left",
        suffixes=("", "_customer"),
    )
 