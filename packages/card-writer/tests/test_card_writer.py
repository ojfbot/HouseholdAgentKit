import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from card_writer import CardRejected, ModelCardWriter, TemplateCardWriter, check_card, render_value, write_card  # noqa: E402

CLAIMS = [
    {"id": "total.c_a", "value": {"amount": "21.40", "currency": "USD"}, "verified_by": "k03:vr_1#total", "label": "synthetic"},
    {"id": "slot.c_a", "value": "17:15", "verified_by": "k05:slot_1#ready_by", "label": "synthetic"},
    {"id": "total.c_b", "value": {"amount": "24.10", "currency": "USD"}, "verified_by": "k03:vr_2#total", "label": "synthetic"},
    {"id": "slot.c_b", "value": "17:30", "verified_by": "k05:slot_2#ready_by", "label": "synthetic"},
]
FACTS = {
    "carts": [
        {"cart_id": "c_a", "label": "Same as last time", "highlights": ["Ground beef, soft shells"], "kid_words": ["Beef tacos"],
         "lock_note": "Maya's tortillas: exact pack kept"},
        {"cart_id": "c_b", "label": "Fresh pick", "highlights": ["Chicken, extra veggies"], "kid_words": ["Chicken tacos"]},
    ],
    "rights": {"partner": ["vote", "free_text"], "teen": ["vote", "one_request"], "kid": ["vote", "pick_add"]},
    "pick_add": ["queso", "guacamole"],
}
W = TemplateCardWriter()


def aud(role):
    return {"member_hash": f"m_{role}", "role": role}


def test_format():
    assert render_value({"amount": "21.40", "currency": "USD"}) == "$21.40"
    assert render_value({"amount": "75", "currency": "USD"}) == "$75"
    assert render_value("17:15") == "5:15 PM"
    assert render_value("2026-12-02T09:05:00-06:00") == "9:05 AM"
    assert render_value(4) == "4"


def test_partner_ballot_every_number_has_a_claim():
    card = W.write(CLAIMS, aud("partner"), kind="ballot", facts=FACTS)
    check_card(card)
    nums = [l for s in card["sections"] for l in s["lines"] if any(ch.isdigit() for ch in l["text"])]
    assert nums and all(l.get("claim_ref") for l in nums)
    assert {a["kind"] for a in card["actions"]} == {"vote", "free_text"}


def test_kid_ballot_has_no_numbers_and_no_price_claims():
    card = W.write(CLAIMS, aud("kid"), kind="ballot", facts=FACTS)
    assert card["claims"] == []
    assert not any(ch.isdigit() for s in card["sections"] for l in s["lines"] for ch in l["text"])
    assert {a["kind"] for a in card["actions"]} == {"vote", "pick_add"}


def test_teen_without_prices_gets_times_only():
    card = W.write(CLAIMS, aud("teen"), kind="ballot", facts=FACTS)
    assert {c["id"] for c in card["claims"]} == {"slot.c_a", "slot.c_b"}
    req = [a for a in card["actions"] if a["kind"] == "request"]
    assert req and req[0]["max_len"] == 80


def test_deterministic():
    a = W.write(CLAIMS, aud("partner"), kind="ballot", facts=FACTS)
    b = W.write(CLAIMS, aud("partner"), kind="ballot", facts=FACTS)
    assert a == b


def test_unlabeled_claim_is_refused():
    bad = [dict(CLAIMS[0], label="")] + CLAIMS[1:]
    res = write_card(W, {"kind": "ballot", "audience": aud("partner"), "claims": bad, "facts": FACTS})
    assert res["refusal"]["code"] == "UNVERIFIED_CLAIM"


def test_guard_catches_a_stray_number():
    card = W.write(CLAIMS, aud("partner"), kind="ballot", facts=FACTS)
    card["sections"][0]["lines"].append({"text": "Save $3 today"})
    with pytest.raises(CardRejected):
        check_card(card)


def test_kid_cannot_get_an_over_cap_card():
    with pytest.raises(CardRejected):
        W.write([], aud("kid"), kind="over_cap", facts={"item_title": "Space heater"})


OVER_CAP_CLAIMS = [
    {"id": "words", "value": "And a little space heater, the bedroom gets cold", "verified_by": "stt:utt_7#transcript", "label": "synthetic"},
    {"id": "item_price", "value": {"amount": "79", "currency": "USD"}, "verified_by": "k03:vr_9#line_4", "label": "synthetic"},
    {"id": "order_total", "value": {"amount": "96.18", "currency": "USD"}, "verified_by": "k03:vr_9#total", "label": "synthetic"},
    {"id": "cap_per_order", "value": {"amount": "75", "currency": "USD"}, "verified_by": "k08:mandate_ruth#cap_per_order", "label": "synthetic"},
]


def test_over_cap_card_for_jen():
    card = W.write(OVER_CAP_CLAIMS, aud("approver_payer"), kind="over_cap",
                   facts={"requester_name": "Mom", "profile_name": "Ruth", "item_title": "Space heater", "call_label": "Call Mom"})
    check_card(card)
    assert [a["action_id"] for a in card["actions"]] == ["approve", "suggest_smaller", "call"]
    assert card["sections"][0]["lines"][0]["claim_ref"] == "words"


class FakePort:
    def __init__(self, fn):
        self.fn = fn

    def structured(self, *, schema, messages):
        draft = json.loads(messages[1]["content"])["draft"]
        return self.fn(draft)


def test_model_rewrites_words_and_keeps_numbers():
    def polite(d):
        d["headline"] = "Mom needs your OK"
        d["sections"][1]["title"] = "Why this came to you"
        return d
    mw = ModelCardWriter(FakePort(polite))
    res = write_card(mw, {"kind": "over_cap", "audience": aud("approver_payer"), "claims": OVER_CAP_CLAIMS,
                          "facts": {"requester_name": "Mom", "profile_name": "Ruth", "item_title": "Space heater"}})
    card = res["ok"]["value"]
    assert card["headline"] == "Mom needs your OK" and res["ok"]["fallback_used"] is False


@pytest.mark.parametrize("attack", ["invent", "drop", "transport"])
def test_model_mistakes_fall_back_to_the_template(attack):
    def bad(d):
        if attack == "invent":
            d["sections"][1]["lines"][0]["text"] = "Space heater $59 {c:item_price}"
        elif attack == "drop":
            d["sections"][1]["lines"] = d["sections"][1]["lines"][1:]
        else:
            raise TimeoutError("model server down")
        return d
    mw = ModelCardWriter(FakePort(bad))
    res = write_card(mw, {"kind": "over_cap", "audience": aud("approver_payer"), "claims": OVER_CAP_CLAIMS,
                          "facts": {"requester_name": "Mom", "profile_name": "Ruth", "item_title": "Space heater"}})
    assert res["ok"]["fallback_used"] is True and res["ok"]["adapter_id"] == "k11.template@0"
    assert mw.last_fallback_reason


def test_slot_overclaim_rejected():
    """IQ's K03 rule: an estimated slot is never promised, and slot.* lines say estimated/about."""
    import copy
    from card_writer.guard import CardRejected, check_card
    base = W.write(CLAIMS, aud("partner"), kind="ballot", facts=FACTS)
    check_card(base)
    bad = copy.deepcopy(base)
    bad["sections"][0]["lines"].append({"text": "Your pickup is reserved"})
    try:
        check_card(bad)
        raise AssertionError("reserved should fail while the slot is estimated")
    except CardRejected as e:
        assert e.code == "SLOT_OVERCLAIM"
    ok = copy.deepcopy(base)
    ok["sections"][0]["lines"].append({"text": "Price confirmed at checkout"})
    check_card(ok)
    hedge = copy.deepcopy(base)
    for s in hedge["sections"]:
        for line in s["lines"]:
            if (line.get("claim_ref") or "").startswith("slot."):
                line["text"] = line["text"].replace(" (estimated)", "")
    try:
        check_card(hedge)
        raise AssertionError("slot line without 'estimated' should fail")
    except CardRejected as e:
        assert e.code == "SLOT_OVERCLAIM"
