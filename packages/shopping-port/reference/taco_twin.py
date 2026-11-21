"""Synthetic taco-night world for push@1 tests (labels: synthetic).

Invented products, brands and prices; no real brands, no Walmart data. Tax and fee are synthetic
placeholders, not the hello-world fixture's values (IQ owns those in fixtures/taco_hw@1.json).
"""
import copy

CATALOG = {
    "T1": dict(name="Sol Mesa flour tortillas, 10 count", role="tortilla", brand="Sol Mesa", product="sm-flour", price=2.98, serves=4, usual=True),
    "T2": dict(name="Sol Mesa flour tortillas, 20 count", role="tortilla", brand="Sol Mesa", product="sm-flour", price=4.98, serves=8),
    "T3": dict(name="Basics flour tortillas, 10 count", role="tortilla", brand="Basics", product="b-flour", price=1.98, serves=4),
    "P1": dict(name="Ground beef 80/20, 1 lb", role="protein", brand="Ranch Co", product="rc-beef", price=5.48, serves=4, usual=True),
    "P2": dict(name="Ground turkey, 1 lb", role="protein", brand="Ranch Co", product="rc-turkey", price=4.97, serves=4),
    "P3": dict(name="Black beans, 15 oz can", role="protein", brand="Basics", product="b-beans", price=0.98, serves=2),
    "C1": dict(name="Meadow Lane shredded cheddar, 8 oz", role="cheese", brand="Meadow Lane", product="ml-cheddar", price=2.47, serves=6, usual=True),
    "C2": dict(name="Basics shredded Mexican blend, 8 oz", role="cheese", brand="Basics", product="b-mex", price=2.12, serves=6),
    "L1": dict(name="Iceberg lettuce, 1 head", role="topping", brand="", product="lettuce", price=1.48, serves=6, produce=True, usual=True),
    "L2": dict(name="Roma tomatoes, 1 lb", role="topping", brand="", product="tomato", price=1.24, serves=6, produce=True, contains=["tomato"]),
    "L3": dict(name="Yellow onion, 1 each", role="topping", brand="", product="onion", price=0.82, serves=6, produce=True),
    "L4": dict(name="Avocados, 2 count", role="topping", brand="", product="avocado", price=2.50, serves=4, produce=True),
    "L5": dict(name="Limes, 3 count", role="garnish", brand="", product="lime", price=0.99, serves=6, produce=True),
    "X1": dict(name="Taco seasoning, 1 packet", role="seasoning", brand="Basics", product="b-season", price=0.88, serves=4),
    "S1": dict(name="Chunky salsa, 16 oz", role="condiment", kind="salsa", brand="Basics", product="b-salsa", price=2.68, serves=8),
    "S2": dict(name="Sour cream, 16 oz", role="condiment", kind="sour_cream", brand="Basics", product="b-sour", price=1.98, serves=8),
    "A1": dict(name="Lager, 6 pack", role="drink", category="alcohol", brand="Hill Brew", product="hb-lager", price=8.98, serves=6),
    "D1": dict(name="Churro bites, 12 oz", role="dessert", sponsored=True, brand="Fiesta Snacks", product="fs-churro", price=3.48, serves=6),
}
USUALS = {"usual:tortilla#a1": "T1", "usual:cheddar#b7": "C1"}
TEMPLATE = {"required": ["tortilla", "protein", "cheese", "topping"], "optional": ["seasoning", "garnish", "condiment"]}
ROLE_WORDS = {"tortilla": "tortillas", "protein": "a protein (meat or beans)", "cheese": "cheese", "topping": "a vegetable topping"}

# A clean answer Sparky could give: each option complete, under budget, true to its goal.
BASE = [
    ("repeat", [("T1", 1), ("P1", 1), ("C1", 1), ("L1", 1), ("X1", 1)]),
    ("fresh", [("T1", 1), ("P2", 1), ("C1", 1), ("L1", 1), ("L3", 1), ("L4", 1), ("L5", 1)]),
    ("savings", [("T1", 1), ("P3", 2), ("C1", 1), ("L3", 1), ("X1", 1)]),
]
SLOTS = ["4:30 PM", "5:00 PM"]
TAX, FEE = 0.02, 0.0   # synthetic


def world(out_of_stock=()):
    cat = copy.deepcopy(CATALOG)
    for iid, it in cat.items():
        it["upc"] = iid
        it["in_stock"] = iid not in out_of_stock
    return {"catalog": cat, "usuals": dict(USUALS), "template": TEMPLATE, "role_words": ROLE_WORDS,
            "tax": TAX, "fee": FEE, "label": "synthetic"}
