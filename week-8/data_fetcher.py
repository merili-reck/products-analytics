# data_fetcher.py: Roll A (API Query / Andmete pärimine)
# Pärib UrbanStyle.ltd müügi-, kliendi- ja tooteandmed Supabase API-st
# ja tagastab igaühe pandas DataFrame'ina.

# --- SAMM 1: Impordi teegid ja loo Supabase client .env põhiselt ----------
import os
import time
import logging

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# load_dotenv() peab olema ENNE os.getenv() kasutamist
load_dotenv()

logger = logging.getLogger(__name__)

# Seaded
PAGE_SIZE = 1000      # ridu ühe päringu kohta (Supabase annab korraga max 1000)
MAX_RETRIES = 3       # mitu korda ebaõnnestunud päringut proovitakse
BASE_DELAY = 1        # sekundites; ooteajad on 1s, 2s, 4s ...

# Tabelite ja veergude nimed. Muuda, kui andmebaasis on teised nimed.
SALES_TABLE = "sales"
CUSTOMERS_TABLE = "customers"
PRODUCTS_TABLE = "products"
SALES_DATE_COLUMN = "sale_date"

# Vaikimisi lõppkuupäev (nagu loengus): võetakse müügid ENNE seda kuupäeva,
# ehk andmed kuni 28.02.2025 ja kogu märts jääb välja.
DEFAULT_END_DATE = "2025-03-01"


class DataFetchError(Exception):
    """Viga, kui andmeid ei õnnestu Supabase'ist pärida."""


_client = None


def get_client() -> Client:
    """Loob Supabase clienti .env väärtustest üks kord ja kasutab seda edasi."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise DataFetchError(
                "SUPABASE_URL või SUPABASE_KEY puudub. Kontrolli, et .env fail "
                "on samas kaustas ja sisaldab mõlemat väärtust."
            )
        _client = create_client(url, key)
    return _client


# --- SAMM 4: Veakäsitlus (try/except) + retry loogika ----------------------
def _is_auth_error(exc: Exception) -> bool:
    """Tuvastab vale API key, et mitte asjatult uuesti proovida."""
    msg = str(exc).lower()
    return any(s in msg for s in ("invalid api key", "401", "jwt", "unauthorized"))


def _execute_with_retry(build_query, description: str):
    """Käivitab päringu; vea korral ootab 1s, 2s, 4s ... ja proovib uuesti
    (exponential backoff)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return build_query().execute()
        except Exception as exc:
            # Vale API key: uuesti proovimine ei aita, anna kohe selge teade
            if _is_auth_error(exc):
                raise DataFetchError(
                    "Vale API key: Supabase lükkas päringu tagasi. Kontrolli "
                    f"SUPABASE_KEY väärtust .env failis. (Detailid: {exc})"
                ) from exc
            # Kõik katsed läbi: anna alla
            if attempt == MAX_RETRIES:
                raise DataFetchError(
                    f"{description} ebaõnnestus pärast {MAX_RETRIES} katset: {exc}"
                ) from exc
            # Oota ja proovi uuesti (iga kord kaks korda kauem)
            delay = BASE_DELAY * 2 ** (attempt - 1)
            logger.warning(
                "%s ebaõnnestus (katse %d/%d): %s. Proovin uuesti %d s pärast...",
                description, attempt, MAX_RETRIES, exc, delay,
            )
            time.sleep(delay)


# Pagination: pärib KÕIK read lehekülg-lehekülje kaupa (1000 rida korraga)
def _fetch_all(table: str, apply_filters=None) -> pd.DataFrame:
    client = get_client()
    rows = []
    start = 0

    while True:
        end = start + PAGE_SIZE - 1

        def build():
            query = client.table(table).select("*")
            if apply_filters:
                query = apply_filters(query)
            return query.range(start, end)

        response = _execute_with_retry(build, f"'{table}' read {start}-{end}")
        batch = response.data or []
        rows.extend(batch)
        logger.info("'%s': päriti %d rida (kokku %d)", table, len(batch), len(rows))

        # Kui tuli vähem kui 1000 rida, oli see viimane lehekülg
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return pd.DataFrame(rows)


# --- SAMM 2: fetch_sales(start_date, end_date) koos kuupäevafiltritega -----
def fetch_sales(start_date=None, end_date=DEFAULT_END_DATE) -> pd.DataFrame:
    """
    Pärib müügiandmed kuupäeva järgi filtreerituna.

    start_date: alates sellest kuupäevast (kaasa arvatud), valikuline.
    end_date:   ENNE seda kuupäeva (kuupäev ise jääb välja, nagu loengu .lt).
                Vaikimisi '2025-03-01'.
    Näide: fetch_sales()                    # kõik müügid enne 01.03.2025
           fetch_sales('2025-01-01')        # 01.01.2025 kuni 28.02.2025
    """
    def filters(query):
        if start_date:
            query = query.gte(SALES_DATE_COLUMN, str(start_date))
        if end_date:
            # .lt = "väiksem kui", seega end_date ise ei ole kaasas
            query = query.lt(SALES_DATE_COLUMN, str(end_date))
        return query

    try:
        df = _fetch_all(SALES_TABLE, filters)
        if df.empty:
            logger.warning(
                "fetch_sales tagastas 0 rida (algus=%s, lõpp=%s). Kontrolli "
                "kuupäevafiltreid või proovi ilma nendeta.", start_date, end_date,
            )
        return df
    except DataFetchError as exc:
        logger.error("fetch_sales ebaõnnestus: %s", exc)
        raise


# --- SAMM 3: fetch_customers() ja fetch_products() analoogselt -------------
def fetch_customers() -> pd.DataFrame:
    """Pärib kõik kliendiandmed."""
    try:
        df = _fetch_all(CUSTOMERS_TABLE)
        if df.empty:
            logger.warning("fetch_customers tagastas 0 rida.")
        return df
    except DataFetchError as exc:
        logger.error("fetch_customers ebaõnnestus: %s", exc)
        raise


def fetch_products() -> pd.DataFrame:
    """Pärib kõik tooteandmed."""
    try:
        df = _fetch_all(PRODUCTS_TABLE)
        if df.empty:
            logger.warning("fetch_products tagastas 0 rida.")
        return df
    except DataFetchError as exc:
        logger.error("fetch_products ebaõnnestus: %s", exc)
        raise


# --- SAMM 5: Testi: prindi ridade arv ja .head() iga DataFrame'i kohta -----
# Käivita: python data_fetcher.py
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    tests = {
        "sales": lambda: fetch_sales(),
        "customers": fetch_customers,
        "products": fetch_products,
    }

    for name, func in tests.items():
        print(f"\n=== {name} ===")
        try:
            df = func()
            print(f"Ridu: {len(df)}")
            print(df.head())
        except DataFetchError as exc:
            print(f"VIGA: {exc}")
