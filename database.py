"""
database.py - SQLite database manager for junkyard bot
Tracks inventory over time to detect new arrivals
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "inventory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # Inventory table - each vehicle seen at a yard
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            yard        TEXT NOT NULL,
            location    TEXT NOT NULL,
            year        TEXT NOT NULL,
            make        TEXT NOT NULL,
            model       TEXT NOT NULL,
            row         TEXT,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL,
            is_target   INTEGER DEFAULT 0,
            notified    INTEGER DEFAULT 0
        )
    """)

    # eBay price cache table
    c.execute("""
        CREATE TABLE IF NOT EXISTS ebay_prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            make        TEXT NOT NULL,
            model       TEXT NOT NULL,
            year        TEXT NOT NULL,
            part        TEXT NOT NULL,
            avg_price   REAL,
            min_price   REAL,
            max_price   REAL,
            sold_count  INTEGER,
            fetched_at  TEXT NOT NULL
        )
    """)

    # Alert log table
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type  TEXT NOT NULL,
            message     TEXT NOT NULL,
            sent_at     TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def upsert_vehicle(yard, location, year, make, model, row):
    """
    Insert new vehicle or update last_seen.
    Returns (is_new: bool, vehicle_id: int)
    """
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    # Check if already exists
    c.execute("""
        SELECT id FROM inventory
        WHERE yard=? AND location=? AND year=? AND make=? AND model=? AND row=?
    """, (yard, location, year, make, model, row))
    row_data = c.fetchone()

    if row_data:
        # Update last_seen
        c.execute("UPDATE inventory SET last_seen=? WHERE id=?", (now, row_data["id"]))
        conn.commit()
        conn.close()
        return False, row_data["id"]
    else:
        # New vehicle
        c.execute("""
            INSERT INTO inventory (yard, location, year, make, model, row, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (yard, location, year, make, model, row, now, now))
        vid = c.lastrowid
        conn.commit()
        conn.close()
        return True, vid


def mark_as_target(vehicle_id):
    conn = get_conn()
    conn.execute("UPDATE inventory SET is_target=1 WHERE id=?", (vehicle_id,))
    conn.commit()
    conn.close()


def mark_notified(vehicle_id):
    conn = get_conn()
    conn.execute("UPDATE inventory SET notified=1 WHERE id=?", (vehicle_id,))
    conn.commit()
    conn.close()


def get_new_unnotified_targets():
    """Get target vehicles that haven't been alerted yet."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM inventory
        WHERE is_target=1 AND notified=0
        ORDER BY first_seen DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_new_unnotified():
    """Get ALL new vehicles (target or not) that haven't been alerted."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM inventory
        WHERE notified=0
        ORDER BY first_seen DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_summary():
    """Get all vehicles seen today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM inventory
        WHERE first_seen LIKE ?
        ORDER BY yard, location, make, model
    """, (f"{today}%",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ebay_price(make, model, year, part, avg_price, min_price, max_price, sold_count):
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO ebay_prices (make, model, year, part, avg_price, min_price, max_price, sold_count, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (make, model, year, part, avg_price, min_price, max_price, sold_count, now))
    conn.commit()
    conn.close()


def get_ebay_prices(make, model, year):
    """Get latest eBay prices for a vehicle's parts."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT part, avg_price, min_price, max_price, sold_count, fetched_at
        FROM ebay_prices
        WHERE make=? AND model=? AND year=?
        ORDER BY fetched_at DESC
    """, (make, model, str(year))).fetchall()
    conn.close()
    # Return only most recent per part
    seen = {}
    for r in rows:
        if r["part"] not in seen:
            seen[r["part"]] = dict(r)
    return seen


def log_alert(alert_type, message):
    conn = get_conn()
    conn.execute("""
        INSERT INTO alert_log (alert_type, message, sent_at)
        VALUES (?, ?, ?)
    """, (alert_type, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_weekly_price_trends():
    """Get eBay price data for weekly trend report."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT make, model, year, part, avg_price, sold_count, fetched_at
        FROM ebay_prices
        ORDER BY make, model, year, part, fetched_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
