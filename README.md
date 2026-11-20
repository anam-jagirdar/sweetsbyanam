# SweetsbyAnam

The website and online ordering system for [SweetsbyAnam](https://www.instagram.com/Sweetsbyanam/), a home bakery in Algonquin, IL. Customers browse the menu and send an order request through a form that is checked on the server and saved to a database. The baker gets an email for each order and manages them in a password-protected dashboard.

Built with Flask and SQLite. The design takes its colors, arch shapes and gingham ribbon from the bakery's logo.

## Features

**For customers**
- Menu with every item, price, flavor and signature combination, plus party packs
- Order form with several items per order. Each item shows only the choices that make sense for it (a cupcake order offers 17 signature combinations or a build-your-own cake + frosting; cake pops ask pops or cakesicles; and so on)
- Running price estimate, and a clear note that add-ons and customizations cost extra
- Phone number required, email optional (the thank-you page says "we will email you" or "we will call or text you" to match)
- Optional inspiration photos (up to 5 JPG, PNG or WebP files, 5 MB each) with previews and a remove button
- Rules enforced for real: at least 7 days' notice, delivery needs an address, quantities capped
- Confirmation page with the order reference and the payment due date (5 days before the event)
- Works on phones, keyboard-friendly, with labeled fields and screen-reader-friendly error messages

**For the baker**
- Email for each new order, with the customer's address as Reply-To so replying goes straight to them
- Dashboard at `/admin`: orders sorted by event date, filter by status (new, confirmed, paid, completed, cancelled), private notes, payment due dates, allergy warnings, and each customer's inspiration photos

## Run it on your computer

Needs Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ADMIN_PASSWORD="pick-something-long" python run.py
```

Open <http://127.0.0.1:5002>. The order dashboard is at <http://127.0.0.1:5002/admin>.

If `ADMIN_PASSWORD` is not set, the admin area does not exist at all (there is no default password).

## Settings

Set these as environment variables.

| Variable | What it does |
|---|---|
| `ADMIN_PASSWORD` | Password for `/admin`. Use a long one. |
| `SECRET_KEY` | Signs login cookies. Set it to a long random string, or you'll have to log in again after every restart. |
| `SWEETS_DB` | Where the SQLite file lives (default: `sweetsbyanam.sqlite` in the current folder). |
| `SWEETS_UPLOADS` | Where customers' inspiration photos are stored (default: an `uploads` folder next to the database). |
| `SWEETS_HTTPS` | Set to `1` once the site is served over HTTPS, so cookies are marked secure. |
| `TRUST_PROXY` | Set to `1` if a hosting proxy sits in front of the app, so rate limits see real visitor addresses. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Mail server for new-order emails. Optional. |
| `NOTIFY_EMAIL` | Where order emails go (default: sweetsbyanam@gmail.com). |

Order emails are optional. Without SMTP settings, orders are still saved and appear in the dashboard.

### Email through Gmail

1. Turn on 2-Step Verification for the Gmail account.
2. Create an **app password** in the Google account's security settings (don't use the normal password).
3. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=<the Gmail address>`, `SMTP_PASSWORD=<the app password>`.

## Editing the menu

Everything customers see about the menu lives in one file, `sweetsbyanam/menu.py`: prices, flavors, signature combinations, notice period, payment timing and contact details. The menu page, the order form and the server-side checks all read from it, so they can't disagree. Change a price there and it changes everywhere.

- **Close a date** (a holiday, a trip): add it to `CLOSED_DATES`, for example `{"2026-12-25"}`.
- **Gallery photos:** drop `.jpg` / `.png` / `.webp` files into `sweetsbyanam/static/gallery/`. They appear on the site automatically.
- **Menu photos:** add `cupcakes.jpg`, `brownies.jpg` and so on to `sweetsbyanam/static/menu/` (see the README.txt in that folder for the names).

## How it works

```
sweetsbyanam/
  menu.py         the menu and the ordering rules (single source of truth)
  orders.py       validates an incoming order against the menu, calculates the estimate
  db.py           SQLite schema and saving an order with its items in one transaction
  uploads.py      checks and stores inspiration photos (private folder, random names)
  notify.py       emails the baker (in a background thread, so email trouble never loses an order)
  admin.py        login and the order dashboard
  security.py     rate limiting, CSRF tokens, security headers
  templates/      Jinja pages
  static/         style.css, order.js, logo and photos
tests/            73 tests
```

Design decisions worth knowing:

- **The server never trusts the browser.** The order form's JavaScript is a convenience. Every choice is re-checked against the menu on the server, every length is capped, and the price estimate is calculated on the server. A customer can't change the price by editing the page.
- **All problems are reported at once,** keyed to the exact field, so the form can highlight them. Errors clear as the customer fixes each field.
- **Spam protection without a CAPTCHA:** a hidden honeypot field that only bots fill in, and a limit of 5 orders per hour per visitor.
- **Customer details stay private.** The confirmation page shows the order but never the phone number or address, and the dashboard needs the password. Admin pages are marked `no-store` and `noindex`.
- **Security basics:** parameterized SQL everywhere, templates escape all customer text, CSRF tokens on every admin form, constant-time password comparison, login attempt limiting, a strict Content-Security-Policy (no inline scripts), and the admin area turned off unless a password is set.
- **Inspiration photos are treated as untrusted files.** The real file type is read from the file's first bytes (not its name), so a renamed script or an SVG is refused. Only JPEG, PNG and WebP are accepted, with limits on count and size. Photos are saved under random names in a private folder outside the public website, and the only way to see one is through the password-protected dashboard.
- **Orders are saved atomically.** An order and its items are written in a single transaction, so you never get half an order.

## Tests

```bash
python -m unittest discover -s tests -v
```

73 tests cover the menu data (prices match the price list), every validation rule and boundary (exactly 7 days is fine, 6 is not), tampering attempts, saving orders, the rate limit and honeypot, privacy of the confirmation page, admin login/CSRF/lockout/escaping of hostile input, photo uploads (fake images, wrong types, too many, too big, filename tricks, who can see them), and the email (including that a mail failure never breaks an order).

I also ran the site in a real browser (Chromium): submitted an empty form and the 7-day rule error, filled in a three-item order, confirmed it landed in the database exactly as typed, then logged into the dashboard, opened the order and changed its status. I checked the phone layout for sideways scrolling.

## Putting it online

GitHub Pages can't run this, because the site has a server and a database. It needs a host that runs Python **and keeps files between restarts**, since orders are stored in a file.

- **Avoid free hosts with a temporary filesystem.** For example, Render's free web services lose local files (including a SQLite database) whenever the service restarts, and they block the usual email ports. Orders would disappear.
- **PythonAnywhere's free account** is a workable option. It runs Flask apps, keeps files, and allows sending mail through Gmail on `smtp.gmail.com` port 587. Its free web app has to be renewed every month, and the address ends in `pythonanywhere.com`. Check their current terms before relying on it, and consider a paid plan for a real business.

Rough steps on PythonAnywhere:

1. Create an account and open a **Bash console**. Upload or `git clone` this repo.
2. In the console: `python3 -m venv ~/.venv && source ~/.venv/bin/activate && pip install -r requirements.txt` (in the repo folder).
3. In the **Web** tab, add a new **Flask** web app (manual configuration is fine) and point the virtualenv at `~/.venv`.
4. Edit the WSGI file the Web tab gives you so it sets the settings and then loads this app:

```python
import os, sys
sys.path.insert(0, "/home/YOURNAME/sweetsbyanam")      # the folder with wsgi.py
os.environ["ADMIN_PASSWORD"] = "a-long-password"
os.environ["SECRET_KEY"] = "a-long-random-string"
os.environ["SWEETS_DB"] = "/home/YOURNAME/sweetsbyanam-data/orders.sqlite"  # keep it outside the code folder
os.environ["SWEETS_HTTPS"] = "1"
os.environ["TRUST_PROXY"] = "1"
os.environ["SMTP_HOST"] = "smtp.gmail.com"
os.environ["SMTP_USER"] = "sweetsbyanam@gmail.com"
os.environ["SMTP_PASSWORD"] = "the-gmail-app-password"
from wsgi import application
```

5. Create the data folder (`mkdir ~/sweetsbyanam-data`), reload the web app, place a test order, and check it appears at `/admin` and in your email.

Treat the hosting step as a checklist to verify as you go. Dashboards and wording on hosting sites change.

## Before you take real orders

- Place a test order and confirm the email arrives (and isn't in spam).
- Back up `orders.sqlite` and the `uploads` folder next to it now and then. Downloading a copy of both is enough.
- Keep `ADMIN_PASSWORD`, `SECRET_KEY` and the Gmail app password out of the repo. Set them only on the host. (`.gitignore` already excludes `.env` and the database.)
- Customers' names, emails, phone numbers and addresses are personal information. Don't share dashboard screenshots publicly.

## Limitations

- No online payment: customers pay Anam directly, 5 days before the event, after she confirms.
- The customer gets an on-screen confirmation but no automatic confirmation email. Anam replies by email to confirm.
- Rate limits and login lockouts are kept in memory, so they are per server process and reset when the app restarts.
- The final price is set by Anam. The site shows base prices and an estimate only.
- Customers can't edit or cancel an order themselves; they contact Anam.
- Times in the dashboard are stored in UTC. Event dates and the 7-day rule use Chicago time.
