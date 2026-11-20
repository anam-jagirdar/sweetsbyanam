"""The menu: the single source of truth for the website AND for validating orders.

To change a price, add a flavor or add a product, edit this file only. The menu page, the order
form and the server-side checks all read from here, so they can never disagree.

Prices are in whole cents. `plus=True` means "starting at" (custom work costs extra).
"""
from __future__ import annotations

BUSINESS = {
    "name": "SweetsbyAnam",
    "tagline": "Homemade treats, with love",
    "city": "Algonquin, IL 60102",
    "email": "sweetsbyanam@gmail.com",
    "instagram": "Sweetsbyanam",
    "instagram_url": "https://www.instagram.com/Sweetsbyanam/",
}

# Ordering rules (shown on the site and enforced by the server)
MIN_DAYS_NOTICE = 7
PAYMENT_DAYS_BEFORE = 5
MAX_DAYS_AHEAD = 365
CLOSED_DATES: set[str] = set()  # e.g. {"2026-12-25"} for days you can't take orders for

CAKE_FLAVORS = ["Chocolate", "Vanilla", "Strawberry", "Lemon", "Pumpkin Spice", "Red Velvet", "Tres Leches",
                "Falooda", "Cookie Dough", "Birthday Cake", "Oreo"]

FROSTING_FLAVORS = ["Vanilla", "Chocolate", "Dark Chocolate", "Cream Cheese", "Strawberry", "Lemon", "Peach",
                    "Orange", "Salted Caramel", "Coffee", "Peanut Butter", "Cinnamon", "Maple", "Peppermint",
                    "Coconut"]

COMBOS = {
    "Chocolate Biscoff": "chocolate cake + biscoff cookie butter cream filling + biscoff buttercream",
    "German Chocolate": "chocolate cake + coconut pecan filling + chocolate buttercream",
    "S'mores": "chocolate cake + marshmallow filling + graham cracker buttercream",
    "White Chocolate Raspberry": "white chocolate raspberry cake + raspberry jam + white chocolate buttercream",
    "Ferrero Rocher": "chocolate cake + hazelnut or nutella cream + chocolate hazelnut buttercream",
    "Peanut Butter & Jelly": "peanut butter cake + strawberry jam + peanut buttercream",
    "Brownie Batter": "chocolate cake + brownie batter filling + fudge buttercream",
    "Strawberry Shortcake": "vanilla pound cake + strawberry filling + whipped cream",
    "Chocolate Peanut Butter Cup": "chocolate cake + peanut butter cream filling + peanut buttercream",
    "Dubai Chocolate": "chocolate cake + pistachio kataifi filling + chocolate buttercream",
    "Blueberry Waffle": "blueberry cake + blueberry syrup filling + maple cream cheese frosting",
    "Key Lime": "key lime cake + cream cheese filling + key lime buttercream",
    "Thin Mint": "chocolate cake + mint chocolate ganache + mint cookies and cream buttercream",
    "Samoa": "chocolate cake + caramel coconut filling + caramel buttercream",
    "Piña Colada": "pineapple coconut cake + pineapple filling + coconut buttercream",
    "Lemon Lovers": "lemon cake + lemon curd filling + lemon buttercream",
    "Cookies & Cream": "chocolate cake + cream filling + cookies and cream buttercream",
}

CHEESECAKE_FLAVORS = ["Original", "Biscoff", "Oreo", "Cookie Dough", "Strawberry", "Pumpkin Swirl", "Chocolate",
                      "Chocolate Peanut Butter"]

SHOOTERS = {
    "Mango": "vanilla cake, mango chunks, and mango mousse",
    "Biscoff": "vanilla cake, Biscoff mousse, Biscoff cookies, Biscoff",
    "Ferrero Rocher": "chocolate cake, Nutella filling, wafer chunks, Nutella",
    "Tiramisu": "lady finger cookie, espresso filling, whipped tiramisu filling, cocoa powder",
    "Oreo": "chocolate cake, Oreo mousse, Oreo chunks, Oreo cream topping",
    "Vanilla": "vanilla cake, vanilla mousse, and vanilla frosting",
    "Berry": "vanilla cake, Chantilly filling, berries, custard",
    "Chocolate": "chocolate cake, chocolate mousse, and chocolate frosting",
}

BROWNIES = ["Original", "Walnut", "Caramel / Salted Caramel", "Brookie (chocolate chip cookie + brownie)",
            "Blondie", "S'mores", "Biscoff", "Dirty Brownie (chocolate chip cookie, Oreo + brownie)",
            "Dubai Brownie", "Hot Fudge Brownie"]

DIPPED = ["Strawberries", "Pretzels", "Oreos", "Madeleines", "Rice Krispies", "Donuts"]

PACK_CONTENTS = ["Cupcakes or mini cheesecakes", "Cake pops", "Dessert shooters", "Dipped goodies"]


def _field(key, label, options=None, required=True, help=None, kind="select"):
    return {"key": key, "label": label, "options": options, "required": required, "help": help, "kind": kind}


# `style="combo_or_classic"` products let the customer choose a signature combination OR build their own
# from a cake flavor + a frosting flavor.
PRODUCTS = {
    "cupcakes": {
        "name": "Cupcakes", "group": "treats", "price": 3500, "plus": False, "unit": "dozen",
        "blurb": "Fresh-baked and frosted. Pick a signature combination or build your own.",
        "style": "combo_or_classic", "fields": [],
    },
    "cake_pops": {
        "name": "Cake Pops / Cakesicles", "group": "treats", "price": 4000, "plus": False, "unit": "dozen",
        "blurb": "Bite-size cake on a stick, dipped and decorated.",
        "fields": [_field("variant", "Cake pops or cakesicles", ["Cake pops", "Cakesicles"]),
                   _field("cake", "Cake flavor", CAKE_FLAVORS)],
    },
    "custom_cake": {
        "name": "Custom Cake", "group": "treats", "price": 5000, "plus": True, "unit": "cake",
        "blurb": "Made for your celebration. Price depends on size and servings.",
        "style": "combo_or_classic",
        "fields": [_field("size", "Size / number of servings", None, help="e.g. 8-inch round, serves 20", kind="text"),
                   _field("message", "Message or theme on the cake", None, required=False, kind="text")],
    },
    "mini_cheesecakes": {
        "name": "Mini Cheesecakes", "group": "treats", "price": 4500, "plus": False, "unit": "dozen",
        "blurb": "Creamy single-serve cheesecakes.",
        "fields": [_field("flavor", "Flavor", CHEESECAKE_FLAVORS)],
    },
    "brownies": {
        "name": "Brownies", "group": "treats", "price": 3000, "plus": False, "unit": "dozen",
        "blurb": "Fudgy, loaded and made to share.",
        "fields": [_field("flavor", "Flavor", BROWNIES)],
    },
    "dipped": {
        "name": "Dipped Goodies", "group": "treats", "price": 3000, "plus": True, "unit": "dozen",
        "blurb": "Everything is covered in chocolate. Price depends on the type and level of decoration.",
        "fields": [_field("flavor", "What would you like dipped?", DIPPED)],
    },
    "shooters": {
        "name": "Dessert Shooters", "group": "treats", "price": 4000, "plus": False, "unit": "dozen",
        "blurb": "Layered dessert cups, ready to serve.",
        "fields": [_field("flavor", "Flavor", list(SHOOTERS))],
    },
    "pack_standard": {
        "name": "Standard Party Pack", "group": "packs", "price": 13000, "plus": True, "unit": "pack",
        "blurb": "1 dozen each of everything below.", "pack_dozens": 1,
        "fields": [_field("base", "Cupcakes or mini cheesecakes?", ["Cupcakes", "Mini cheesecakes"]),
                   _field("flavors", "Flavors you'd like", None, required=False,
                          help="Tell us your favorites for each item. We'll confirm everything with you.", kind="textarea")],
    },
    "pack_deluxe": {
        "name": "Deluxe Party Pack", "group": "packs", "price": 27500, "plus": True, "unit": "pack",
        "blurb": "2 dozen each of everything below.", "pack_dozens": 2,
        "fields": [_field("base", "Cupcakes or mini cheesecakes?", ["Cupcakes", "Mini cheesecakes"]),
                   _field("flavors", "Flavors you'd like", None, required=False,
                          help="Tell us your favorites for each item. We'll confirm everything with you.", kind="textarea")],
    },
    "pack_premium": {
        "name": "Premium Party Pack", "group": "packs", "price": 40000, "plus": True, "unit": "pack",
        "blurb": "3 dozen each of everything below.", "pack_dozens": 3,
        "fields": [_field("base", "Cupcakes or mini cheesecakes?", ["Cupcakes", "Mini cheesecakes"]),
                   _field("flavors", "Flavors you'd like", None, required=False,
                          help="Tell us your favorites for each item. We'll confirm everything with you.", kind="textarea")],
    },
}

QUANTITY_LIMITS = {"dozen": (1, 20), "cake": (1, 5), "pack": (1, 5)}
UNIT_LABELS = {"dozen": ("dozen", "dozens"), "cake": ("cake", "cakes"), "pack": ("pack", "packs")}


def money(cents: int, plus: bool = False) -> str:
    text = f"${cents / 100:,.0f}" if cents % 100 == 0 else f"${cents / 100:,.2f}"
    return text + ("+" if plus else "")


def price_label(product: dict) -> str:
    unit = "" if product["unit"] == "cake" else f" / {product['unit']}"
    return money(product["price"], product["plus"]) + unit


def pack_summary(product: dict) -> str:
    n = product["pack_dozens"]
    return f"{n} dozen each: " + ", ".join(c.lower() if i else c for i, c in enumerate(PACK_CONTENTS))


def client_menu() -> dict:
    """What the order form's JavaScript needs, as plain JSON."""
    return {
        "products": {
            key: {
                "name": p["name"], "unit": p["unit"], "price": price_label(p), "style": p.get("style"),
                "group": p["group"], "price_cents": p["price"], "plus": p["plus"],
                "limits": QUANTITY_LIMITS[p["unit"]], "unit_label": UNIT_LABELS[p["unit"]],
                "fields": p["fields"],
            }
            for key, p in PRODUCTS.items()
        },
        "combos": COMBOS, "cake_flavors": CAKE_FLAVORS, "frostings": FROSTING_FLAVORS,
    }
