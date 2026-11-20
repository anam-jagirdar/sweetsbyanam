"""SweetsbyAnam: website and online order system for a home bakery."""
import json
import os
import secrets
from datetime import date

from flask import Flask, abort, jsonify, render_template, request, url_for

from . import admin, db, menu, notify, orders, uploads
from .security import RateLimiter, add_security_headers, csrf_token

IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".webp")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("SWEETS_DB", os.path.join(os.getcwd(), "sweetsbyanam.sqlite")),
        # Set SECRET_KEY in real use. Without it a random key is made at startup, which just means
        # the admin has to log in again after each restart.
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),  # empty = admin area switched off
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SWEETS_HTTPS") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        MAX_CONTENT_LENGTH=64 * 1024,  # everything except the order form (which allows photos, below)
        # Customers' inspiration photos live here, outside the public static folder.
        UPLOAD_DIR=os.environ.get("SWEETS_UPLOADS", ""),
        SMTP_HOST=os.environ.get("SMTP_HOST", ""),
        SMTP_PORT=_env_int("SMTP_PORT", 587),
        SMTP_USER=os.environ.get("SMTP_USER", ""),
        SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
        SMTP_FROM=os.environ.get("SMTP_FROM", ""),
        NOTIFY_EMAIL=os.environ.get("NOTIFY_EMAIL", menu.BUSINESS["email"]),
        ORDERS_PER_HOUR=5,
        LOGIN_FAILURES_PER_WINDOW=5,
        TRUST_PROXY=os.environ.get("TRUST_PROXY") == "1",
    )
    if config:
        app.config.update(config)
    if app.config["TRUST_PROXY"]:  # behind a host's load balancer, so client IPs come from its header
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.config["UPLOAD_DIR"]:
        app.config["UPLOAD_DIR"] = os.path.join(os.path.dirname(os.path.abspath(app.config["DATABASE"])), "uploads")

    app.order_limiter = RateLimiter(app.config["ORDERS_PER_HOUR"], 3600)
    app.login_limiter = RateLimiter(app.config["LOGIN_FAILURES_PER_WINDOW"], 300)
    app.teardown_appcontext(db.close_db)
    app.after_request(add_security_headers)
    app.register_blueprint(admin.bp)

    @app.context_processor
    def inject():
        return {"biz": menu.BUSINESS, "money": menu.money, "price_label": menu.price_label, "rules": menu,
                "csrf_token": csrf_token}

    # ------------------------------------------------------------------ public pages
    def static_images(folder: str, stem: str | None = None):
        path = os.path.join(app.static_folder, folder)
        if not os.path.isdir(path):
            return [] if stem is None else None
        names = sorted(os.listdir(path))
        if stem is not None:
            return next((f"{folder}/{n}" for n in names if n.lower() in {stem + e for e in IMAGE_TYPES}), None)
        return [f"{folder}/{n}" for n in names if n.lower().endswith(IMAGE_TYPES)]

    @app.get("/")
    def home():
        return render_template("home.html", gallery=static_images("gallery")[:6], products=menu.PRODUCTS)

    @app.get("/menu")
    def menu_page():
        photos = {key: static_images("menu", key) for key in menu.PRODUCTS}
        treats = {k: p for k, p in menu.PRODUCTS.items() if p["group"] == "treats"}
        packs = {k: p for k, p in menu.PRODUCTS.items() if p["group"] == "packs"}
        return render_template("menu.html", treats=treats, packs=packs, photos=photos, m=menu,
                               pack_summary=menu.pack_summary)

    @app.get("/gallery")
    def gallery():
        return render_template("gallery.html", photos=static_images("gallery"))

    @app.get("/order")
    def order_page():
        earliest = orders.earliest_event_date()
        return render_template("order.html", earliest=earliest.isoformat(), earliest_pretty=earliest.strftime("%B ")
                               + str(earliest.day), menu_data=menu.client_menu(), closed=sorted(menu.CLOSED_DATES),
                               products=menu.PRODUCTS)

    # ------------------------------------------------------------------ order API
    def api_error(status, code, message, fields=None, headers=None):
        body = {"error": {"code": code, "message": message}}
        if fields:
            body["error"]["fields"] = fields
        response = jsonify(body)
        response.status_code = status
        for k, v in (headers or {}).items():
            response.headers[k] = v
        return response

    @app.post("/api/orders")
    def create_order():
        ip = request.remote_addr or "unknown"
        if app.order_limiter.blocked(ip):  # checked first, before any photos are read
            return api_error(429, "too_many_orders", "You've sent several orders recently. Please email us instead.",
                             headers={"Retry-After": str(app.order_limiter.retry_after(ip))})
        files = []
        if request.mimetype == "multipart/form-data":  # the website form: order details as JSON text + photos
            request.max_content_length = uploads.MAX_REQUEST_BYTES  # allow photos on this one route only
            try:
                data = json.loads(request.form.get("order", ""))
            except ValueError:
                data = None
            files = request.files.getlist("images")
        else:  # plain JSON, no photos (handy for scripts and tests)
            data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return api_error(400, "invalid_json", "We couldn't read that order. Please try again.")
        if data.get("website"):  # hidden "honeypot" field only bots fill in: pretend it worked, store nothing
            return jsonify({"ref": "SBA-XXXXXX", "redirect": url_for("home")}), 201

        problems = {}
        try:
            order = orders.clean_order(data)
        except orders.OrderInvalid as exc:
            order, problems = None, dict(exc.fields)
        images, image_problems = uploads.clean_images(files)
        problems.update(image_problems)
        if problems:
            return api_error(422, "validation_failed", "Please fix the highlighted fields.", problems)

        saved = uploads.store(app.config["UPLOAD_DIR"], images)
        try:
            ref = db.save_order(order, saved)
        except Exception:
            uploads.remove(app.config["UPLOAD_DIR"], saved)  # don't leave orphaned photos behind
            raise
        app.order_limiter.hit(ip)
        notify.notify_new_order(app.config, ref, order, url_for("admin.dashboard", _external=True), len(saved))
        return jsonify({"ref": ref, "redirect": url_for("thanks", ref=ref)}), 201

    @app.get("/order/thanks/<ref>")
    def thanks(ref):
        row = db.get_db().execute("SELECT * FROM orders WHERE ref = ?", (ref,)).fetchone()
        if row is None:
            abort(404)
        event = date.fromisoformat(row["event_date"])
        return render_template("thanks.html", order=row, items=db.load_items(row["id"]), event=event,
                               image_count=len(db.load_images(row["id"])),
                               due=orders.payment_due(event), first_name=row["name"].split()[0])

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=getattr(e, "description", "Bad request.")), 400

    @app.errorhandler(413)
    def too_large(_e):
        return api_error(413, "too_large", "That is too large. Photos must be 5 MB or smaller, and no more than 5 of them.",
                         {"images": "Your photos are too big in total. Try fewer or smaller photos."})

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("error.html", code=500, message="Something went wrong on our side."), 500

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    with app.app_context():
        db.init_db()
    return app
