import os
import sqlite3
import re
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "stocks.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "datasource.csv")

SCHEMA_DESCRIPTION = """
Table: stocks
Columns:
- symbol (TEXT): Ticker emiten saham (contoh: 'PSAB', 'MARK', 'SIDO', 'BSSR', dll.)
- current_ratio (REAL): Rasio lancar / likuiditas (Current Ratio). Nilai > 1.5 atau > 2 dianggap likuiditas sehat.
- der (REAL): Debt-to-Equity Ratio (Rasio Utang terhadap Modal). Nilai < 0.5 atau < 1 dianggap utang rendah / aman.
- dividend_yield (REAL): Persentase yield dividen (contoh: 8.5 berarti 8.5%). Nilai > 7 dianggap dividen tinggi/royal.
- fcf_ttm (REAL): Free Cash Flow 12 bulan terakhir dalam Rupiah (contoh: 1158531000000 = ~Rp 1.16 T). Nilai > 0 berarti arus kas bebas positif.
- gross_margin (REAL): Persentase Margin Laba Kotor (contoh: 40.5 berarti 40.5%). Nilai > 30 atau > 40 dianggap margin tebal.
- net_profit_ttm (REAL): Laba bersih 12 bulan terakhir dalam Rupiah (contoh: 962387000000 = ~Rp 962 M).
- roe_ttm (REAL): Return on Equity 12 bulan terakhir dalam persen (contoh: 25.4 berarti 25.4%). Nilai > 15 atau > 20 dianggap sangat profitable.
"""

def init_db(force: bool = False):
    """
    Ingest datasource.csv into SQLite stocks.db.
    """
    if not force and os.path.exists(DB_PATH):
        # Check if table has data
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='stocks'")
            if cursor.fetchone()[0] > 0:
                cursor.execute("SELECT count(*) FROM stocks")
                if cursor.fetchone()[0] > 0:
                    return

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Source file not found: {CSV_PATH}")

    # Read tab-delimited or auto-detect separator
    try:
        df = pd.read_csv(CSV_PATH, sep="\t")
        if len(df.columns) <= 1:
            df = pd.read_csv(CSV_PATH)
    except Exception:
        df = pd.read_csv(CSV_PATH, sep=None, engine="python")

    # Clean column names
    col_mapping = {
        "Symbol": "symbol",
        "Current Ratio": "current_ratio",
        "DER": "der",
        "Dividend Yield": "dividend_yield",
        "FCF (TTM)": "fcf_ttm",
        "Gross Margin": "gross_margin",
        "Net Profit (TTM)": "net_profit_ttm",
        "ROE (TTM)": "roe_ttm"
    }
    
    # Strip whitespace from headers
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=col_mapping)

    # Convert numeric columns
    numeric_cols = ["current_ratio", "der", "dividend_yield", "fcf_ttm", "gross_margin", "net_profit_ttm", "roe_ttm"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("stocks", con=conn, if_exists="replace", index=False)
        # Create an index on symbol
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol)")

def execute_safe_query(query: str):
    """
    Safely executes read-only SQL queries on SQLite.
    Returns (records: list[dict], error: str | None).
    """
    # Clean query
    cleaned_query = query.strip()
    if cleaned_query.endswith(";"):
        cleaned_query = cleaned_query[:-1].strip()

    # Disallow destructive/modifying operations
    disallowed_patterns = [
        r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b",
        r"\bALTER\b", r"\bTRUNCATE\b", r"\bCREATE\b", r"\bREPLACE\b",
        r"\bEXEC\b", r"\bPRAGMA\b", r"\bATTACH\b", r"\bDETACH\b"
    ]
    for pattern in disallowed_patterns:
        if re.search(pattern, cleaned_query, re.IGNORECASE):
            return [], f"Disallowed SQL operation detected matching: {pattern}"

    # Must start with SELECT or WITH
    if not (cleaned_query.upper().startswith("SELECT") or cleaned_query.upper().startswith("WITH")):
        return [], "Query must begin with SELECT or WITH."

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(cleaned_query)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            return results, None
    except Exception as e:
        return [], f"SQL Execution Error: {str(e)}"

def get_all_stocks():
    """
    Returns all stock records sorted by ROE descending.
    """
    init_db()
    results, err = execute_safe_query("SELECT * FROM stocks ORDER BY roe_ttm DESC")
    return results if not err else []

if __name__ == "__main__":
    init_db(force=True)
    all_s = get_all_stocks()
    print(f"Initialized database with {len(all_s)} stocks.")
    print("Sample stock:", all_s[0] if all_s else "Empty")
