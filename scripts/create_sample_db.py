"""
Creates a sample SQLite database (sample.db) with fictional data
for testing the MCP server without needing a real database.

Usage:
    python scripts/create_sample_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sample.db"


def create_sample_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            city        TEXT,
            created_at  TEXT    DEFAULT (DATE('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            category    TEXT,
            price       REAL    NOT NULL,
            stock       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            status      TEXT    NOT NULL DEFAULT 'pending',
            total       REAL    NOT NULL DEFAULT 0,
            created_at  TEXT    DEFAULT (DATE('now'))
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL REFERENCES orders(id),
            product_id  INTEGER NOT NULL REFERENCES products(id),
            quantity    INTEGER NOT NULL,
            unit_price  REAL    NOT NULL
        );
    """)

    cur.executemany(
        "INSERT OR IGNORE INTO customers (name, email, city) VALUES (?, ?, ?)",
        [
            ("Luke Skywalker",   "luke@rebellion.org",   "Tatooine"),
            ("Leia Organa",      "leia@rebellion.org",   "Alderaan"),
            ("Han Solo",         "han@millennium.com",   "Corellia"),
            ("Lando Calrissian", "lando@cloudcity.com",  "Bespin"),
            ("Padmé Amidala",    "padme@senate.gov",     "Naboo"),
        ],
    )

    cur.executemany(
        "INSERT OR IGNORE INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        [
            ("Lightsaber",          "Weapons",      999.99,  15),
            ("Blaster DL-44",       "Weapons",      349.50,  42),
            ("Hyperdrive Motivator", "Parts",        1200.00,  8),
            ("Bacta Tank",          "Medical",      4500.00,  3),
            ("Datapad",             "Electronics",   89.99,  60),
            ("Thermal Detonator",   "Weapons",       75.00,  20),
            ("Jedi Robes",          "Clothing",     120.00,  30),
        ],
    )

    cur.executemany(
        "INSERT OR IGNORE INTO orders (id, customer_id, status, total, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "completed", 1119.98, "2026-01-10"),
            (2, 2, "completed",  869.49, "2026-01-15"),
            (3, 3, "shipped",   1549.50, "2026-02-03"),
            (4, 4, "pending",    164.99, "2026-03-22"),
            (5, 1, "completed",  120.00, "2026-04-05"),
        ],
    )

    cur.executemany(
        "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        [
            (1, 1, 1,  999.99),
            (1, 5, 1,   89.99),
            (2, 2, 1,  349.50),
            (2, 5, 2,   89.99),
            (2, 7, 1,  120.00),
            (3, 2, 1,  349.50),
            (3, 3, 1, 1200.00),
            (4, 5, 1,   89.99),
            (4, 7, 1,  120.00),
            (5, 7, 1,  120.00),
        ],
    )

    conn.commit()
    conn.close()
    print(f"Sample database created at: {DB_PATH}")


if __name__ == "__main__":
    create_sample_db()
