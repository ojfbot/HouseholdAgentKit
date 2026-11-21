import re, json
from semantic_render import render

HW = {"brief_version": "brief@1", "mandate_id": "m_hw_c21_001", "round": 0, "occasion": "taco_night",
      "headcount": {"adults": 2, "kids": 2},
      "deadline": {"type": "pickup_ready_by", "time": "2026-12-02T17:30:00-06:00", "store": "store_rr_01"},
      "budget": {"max": 25.00, "currency": "USD", "includes": ["tax", "fees"], "hard": True},
      "locks": [{"item_ref": "usual:tortilla#a1", "rule": "exact_item_and_packaging", "no_substitutes": True},
                {"item_ref": "usual:cheddar#b7", "rule": "exact_item", "no_substitutes": True}],
      "exclude": [{"kind": "ingredient", "value": "tomato", "hard": False}, {"kind": "category", "value": "alcohol", "hard": True}],
      "on_hand": ["salsa", "sour_cream"],
      "ask": {"options": 3, "vectors": ["repeat", "fresh", "savings"], "format": "line_items_with_price_and_stock", "include": ["slot_options"]},
      "disclosure": {"mark_sponsored": True, "mark_substitutes": True}}
NEVER = ["mandate_id", "m_hw_c21_001", "age", "years old", "allerg", "because", "diagnos", "autis", "arfid", "snap", "ebt", "household_hash", "@", "phone"]

def body(t): return t.split("The same request as data")[0]

def test_every_hard_constraint_in_words_twice():
    t = body(render(HW, store_label="Round Rock Supercenter"))
    for needle in ["$25.00 or less including tax and fees", "5:30 PM", "our usual tortilla", "our usual cheddar", "no alcohol"]:
        assert t.lower().count(needle.lower()) >= 2, needle

def test_deadline_is_fulfillment_not_cooking():
    assert "not a cooking time" in render(HW)

def test_opaque_refs_never_alone():
    t = body(render(HW))
    for ref in ["usual:tortilla#a1", "usual:cheddar#b7"]:
        i = t.index(ref); assert "our usual" in t[max(0, i - 40):i]

def test_disclosure_rules_hold_in_prose():
    t = body(render(HW)).lower()
    for w in NEVER: assert not re.search(r"\b" + re.escape(w), t), w

def test_soft_stays_soft():
    t = render(HW)
    assert "Leave out tomato if you can." in t and "No tomato" not in t

def test_json_appendix_is_last_and_optional():
    t = render(HW, include_json=True)
    assert t.rstrip().endswith("```") and "Must:" in t.split("```json")[0]
    assert "```" not in render(HW)

def test_answer_shape_asks_for_unknown_not_guess():
    assert 'write "unknown" rather than guessing' in render(HW)

def test_length_one_screen():
    assert len(body(render(HW, store_label="Round Rock Supercenter")).split()) <= 300

def test_answer_is_list_shaped():
    assert "one item per line as: item, quantity, price, in stock or not" in render(HW)

def test_generic_request_fails_the_same_checks():
    generic = "Taco night for under $25 by 6pm."
    assert "not a cooking time" not in generic and "our usual" not in generic

def test_allergen_is_a_rule_without_a_reason():
    b = dict(HW, exclude=HW["exclude"] + [{"kind": "allergen", "value": "peanuts", "hard": True}])
    t = body(render(b)).lower()
    assert "no peanuts, including products that may contain it" in t and "allerg" not in t
