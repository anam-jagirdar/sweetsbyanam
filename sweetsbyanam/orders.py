"""Checking an incoming order. Nothing from the browser is trusted: every choice is compared with
the menu, every length is capped, and the price estimate is calculated here, never taken from the page."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from . import menu

try:
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("America/Chicago")
except Exception:  # tz database missing: fall back to UTC
    _TZ = timezone.utc

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s.]{2,}$")
PHONE = re.compile(r"^[0-9+()\-.\s]{7,25}$")
MAX_ITEMS = 12


class OrderInvalid(Exception):
    def __init__(self, fields: dict):
        super().__init__("invalid order")
        self.fields = fields


def today() -> date:
    return datetime.now(_TZ).date()


def earliest_event_date(now: date | None = None) -> date:
    return (now or today()) + timedelta(days=menu.MIN_DAYS_NOTICE)


def payment_due(event: date) -> date:
    return event - timedelta(days=menu.PAYMENT_DAYS_BEFORE)


def _text(raw, name, errors, required=False, maximum=200):
    if raw is None or raw == "":
        if required:
            errors[name] = "This is required."
        return ""
    if not isinstance(raw, str):
        errors[name] = "Must be text."
        return ""
    value = " ".join(raw.split()) if maximum <= 200 else raw.strip()
    if required and not value:
        errors[name] = "This is required."
    elif len(value) > maximum:
        errors[name] = f"Please keep this under {maximum} characters."
    return value


def _choice(raw, options, name, errors, required=True):
    if raw in (None, ""):
        if required:
            errors[name] = "Please choose an option."
        return ""
    if raw not in options:
        errors[name] = "Please choose one of the listed options."
        return ""
    return raw


def clean_item(raw, index: int, errors: dict) -> dict | None:
    prefix = f"items.{index}"
    if not isinstance(raw, dict):
        errors[prefix] = "Invalid item."
        return None
    key = raw.get("product")
    product = menu.PRODUCTS.get(key) if isinstance(key, str) else None
    if product is None:
        errors[f"{prefix}.product"] = "Please choose an item."
        return None

    local: dict = {}
    low, high = menu.QUANTITY_LIMITS[product["unit"]]
    qty = raw.get("qty")
    if isinstance(qty, bool) or not isinstance(qty, int) or not low <= qty <= high:
        local["qty"] = f"Choose between {low} and {high}. For bigger orders, email us."
        qty = 0

    details: dict[str, str] = {}
    if product.get("style") == "combo_or_classic":
        mode = _choice(raw.get("mode"), ("combo", "classic"), "mode", local)
        if mode == "combo":
            details["Signature combination"] = _choice(raw.get("combo"), list(menu.COMBOS), "combo", local)
        elif mode == "classic":
            details["Cake flavor"] = _choice(raw.get("cake"), menu.CAKE_FLAVORS, "cake", local)
            details["Frosting"] = _choice(raw.get("frosting"), menu.FROSTING_FLAVORS, "frosting", local)
    for field in product["fields"]:
        if field["options"] is not None:
            value = _choice(raw.get(field["key"]), field["options"], field["key"], local, field["required"])
        else:
            maximum = 1000 if field["kind"] == "textarea" else 120
            value = _text(raw.get(field["key"]), field["key"], local, field["required"], maximum)
        if value:
            details[field["label"]] = value
    notes = _text(raw.get("notes"), "notes", local, maximum=500)
    if notes:
        details["Notes / customizations"] = notes

    for name, message in local.items():
        errors[f"{prefix}.{name}"] = message
    if local:
        return None
    return {"product": key, "name": product["name"], "qty": qty, "unit": product["unit"], "details": details,
            "line_cents": product["price"] * qty, "plus": product["plus"]}


def clean_order(data, now: date | None = None) -> dict:
    """Return a clean order dict, or raise OrderInvalid listing every problem at once."""
    if not isinstance(data, dict):
        raise OrderInvalid({"form": "Invalid request."})
    errors: dict[str, str] = {}
    name = _text(data.get("name"), "name", errors, required=True, maximum=80)
    phone = _text(data.get("phone"), "phone", errors, required=True, maximum=25)
    if phone and "phone" not in errors and not PHONE.match(phone):
        errors["phone"] = "Please enter a valid phone number."
    email = _text(data.get("email"), "email", errors, maximum=254)  # optional
    if email and "email" not in errors and not EMAIL.match(email):
        errors["email"] = "Please enter a valid email address."

    fulfilment = _choice(data.get("fulfilment"), ("pickup", "delivery"), "fulfilment", errors)
    address = _text(data.get("address"), "address", errors, required=(fulfilment == "delivery"), maximum=200)
    if fulfilment != "delivery":
        address = ""

    event = None
    raw_date = data.get("event_date")
    try:
        event = date.fromisoformat(raw_date) if isinstance(raw_date, str) else None
    except ValueError:
        event = None
    earliest = earliest_event_date(now)
    if event is None:
        errors["event_date"] = "Please choose a date."
    elif event < earliest:
        errors["event_date"] = (f"We need at least {menu.MIN_DAYS_NOTICE} days' notice. "
                                f"The earliest date is {earliest.strftime('%B')} {earliest.day}, {earliest.year}.")
    elif event > (now or today()) + timedelta(days=menu.MAX_DAYS_AHEAD):
        errors["event_date"] = "That date is too far ahead. Please email us."
    elif event.isoformat() in menu.CLOSED_DATES:
        errors["event_date"] = "We're not taking orders for that date. Please pick another."

    occasion = _text(data.get("occasion"), "occasion", errors, maximum=100)
    notes = _text(data.get("notes"), "notes", errors, maximum=2000)
    allergies = _text(data.get("allergies"), "allergies", errors, maximum=500)

    raw_items = data.get("items")
    items = []
    if not isinstance(raw_items, list) or not raw_items:
        errors["items"] = "Please add at least one item."
    elif len(raw_items) > MAX_ITEMS:
        errors["items"] = f"Please keep an order to {MAX_ITEMS} items or fewer. Email us for larger orders."
    else:
        for i, raw in enumerate(raw_items):
            item = clean_item(raw, i, errors)
            if item:
                items.append(item)

    if errors:
        raise OrderInvalid(errors)
    return {
        "name": name, "email": email, "phone": phone, "fulfilment": fulfilment, "address": address,
        "event_date": event.isoformat(), "occasion": occasion, "notes": notes, "allergies": allergies,
        "items": items, "estimate_cents": sum(i["line_cents"] for i in items),
        "has_custom_pricing": any(i["plus"] for i in items),
    }
