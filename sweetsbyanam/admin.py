"""The baker's private order dashboard (password protected)."""
import hmac
from datetime import date
from functools import wraps

import os

from flask import Blueprint, abort, current_app, redirect, render_template, request, send_from_directory, session, url_for

from . import db, orders
from .db import STATUSES, get_db
from .security import require_csrf

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _enabled() -> bool:
    return bool(current_app.config["ADMIN_PASSWORD"])


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _enabled():
            abort(404)  # no password configured: the admin area does not exist
        if not session.get("admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not _enabled():
        abort(404)
    error = None
    ip = request.remote_addr or "unknown"
    limiter = current_app.login_limiter
    if request.method == "POST":
        require_csrf()
        if limiter.blocked(ip):
            error = f"Too many attempts. Try again in {limiter.retry_after(ip) // 60 + 1} minutes."
        elif hmac.compare_digest(request.form.get("password", "").encode(), current_app.config["ADMIN_PASSWORD"].encode()):
            limiter.clear(ip)
            csrf = session.get("csrf")
            session.clear()  # fresh session on login
            session["csrf"], session["admin"], session.permanent = csrf, True, True
            return redirect(url_for("admin.dashboard"))
        else:
            limiter.hit(ip)
            error = "Wrong password."
    return render_template("admin_login.html", error=error), (401 if error else 200)


@bp.post("/logout")
def logout():
    require_csrf()
    session.clear()
    return redirect(url_for("admin.login"))


@bp.get("")
@admin_required
def dashboard():
    status = request.args.get("status", "open")
    where, params = "", ()
    if status == "open":
        where, params = "WHERE status IN ('new', 'confirmed', 'paid')", ()
    elif status in STATUSES:
        where, params = "WHERE status = ?", (status,)
    elif status != "all":
        abort(404)
    rows = get_db().execute(
        f"SELECT * FROM orders {where} ORDER BY event_date ASC, id ASC", params).fetchall()
    counts = {r["status"]: r["n"] for r in get_db().execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status")}
    return render_template("admin_orders.html", rows=rows, status=status, counts=counts, statuses=STATUSES,
                           today=orders.today().isoformat())


@bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def order_detail(order_id):
    db_ = get_db()
    row = db_.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        abort(404)
    if request.method == "POST":
        require_csrf()
        new_status = request.form.get("status", "")
        notes = request.form.get("owner_notes", "")[:2000]
        if new_status not in STATUSES:
            abort(400, "Unknown status.")
        with db_:
            db_.execute("UPDATE orders SET status = ?, owner_notes = ? WHERE id = ?", (new_status, notes, order_id))
        return redirect(url_for("admin.order_detail", order_id=order_id, saved=1))
    event = date.fromisoformat(row["event_date"])
    return render_template("admin_order.html", order=row, items=db.load_items(order_id), statuses=STATUSES,
                           images=db.load_images(order_id),
                           event=event, due=orders.payment_due(event), saved=request.args.get("saved"))


@bp.get("/photos/<int:image_id>")
@admin_required
def photo(image_id):
    """Customers' inspiration photos. Only reachable when logged in as the baker."""
    row = get_db().execute("SELECT filename, content_type FROM order_images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        abort(404)
    return send_from_directory(os.path.abspath(current_app.config["UPLOAD_DIR"]), row["filename"],
                               mimetype=row["content_type"], max_age=0)
