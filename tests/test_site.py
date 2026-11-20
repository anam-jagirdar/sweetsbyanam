import copy
import os
import re
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from sweetsbyanam import create_app, menu, notify, orders
from sweetsbyanam.db import get_db

PASSWORD = "correct horse battery"


def future(days=10):
    return (orders.today() + timedelta(days=days)).isoformat()


def good_order(**changes):
    order = {
        "name": "Sam Customer", "email": "sam@example.com", "phone": "(847) 555-0123",
        "fulfilment": "pickup", "address": "", "event_date": future(), "occasion": "Birthday",
        "allergies": "", "notes": "", "website": "",
        "items": [{"product": "cupcakes", "qty": 2, "mode": "combo", "combo": "Dubai Chocolate", "notes": ""}],
    }
    order.update(changes)
    return order


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"DATABASE": os.path.join(self.tmp.name, "t.sqlite"), "SECRET_KEY": "test",
                               "ADMIN_PASSWORD": PASSWORD, "TESTING": True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, order):
        return self.client.post("/api/orders", json=order)

    def db_rows(self, sql, *args):
        with self.app.app_context():
            return get_db().execute(sql, args).fetchall()

    def login(self, client=None):
        client = client or self.client
        page = client.get("/admin/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return client.post("/admin/login", data={"password": PASSWORD, "csrf_token": token}), token


class MenuDataTests(unittest.TestCase):
    def test_every_product_has_valid_price_unit_and_group(self):
        for key, p in menu.PRODUCTS.items():
            self.assertGreater(p["price"], 0, key)
            self.assertIn(p["unit"], menu.QUANTITY_LIMITS, key)
            self.assertIn(p["group"], ("treats", "packs"), key)

    def test_prices_match_what_anam_listed(self):
        expected = {"cupcakes": 3500, "cake_pops": 4000, "custom_cake": 5000, "mini_cheesecakes": 4500,
                    "brownies": 3000, "dipped": 3000, "shooters": 4000,
                    "pack_standard": 13000, "pack_deluxe": 27500, "pack_premium": 40000}
        self.assertEqual({k: p["price"] for k, p in menu.PRODUCTS.items()}, expected)
        self.assertEqual({k for k, p in menu.PRODUCTS.items() if p["plus"]},
                         {"custom_cake", "dipped", "pack_standard", "pack_deluxe", "pack_premium"})

    def test_flavor_counts(self):
        self.assertEqual((len(menu.CAKE_FLAVORS), len(menu.FROSTING_FLAVORS), len(menu.COMBOS)), (11, 15, 17))
        self.assertEqual((len(menu.CHEESECAKE_FLAVORS), len(menu.SHOOTERS), len(menu.BROWNIES), len(menu.DIPPED)),
                         (8, 8, 10, 6))

    def test_price_labels(self):
        self.assertEqual(menu.price_label(menu.PRODUCTS["cupcakes"]), "$35 / dozen")
        self.assertEqual(menu.price_label(menu.PRODUCTS["custom_cake"]), "$50+")
        self.assertEqual(menu.price_label(menu.PRODUCTS["dipped"]), "$30+ / dozen")


class PageTests(Base):
    def test_public_pages_render(self):
        for url in ("/", "/menu", "/gallery", "/order"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_menu_shows_all_products_and_prices(self):
        html = self.client.get("/menu").get_data(as_text=True)
        for text in ("Cupcakes", "$35 / dozen", "Cake Pops / Cakesicles", "Mini Cheesecakes", "Dessert Shooters",
                     "Dubai Chocolate", "Tiramisu", "Dirty Brownie", "Madeleines", "$130+", "$275+", "$400+", "Falooda"):
            self.assertIn(text, html)

    def test_contact_details_present(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("sweetsbyanam@gmail.com", html)
        self.assertIn("instagram.com/Sweetsbyanam", html)
        self.assertIn("Algonquin, IL 60102", html)

    def test_home_page_changes(self):
        html = self.client.get("/").get_data(as_text=True)
        for text in ("Selection", "Submit request", "Confirmation", "We will contact you to confirm details and final pricing.",
                     "Payment is due 5 days before pickup/delivery date.", "Algonquin, Illinois", "Please order at least 7 days ahead.",
                     "Place an order", "See the menu", "Treats for every table", "tell us what you want to create!"):
            self.assertIn(text, html)
        for gone in ("We confirm", "Pay 5 days before", "baked to order for your celebration", "still-life"):
            self.assertNotIn(gone, html)
        self.assertEqual(html.count("<img"), 1)  # just the logo: the second illustration is gone
        self.assertNotIn("<h1>Homemade treats", html)

    def test_menu_page_has_no_counts_in_headings(self):
        html = self.client.get("/menu").get_data(as_text=True)
        self.assertIn("<summary>Signature combinations</summary>", html)
        self.assertIn("<summary>Or build your own</summary>", html)
        self.assertNotRegex(html, r"Signature combinations \(\d+\)")
        self.assertNotRegex(html, r"\d+ cakes \+ \d+ frostings")

    def test_order_page_wording_and_field_order(self):
        html = self.client.get("/order").get_data(as_text=True)
        self.assertIn("we will email you to confirm", html)
        self.assertNotIn("Anam will", html)
        self.assertIn("Inspiration photos", html)
        phone, email = html.index('for="phone"'), html.index('for="email"')
        self.assertLess(phone, email)  # phone comes first
        self.assertRegex(html, r'for="email">Email <span class="opt">\(optional\)')
        self.assertIn('id="phone" name="phone" type="tel" autocomplete="tel" maxlength="25" required', html)
        self.assertNotRegex(html, r'id="email"[^>]*required')

    def test_unknown_page_is_branded_404(self):
        r = self.client.get("/nothing-here")
        self.assertEqual(r.status_code, 404)
        self.assertIn("SweetsbyAnam", r.get_data(as_text=True))

    def test_security_headers(self):
        r = self.client.get("/")
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_no_inline_scripts_or_styles_blocked_by_csp(self):
        html = self.client.get("/order").get_data(as_text=True)
        self.assertNotRegex(html, r"<script(?![^>]*(src=|type=\"application/json\"))")
        self.assertNotIn(' style="', html)


class OrderValidationTests(unittest.TestCase):
    def check(self, **changes):
        return orders.clean_order(good_order(**changes))

    def invalid(self, **changes):
        with self.assertRaises(orders.OrderInvalid) as ctx:
            self.check(**changes)
        return ctx.exception.fields

    def test_good_order_and_estimate(self):
        o = self.check()
        self.assertEqual(o["estimate_cents"], 7000)
        self.assertFalse(o["has_custom_pricing"])
        self.assertEqual(o["items"][0]["details"], {"Signature combination": "Dubai Chocolate"})

    def test_estimate_sums_and_flags_plus_pricing(self):
        o = self.check(items=[
            {"product": "cupcakes", "qty": 1, "mode": "classic", "cake": "Red Velvet", "frosting": "Cream Cheese"},
            {"product": "dipped", "qty": 2, "flavor": "Strawberries"},
            {"product": "pack_standard", "qty": 1, "base": "Cupcakes"}])
        self.assertEqual(o["estimate_cents"], 3500 + 6000 + 13000)
        self.assertTrue(o["has_custom_pricing"])

    def test_client_cannot_set_the_price(self):
        item = {"product": "cupcakes", "qty": 1, "mode": "combo", "combo": "Samoa", "price": 1, "line_cents": 1}
        self.assertEqual(self.check(items=[item])["estimate_cents"], 3500)

    def test_one_week_notice_boundaries(self):
        self.check(event_date=future(7))  # exactly 7 days: fine
        self.assertIn("event_date", self.invalid(event_date=future(6)))
        self.assertIn("event_date", self.invalid(event_date=future(0)))
        self.assertIn("event_date", self.invalid(event_date=future(-3)))

    def test_bad_and_far_dates(self):
        for bad in ("", None, "31/12/2030", "2026-02-30", 5, "tomorrow"):
            self.assertIn("event_date", self.invalid(event_date=bad), repr(bad))
        self.assertIn("event_date", self.invalid(event_date=future(menu.MAX_DAYS_AHEAD + 5)))

    def test_closed_dates(self):
        day = future(20)
        with mock.patch.object(menu, "CLOSED_DATES", {day}):
            self.assertIn("event_date", self.invalid(event_date=day))

    def test_contact_validation(self):
        f = self.invalid(name="", email="nope", phone="abc")
        self.assertEqual(set(f), {"name", "email", "phone"})
        self.assertIn("email", self.invalid(email="a@b"))
        self.assertIn("name", self.invalid(name="x" * 81))
        self.check(email="")  # email is optional now
        self.assertIn("phone", self.invalid(phone=""))  # phone is required
        self.assertIn("phone", self.invalid(phone=None))

    def test_delivery_needs_address_pickup_drops_it(self):
        self.assertIn("address", self.invalid(fulfilment="delivery", address=""))
        self.assertEqual(self.check(fulfilment="delivery", address="1 Main St")["address"], "1 Main St")
        self.assertEqual(self.check(fulfilment="pickup", address="ignored")["address"], "")
        self.assertIn("fulfilment", self.invalid(fulfilment="drone"))

    def test_items_required_and_capped(self):
        self.assertIn("items", self.invalid(items=[]))
        self.assertIn("items", self.invalid(items="cupcakes"))
        one = good_order()["items"][0]
        self.assertIn("items", self.invalid(items=[one] * (orders.MAX_ITEMS + 1)))

    def test_item_errors_are_reported_per_field(self):
        f = self.invalid(items=[{"product": "cupcakes", "qty": 0, "mode": "classic", "cake": "Moon", "frosting": ""}])
        self.assertEqual(set(f), {"items.0.qty", "items.0.cake", "items.0.frosting"})

    def test_unknown_product_and_bad_quantities(self):
        self.assertIn("items.0.product", self.invalid(items=[{"product": "pizza", "qty": 1}]))
        for qty in (0, 21, -1, "2", 1.5, True, None):
            f = self.invalid(items=[{"product": "brownies", "qty": qty, "flavor": "Original"}])
            self.assertIn("items.0.qty", f, repr(qty))
        self.assertIn("items.0.qty", self.invalid(items=[{"product": "custom_cake", "qty": 6, "mode": "combo",
                                                         "combo": "Samoa", "size": "8 inch"}]))

    def test_flavor_must_come_from_that_products_menu(self):
        self.assertIn("items.0.flavor", self.invalid(items=[{"product": "brownies", "qty": 1, "flavor": "Strawberries"}]))
        self.assertIn("items.0.combo", self.invalid(items=[{"product": "cupcakes", "qty": 1, "mode": "combo", "combo": "Hawaiian"}]))
        self.assertIn("items.0.mode", self.invalid(items=[{"product": "cupcakes", "qty": 1, "mode": "surprise"}]))

    def test_custom_cake_needs_size(self):
        base = {"product": "custom_cake", "qty": 1, "mode": "classic", "cake": "Vanilla", "frosting": "Vanilla"}
        self.assertIn("items.0.size", self.invalid(items=[base]))
        ok = self.check(items=[{**base, "size": "8-inch, serves 20", "message": "Happy Birthday Mom"}])
        self.assertEqual(ok["items"][0]["details"]["Size / number of servings"], "8-inch, serves 20")

    def test_cake_pops_variant(self):
        item = {"product": "cake_pops", "qty": 1, "variant": "Cakesicles", "cake": "Oreo"}
        self.assertEqual(self.check(items=[item])["items"][0]["details"]["Cake pops or cakesicles"], "Cakesicles")
        self.assertIn("items.0.variant", self.invalid(items=[{**item, "variant": "Lollipops"}]))

    def test_wrong_json_shapes_never_crash(self):
        for junk in (None, [], "x", 5, {"items": [None, 5, "x", []]}, {"items": [{"product": ["a"]}]},
                     {"name": ["list"], "items": [{}]}, {"name": {"a": 1}}):
            with self.assertRaises(orders.OrderInvalid):
                orders.clean_order(junk)

    def test_text_is_trimmed_and_long_notes_rejected(self):
        self.assertEqual(self.check(name="  Sam    Lee  ")["name"], "Sam Lee")
        self.assertIn("notes", self.invalid(notes="x" * 2001))
        self.assertIn("allergies", self.invalid(allergies="x" * 501))

    def test_payment_due_date(self):
        self.assertEqual(orders.payment_due(date(2026, 12, 20)), date(2026, 12, 15))


class OrderApiTests(Base):
    def test_order_is_saved_with_items(self):
        r = self.post(good_order(items=[
            {"product": "cupcakes", "qty": 2, "mode": "combo", "combo": "Samoa", "notes": "gold sprinkles"},
            {"product": "brownies", "qty": 1, "flavor": "Brookie (chocolate chip cookie + brownie)"}]))
        self.assertEqual(r.status_code, 201)
        ref = r.get_json()["ref"]
        self.assertRegex(ref, r"^SBA-[A-Z2-9]{6}$")
        order = self.db_rows("SELECT * FROM orders")[0]
        self.assertEqual((order["ref"], order["status"], order["estimate_cents"]), (ref, "new", 10000))
        self.assertEqual(len(self.db_rows("SELECT * FROM order_items")), 2)
        self.assertIn("gold sprinkles", self.db_rows("SELECT details FROM order_items")[0]["details"])

    def test_validation_failure_stores_nothing(self):
        r = self.post(good_order(email="bad", event_date=future(2)))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.get_json()["error"]["fields"]), {"email", "event_date"})
        self.assertEqual(self.db_rows("SELECT * FROM orders"), [])

    def test_non_json_rejected(self):
        self.assertEqual(self.client.post("/api/orders", data="hello").status_code, 400)
        self.assertEqual(self.client.post("/api/orders", json=[1]).status_code, 400)

    def test_honeypot_pretends_success_but_stores_nothing(self):
        r = self.post(good_order(website="http://spam.example"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.db_rows("SELECT * FROM orders"), [])

    def test_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.post(good_order()).status_code, 201)
        r = self.post(good_order())
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        self.assertEqual(len(self.db_rows("SELECT * FROM orders")), 5)

    def test_invalid_orders_do_not_use_up_the_limit(self):
        for _ in range(8):
            self.post(good_order(email="bad"))
        self.assertEqual(self.post(good_order()).status_code, 201)

    def test_oversized_body_rejected(self):
        self.assertEqual(self.post(good_order(notes="x" * 70000)).status_code, 413)

    def test_sql_injection_text_is_stored_literally(self):
        evil = "Robert'); DROP TABLE orders;--"
        self.assertEqual(self.post(good_order(name=evil)).status_code, 201)
        self.assertEqual(self.db_rows("SELECT name FROM orders")[0]["name"], evil)

    def test_thanks_page_shows_order_but_not_private_details(self):
        ref = self.post(good_order(phone="847-555-9999", fulfilment="delivery", address="12 Secret Lane")).get_json()["ref"]
        html = self.client.get(f"/order/thanks/{ref}").get_data(as_text=True)
        self.assertIn(ref, html)
        self.assertIn("Dubai Chocolate", html)
        self.assertIn("Thank you, Sam!", html)
        self.assertNotIn("12 Secret Lane", html)
        self.assertNotIn("847-555-9999", html)
        self.assertEqual(self.client.get("/order/thanks/SBA-NOPE00").status_code, 404)

    def test_thanks_page_escapes_html(self):
        ref = self.post(good_order(name="<b>Hax</b>", email="a@b.co")).get_json()["ref"]
        html = self.client.get(f"/order/thanks/{ref}").get_data(as_text=True)
        self.assertNotIn("<b>Hax</b>", html)


class AdminTests(Base):
    def test_admin_requires_login(self):
        self.assertEqual(self.client.get("/admin").status_code, 302)
        self.assertEqual(self.client.get("/admin/orders/1").status_code, 302)

    def test_admin_disabled_without_password(self):
        app = create_app({"DATABASE": os.path.join(self.tmp.name, "x.sqlite"), "ADMIN_PASSWORD": ""})
        c = app.test_client()
        for url in ("/admin", "/admin/login", "/admin/orders/1"):
            self.assertEqual(c.get(url).status_code, 404, url)
        self.assertEqual(c.post("/admin/login", data={"password": ""}).status_code, 404)

    def test_login_wrong_and_right(self):
        page = self.client.get("/admin/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        bad = self.client.post("/admin/login", data={"password": "nope", "csrf_token": token})
        self.assertEqual(bad.status_code, 401)
        good, _ = self.login()
        self.assertEqual(good.status_code, 302)
        self.assertEqual(self.client.get("/admin").status_code, 200)

    def test_login_needs_csrf_token(self):
        self.assertEqual(self.client.post("/admin/login", data={"password": PASSWORD}).status_code, 400)

    def test_login_lockout(self):
        page = self.client.get("/admin/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        for _ in range(5):
            self.client.post("/admin/login", data={"password": "nope", "csrf_token": token})
        r = self.client.post("/admin/login", data={"password": PASSWORD, "csrf_token": token})
        self.assertEqual(r.status_code, 401)
        self.assertIn("Too many attempts", r.get_data(as_text=True))

    def test_dashboard_lists_orders_and_details_show_everything(self):
        self.post(good_order(allergies="peanuts", fulfilment="delivery", address="12 Elm St"))
        self.login()
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Sam Customer", html)
        detail = self.client.get("/admin/orders/1").get_data(as_text=True)
        for text in ("sam@example.com", "12 Elm St", "peanuts", "Dubai Chocolate", "Payment due"):
            self.assertIn(text, detail)
        self.assertEqual(self.client.get("/admin/orders/999").status_code, 404)

    def test_status_update_needs_csrf_and_valid_status(self):
        self.post(good_order())
        _, token = self.login()
        url = "/admin/orders/1"
        self.assertEqual(self.client.post(url, data={"status": "paid"}).status_code, 400)
        self.assertEqual(self.client.post(url, data={"status": "bogus", "csrf_token": token}).status_code, 400)
        r = self.client.post(url, data={"status": "confirmed", "owner_notes": "called her", "csrf_token": token})
        self.assertEqual(r.status_code, 302)
        row = self.db_rows("SELECT status, owner_notes FROM orders")[0]
        self.assertEqual((row["status"], row["owner_notes"]), ("confirmed", "called her"))

    def test_status_filters(self):
        self.post(good_order())
        _, token = self.login()
        self.client.post("/admin/orders/1", data={"status": "completed", "csrf_token": token})
        self.assertNotIn("Sam Customer", self.client.get("/admin?status=open").get_data(as_text=True))
        self.assertIn("Sam Customer", self.client.get("/admin?status=completed").get_data(as_text=True))
        self.assertIn("Sam Customer", self.client.get("/admin?status=all").get_data(as_text=True))
        self.assertEqual(self.client.get("/admin?status=weird").status_code, 404)

    def test_admin_escapes_customer_input(self):
        self.post(good_order(name="<script>alert(1)</script>", notes="<img src=x onerror=alert(2)>"))
        self.login()
        for url in ("/admin", "/admin/orders/1"):
            html = self.client.get(url).get_data(as_text=True)
            self.assertNotIn("<script>alert(1)", html)
            self.assertNotIn("<img src=x", html)

    def test_admin_pages_are_not_cached_or_indexed(self):
        self.login()
        r = self.client.get("/admin")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertIn("noindex", r.headers["X-Robots-Tag"])

    def test_logout(self):
        _, token = self.login()
        self.client.post("/admin/logout", data={"csrf_token": token})
        self.assertEqual(self.client.get("/admin").status_code, 302)


def tiny_png() -> bytes:
    import struct, zlib

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = zlib.compress(b"\x00\xff\xaa\xbb")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


class PhotoUploadTests(Base):
    def submit(self, files, **changes):
        import io, json

        data = {"order": json.dumps(good_order(**changes))}
        data["images"] = [(io.BytesIO(body), name) for name, body in files]
        return self.client.post("/api/orders", data=data, content_type="multipart/form-data")

    def upload_dir(self):
        return self.app.config["UPLOAD_DIR"]

    def test_photos_are_saved_privately_with_the_order(self):
        r = self.submit([("cake idea.png", tiny_png()), ("two.jpg", b"\xff\xd8\xff\xe0" + b"0" * 50)])
        self.assertEqual(r.status_code, 201)
        rows = self.db_rows("SELECT * FROM order_images ORDER BY id")
        self.assertEqual([r["original_name"] for r in rows], ["cake idea.png", "two.jpg"])
        self.assertEqual([r["content_type"] for r in rows], ["image/png", "image/jpeg"])
        for row in rows:
            self.assertRegex(row["filename"], r"^[0-9a-f]{32}\.(png|jpg)$")  # random name, not the customer's
            self.assertTrue(os.path.exists(os.path.join(self.upload_dir(), row["filename"])))
        self.assertNotIn(os.path.abspath(self.app.static_folder), os.path.abspath(self.upload_dir()))

    def test_photos_are_optional_and_json_still_works(self):
        self.assertEqual(self.submit([]).status_code, 201)
        self.assertEqual(self.post(good_order()).status_code, 201)

    def test_fake_images_are_rejected_by_content_not_name(self):
        r = self.submit([("virus.jpg", b"<html><script>alert(1)</script></html>")])
        self.assertEqual(r.status_code, 422)
        self.assertIn("images", r.get_json()["error"]["fields"])
        self.assertEqual(self.db_rows("SELECT * FROM orders"), [])
        self.assertFalse(os.path.exists(self.upload_dir()) and os.listdir(self.upload_dir()))

    def test_svg_and_gif_and_pdf_rejected(self):
        for name, body in (("a.svg", b"<svg onload=alert(1)></svg>"), ("a.gif", b"GIF89a\x01\x00"), ("a.pdf", b"%PDF-1.4")):
            self.assertEqual(self.submit([(name, body)]).status_code, 422, name)

    def test_too_many_photos(self):
        r = self.submit([(f"{i}.png", tiny_png()) for i in range(6)])
        self.assertEqual(r.status_code, 422)
        self.assertIn("at most 5", r.get_json()["error"]["fields"]["images"])
        self.assertEqual(self.submit([(f"{i}.png", tiny_png()) for i in range(5)]).status_code, 201)

    def test_photo_over_5mb_rejected(self):
        big = tiny_png() + b"0" * (5 * 1024 * 1024)
        r = self.submit([("big.png", big)])
        self.assertEqual(r.status_code, 422)
        self.assertIn("5 MB", r.get_json()["error"]["fields"]["images"])

    def test_whole_request_size_cap(self):
        r = self.submit([(f"{i}.png", tiny_png() + b"0" * (4 * 1024 * 1024)) for i in range(5)] + [("x.png", tiny_png() + b"0" * (4 * 1024 * 1024))])
        self.assertIn(r.status_code, (413, 422))

    def test_order_errors_and_photo_errors_reported_together(self):
        r = self.submit([("bad.txt", b"hello")], email="nope")
        self.assertEqual(set(r.get_json()["error"]["fields"]), {"email", "images"})

    def test_original_filename_cannot_escape_folder(self):
        self.submit([("../../etc/passwd.png", tiny_png())])
        row = self.db_rows("SELECT original_name, filename FROM order_images")[0]
        self.assertEqual(row["original_name"], "passwd.png")
        self.assertNotIn("/", row["filename"])

    def test_photos_only_visible_to_logged_in_baker(self):
        self.submit([("idea.png", tiny_png())])
        self.assertEqual(self.client.get("/admin/photos/1").status_code, 302)  # sent to the login page
        self.login()
        r = self.client.get("/admin/photos/1")
        self.assertEqual((r.status_code, r.mimetype), (200, "image/png"))
        self.assertEqual(r.data, tiny_png())
        self.assertEqual(self.client.get("/admin/photos/99").status_code, 404)
        detail = self.client.get("/admin/orders/1").get_data(as_text=True)
        self.assertIn("/admin/photos/1", detail)
        self.assertIn("Inspiration photos", detail)

    def test_photos_not_reachable_from_public_urls(self):
        self.submit([("idea.png", tiny_png())])
        name = self.db_rows("SELECT filename FROM order_images")[0]["filename"]
        for url in (f"/static/{name}", f"/static/uploads/{name}", f"/uploads/{name}"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_thanks_page_mentions_photo_count(self):
        ref = self.submit([("a.png", tiny_png()), ("b.png", tiny_png())]).get_json()["ref"]
        self.assertIn("2 inspiration photos", self.client.get(f"/order/thanks/{ref}").get_data(as_text=True))

    def test_failed_database_write_removes_saved_photos(self):
        with mock.patch("sweetsbyanam.db.save_order", side_effect=RuntimeError("db down")):
            self.app.config["PROPAGATE_EXCEPTIONS"] = False
            r = self.submit([("a.png", tiny_png())])
        self.assertEqual(r.status_code, 500)
        self.assertEqual(os.listdir(self.upload_dir()), [])

    def test_email_mentions_photos(self):
        settings = notify.smtp_settings(create_app({"DATABASE": os.path.join(self.tmp.name, "n.sqlite"), "SMTP_HOST": "h",
                                                    "NOTIFY_EMAIL": "b@x"}).config)
        order = orders.clean_order(good_order())
        self.assertIn("Inspiration photos: 3", notify.order_email("SBA-1", order, "u", settings, 3).get_content())


class NoEmailOrderTests(Base):
    def test_order_without_email_is_accepted_and_shown_properly(self):
        r = self.post(good_order(email="", phone="847-555-0100"))
        self.assertEqual(r.status_code, 201)
        ref = r.get_json()["ref"]
        thanks = self.client.get(f"/order/thanks/{ref}").get_data(as_text=True)
        self.assertIn("We will call or text you at", thanks)
        self.assertIn("847-555-0100", thanks)
        self.login()
        detail = self.client.get("/admin/orders/1").get_data(as_text=True)
        self.assertIn("No email given", detail)
        self.assertIn("tel:847-555-0100", detail)

    def test_order_with_email_says_email(self):
        ref = self.post(good_order()).get_json()["ref"]
        self.assertIn("We will email you at", self.client.get(f"/order/thanks/{ref}").get_data(as_text=True))

    def test_phone_is_required_by_the_api(self):
        r = self.post(good_order(phone=""))
        self.assertEqual(r.status_code, 422)
        self.assertIn("phone", r.get_json()["error"]["fields"])

    def test_notification_email_without_customer_email_has_no_reply_to(self):
        app = create_app({"DATABASE": os.path.join(self.tmp.name, "m.sqlite"), "SMTP_HOST": "h", "NOTIFY_EMAIL": "b@x"})
        order = orders.clean_order(good_order(email=""))
        msg = notify.order_email("SBA-1", order, "u", notify.smtp_settings(app.config))
        self.assertIsNone(msg["Reply-To"])
        self.assertIn("call or text", msg.get_content())


class EmailTests(Base):
    def smtp_app(self):
        return create_app({"DATABASE": os.path.join(self.tmp.name, "m.sqlite"), "SMTP_HOST": "smtp.test",
                           "SMTP_USER": "me@test", "SMTP_PASSWORD": "pw", "NOTIFY_EMAIL": "baker@test"})

    def test_email_content(self):
        settings = notify.smtp_settings(self.smtp_app().config)
        order = orders.clean_order(good_order(allergies="tree nuts", notes="blue theme"))
        msg = notify.order_email("SBA-ABC234", order, "http://x/admin", settings)
        body = msg.get_content()
        self.assertEqual(msg["To"], "baker@test")
        self.assertEqual(msg["Reply-To"], "sam@example.com")
        self.assertIn("SBA-ABC234", msg["Subject"])
        for text in ("Dubai Chocolate", "ALLERGIES: tree nuts", "blue theme", "$70", "http://x/admin"):
            self.assertIn(text, body)

    def test_order_sends_email_when_configured(self):
        app = self.smtp_app()
        with mock.patch("sweetsbyanam.notify.smtplib.SMTP") as smtp:
            client = app.test_client()
            self.assertEqual(client.post("/api/orders", json=good_order()).status_code, 201)
            for t in __import__("threading").enumerate():
                if t is not __import__("threading").current_thread() and t.daemon:
                    t.join(timeout=3)
        server = smtp.return_value.__enter__.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("me@test", "pw")
        server.send_message.assert_called_once()

    def test_email_failure_never_breaks_the_order(self):
        app = self.smtp_app()
        with mock.patch("sweetsbyanam.notify.smtplib.SMTP", side_effect=OSError("smtp down")):
            r = app.test_client().post("/api/orders", json=good_order())
            for t in __import__("threading").enumerate():
                if t.daemon and t is not __import__("threading").current_thread():
                    t.join(timeout=3)
        self.assertEqual(r.status_code, 201)
        with app.app_context():
            self.assertEqual(len(get_db().execute("SELECT * FROM orders").fetchall()), 1)

    def test_no_email_attempted_without_smtp_config(self):
        with mock.patch("sweetsbyanam.notify.smtplib.SMTP") as smtp:
            self.post(good_order())
        smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
