import os
import sqlite3
import threading

import pandas as pd

DATA_DIR = "data"
TABLES_DIR = os.path.join(DATA_DIR, "tables")
DB_PATH = os.path.join(DATA_DIR, "app_state.db")

# Use threading.local to avoid SQLite 'same thread' errors in Streamlit
_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn"):
        # Ensure directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """Initializes the database schema."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            pmid TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            journal TEXT,
            pub_year TEXT,
            abstract TEXT,
            screening_decision TEXT,
            screening_reason TEXT,
            exclusion_category TEXT,
            pdf_download_status TEXT,
            pico_data TEXT,
            rob_data TEXT,
            pipeline_status INTEGER DEFAULT 0
        )
    """)

    # Add columns for backward compatibility if they are missing
    try:
        c.execute("ALTER TABLE articles ADD COLUMN pico_data TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE articles ADD COLUMN rob_data TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE articles ADD COLUMN exclusion_category TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()


def clear_db():
    """Clears all records from the database."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS articles")
    conn.commit()
    init_db()


def import_pubmed_results(df):
    """
    Imports initial PubMed search results into the database.
    Ignores existing PMIDs to avoid overwriting state.
    """
    if df.empty:
        return

    conn = _get_conn()
    # Convert dataframe to list of dicts, replacing NaN with empty string
    df_clean = df.fillna("")
    records = df_clean.to_dict("records")

    c = conn.cursor()
    for row in records:
        c.execute(
            """
            INSERT OR IGNORE INTO articles
            (pmid, doi, title, journal, pub_year, abstract, pipeline_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(row.get("pmid", "")),
                str(row.get("doi", "")),
                str(row.get("title", "")),
                str(row.get("journal", "")),
                str(row.get("pub_year", "")),
                str(row.get("abstract", "")),
                0,  # Fetched
            ),
        )
    conn.commit()


def update_article(pmid, **kwargs):
    """
    Updates specific fields for an article.
    Example: update_article("1234", screening_decision="Included", pipeline_status=1)
    """
    if not kwargs:
        return

    conn = _get_conn()
    c = conn.cursor()

    # Sanitize: convert string 'nan', 'NaN', and Python None/NaN to empty string ""
    sanitized_kwargs = {}
    for k, v in kwargs.items():
        if pd.isna(v) or str(v).lower() == "nan":
            sanitized_kwargs[k] = ""
        else:
            sanitized_kwargs[k] = v

    set_clause = ", ".join([f"{k} = ?" for k in sanitized_kwargs.keys()])
    values = list(sanitized_kwargs.values())
    values.append(str(pmid))

    c.execute(f"UPDATE articles SET {set_clause} WHERE pmid = ?", values)
    conn.commit()


def get_articles_df(filters=None):
    """
    Returns a DataFrame of articles, optionally filtered.
    filters: dict of column=value
    """
    conn = _get_conn()

    query = "SELECT * FROM articles"
    params = []

    if filters:
        conditions = []
        for k, v in filters.items():
            if v is None:
                conditions.append(f"{k} IS NULL")
            else:
                conditions.append(f"{k} = ?")
                params.append(v)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    df = pd.read_sql_query(query, conn, params=params)
    return df


def get_article(pmid):
    """Returns a dictionary representation of a single article, or None."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM articles WHERE pmid = ?", (str(pmid),))
    row = c.fetchone()
    return dict(row) if row else None


# Auto-initialize on import
init_db()
