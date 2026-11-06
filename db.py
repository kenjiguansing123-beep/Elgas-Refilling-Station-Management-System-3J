"""Database setup (SQLite). All SQL is kept in db.py, services.py and api.py so it can move to MySQL later."""
import os
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash

PAYMENT_STATUSES = ("Paid", "Unpaid")

# The one login account (change before real use)
LOGIN_EMAIL = "Elgas"
LOGIN_PASSWORD = "Elgas123"

# Starting prices are PLACEHOLDERS (about P118 per kg). Replace them on the Price List page.
DEFAULT_PRICES = [(2.7, 319.0), (5.0, 591.0), (7.0, 827.0), (11.0, 1300.0), (22.0, 2600.0), (50.0, 5909.0)]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_list (
    size_kg REAL PRIMARY KEY,
    price REAL NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'Paid',
    tank_count INTEGER NOT NULL,
    total_kg REAL NOT NULL,
    total REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transaction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL,
    size_kg REAL NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _is_old_schema(path):
    """The first test version stored one price per kg and a Paid/Unpaid status. It cannot be reused."""
    if not os.path.exists(path):
        return False
    conn = sqlite3.connect(path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    conn.close()
    return "price_per_kg" in cols


def init_db(path):
    if _is_old_schema(path):  # keep the old file as a backup and start a fresh database
        os.replace(path, path.replace(".db", "") + "_old_backup.db")
    conn = sqlite3.connect(path)
    if "username" in [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]:
        conn.execute("DROP TABLE users")  # older test version used a username column
    conn.executescript(SCHEMA)
    # Upgrade existing databases without deleting customer/refill history.
    transaction_columns = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    if "payment_status" not in transaction_columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'Paid'")
    conn.execute("UPDATE transactions SET payment_status='Paid' WHERE payment_status IS NULL OR payment_status=''")

    # Remove the retired payment_method column while preserving all transaction history.
    transaction_columns = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    if "payment_method" in transaction_columns:
        try:
            conn.execute("ALTER TABLE transactions DROP COLUMN payment_method")
        except sqlite3.OperationalError:
            # Compatibility fallback for older SQLite versions.
            conn.executescript("""
                CREATE TABLE transactions_clean (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    payment_status TEXT NOT NULL DEFAULT 'Paid',
                    tank_count INTEGER NOT NULL,
                    total_kg REAL NOT NULL,
                    total REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO transactions_clean
                    (id, customer_name, payment_status, tank_count, total_kg, total, created_at, updated_at)
                SELECT id, customer_name, payment_status, tank_count, total_kg, total, created_at, updated_at
                FROM transactions;
                DROP TABLE transactions;
                ALTER TABLE transactions_clean RENAME TO transactions;
            """)

    # Remove the retired availability flag from older price-list databases.
    price_columns = [r[1] for r in conn.execute("PRAGMA table_info(price_list)").fetchall()]
    if "active" in price_columns:
        try:
            conn.execute("ALTER TABLE price_list DROP COLUMN active")
        except sqlite3.OperationalError:
            conn.executescript("""
                CREATE TABLE price_list_clean (
                    size_kg REAL PRIMARY KEY,
                    price REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO price_list_clean (size_kg, price, updated_at)
                SELECT size_kg, price, updated_at FROM price_list;
                DROP TABLE price_list;
                ALTER TABLE price_list_clean RENAME TO price_list;
            """)
    if not conn.execute("SELECT 1 FROM users WHERE email=?", (LOGIN_EMAIL,)).fetchone():
        conn.execute("DELETE FROM users")  # the system has one account
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?,?)",
                     (LOGIN_EMAIL, generate_password_hash(LOGIN_PASSWORD)))
    if conn.execute("SELECT COUNT(*) FROM price_list").fetchone()[0] == 0:
        conn.executemany("INSERT INTO price_list (size_kg, price, updated_at) VALUES (?,?,?)",
                         [(s, p, now()) for s, p in DEFAULT_PRICES])
    conn.commit()
    conn.close()
