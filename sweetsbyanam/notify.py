"""Email the baker when an order arrives. Optional: if SMTP isn't configured nothing is sent, and a
failure here can never stop a customer's order from being saved (it runs in a background thread)."""
import logging
import smtplib
import threading
from email.message import EmailMessage

from . import menu

log = logging.getLogger("sweetsbyanam")


def smtp_settings(config) -> dict | None:
    if not (config.get("SMTP_HOST") and config.get("NOTIFY_EMAIL")):
        return None
    return {k: config.get(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "NOTIFY_EMAIL")}


def order_email(ref: str, order: dict, admin_url: str, settings: dict, photo_count: int = 0) -> EmailMessage:
    lines = [f"New order {ref}", "", f"Name:       {order['name']}", f"Phone:      {order['phone']}",
             f"Email:      {order['email'] or '(not given, so call or text)'}", f"Event date: {order['event_date']}"]
    if order["occasion"]:
        lines.append(f"Occasion:   {order['occasion']}")
    lines.append(f"{order['fulfilment'].title()}" + (f": {order['address']}" if order["address"] else ""))
    lines += ["", "Items:"]
    for item in order["items"]:
        lines.append(f"  - {item['qty']} x {item['name']}")
        lines += [f"      {k}: {v}" for k, v in item["details"].items()]
    lines += ["", f"Estimated base total: {menu.money(order['estimate_cents'])}"
              + (" (+ custom work)" if order["has_custom_pricing"] else "")]
    if order["allergies"]:
        lines += ["", f"ALLERGIES: {order['allergies']}"]
    if order["notes"]:
        lines += ["", f"Notes: {order['notes']}"]
    if photo_count:
        lines += ["", f"Inspiration photos: {photo_count} attached (open the order in the dashboard to see them)"]
    lines += ["", f"Manage it: {admin_url}"]

    message = EmailMessage()
    message["Subject"] = f"New order {ref} for {order['event_date']} ({order['name']})"
    message["From"] = settings["SMTP_FROM"] or settings["SMTP_USER"] or settings["NOTIFY_EMAIL"]
    message["To"] = settings["NOTIFY_EMAIL"]
    if order["email"]:
        message["Reply-To"] = order["email"]  # hitting Reply goes straight to the customer
    message.set_content("\n".join(lines))
    return message


def _send(message: EmailMessage, settings: dict) -> None:
    try:
        with smtplib.SMTP(settings["SMTP_HOST"], int(settings["SMTP_PORT"] or 587), timeout=15) as server:
            server.starttls()
            if settings["SMTP_USER"]:
                server.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"] or "")
            server.send_message(message)
    except Exception:
        log.exception("could not send the new-order email")


def notify_new_order(config, ref: str, order: dict, admin_url: str, photo_count: int = 0, wait: bool = False):
    settings = smtp_settings(config)
    if not settings:
        return None
    thread = threading.Thread(target=_send, args=(order_email(ref, order, admin_url, settings, photo_count), settings), daemon=True)
    thread.start()
    if wait:
        thread.join(timeout=20)
    return thread
