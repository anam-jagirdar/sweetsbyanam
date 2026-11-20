"""SQLite storage for orders."""
import json
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

STATUSES = ("new", "confirmed", "paid", "completed", "cancelled")
REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L lookalikes

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ref              TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    email            TEXT NOT NULL DEFAULT '',
    phone            TEXT NOT NULL,
    fulfilment       TEXT NOT NULL CHECK (fulfilment IN ('pickup', 'delivery')),
    address          TEXT NOT NULL DEFAULT '',
    event_date       TEXT NOT NULL,
    occasion         TEXT NOT NULL DEFAULT '',
    notes            TEXT NOT NULL DEFAULT '',
    allergies        TEXT NOT NULL DEFAULT '',
    estimate_cents   INTEGER NOT NULL,
    custom_pricing   INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','confirmed','paid','completed','cancelled')),
    owner_notes      TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product     TEXT NOT NULL,
    name        TEXT NOT NULL,
    qty         INTEGER NOT NULL,
    unit        TEXT NOT NULL,
    details     TEXT NOT NULL,
    line_cents  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS order_images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    size          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_order ON order_images(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_status_date ON orders(status, event_date);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def new_ref() -> str:
    return "SBA-" + "".join(secrets.choice(REF_ALPHABET) for _ in range(6))


def save_order(order: dict, images: list | None = None) -> str:
    """Store a cleaned order, its items and its (already saved) inspiration images in one transaction.
    Returns its reference code."""
    db = get_db()
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for _ in range(5):  # a clash on the random reference is astronomically unlikely, but retry anyway
        ref = new_ref()
        try:
            with db:  # commits on success, rolls everything back on error
                cursor = db.execute(
                    "INSERT INTO orders (ref, name, email, phone, fulfilment, address, event_date, occasion, notes,"
                    " allergies, estimate_cents, custom_pricing, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ref, order["name"], order["email"], order["phone"], order["fulfilment"], order["address"],
                     order["event_date"], order["occasion"], order["notes"], order["allergies"],
                     order["estimate_cents"], int(order["has_custom_pricing"]), created))
                db.executemany(
                    "INSERT INTO order_items (order_id, product, name, qty, unit, details, line_cents) VALUES (?,?,?,?,?,?,?)",
                    [(cursor.lastrowid, i["product"], i["name"], i["qty"], i["unit"], json.dumps(i["details"]),
                      i["line_cents"]) for i in order["items"]])
                db.executemany(
                    "INSERT INTO order_images (order_id, filename, original_name, content_type, size) VALUES (?,?,?,?,?)",
                    [(cursor.lastrowid, im["filename"], im["original_name"], im["content_type"], im["size"])
                     for im in images or []])
            return ref
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("could not allocate an order reference")


def load_items(order_id: int) -> list[dict]:
    rows = get_db().execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    return [{**dict(r), "details": json.loads(r["details"])} for r in rows]


def load_images(order_id: int) -> list:
    return get_db().execute("SELECT * FROM order_images WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
