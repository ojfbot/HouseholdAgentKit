"""Deterministic K11 templates, one per (kind, role). This is the tier-`none` fallback (ADR-006).

A template returns a card *draft*: Card@0 `sections` and `actions` whose line text may hold `{c:<claim_id>}`
placeholders. The writer (writer.py) fills the placeholders from claims and sets `claim_ref`, so a template
or a model never types a number. One placeholder per line at most.

Facts are words only (labels, names, the poll's rights). Every number arrives as a claim.
"""
from __future__ import annotations

KINDS_BY_ROLE = {
    "owner": {"ballot", "approval", "digest"},
    "partner": {"ballot"},
    "teen": {"ballot"},
    "kid": {"ballot"},
    "approver_payer": {"over_cap", "digest", "approval"},
    "requester": {"readback"},
}


def _vote_actions(carts, prefix="Pick"):
    return [
        {"action_id": f"vote:{c['cart_id']}", "kind": "vote", "label": f"{prefix} {c['label']}", "option": c["cart_id"]}
        for c in carts
    ]


def ballot(audience: dict, facts: dict) -> dict:
    role = audience["role"]
    rights = set(facts.get("rights", {}).get(role, ["vote"]))
    carts = facts["carts"]
    show_prices = role in ("owner", "partner") or (role == "teen" and facts.get("teen_sees_prices", False))
    sections = []
    for cart in carts:
        cid = cart["cart_id"]
        lines = []
        if role == "kid":
            lines += [{"text": h} for h in cart.get("kid_words", cart.get("highlights", []))[:3]]
        else:
            if show_prices:
                lines.append({"text": "Total {c:total.%s}" % cid})
            ready = "Ready by {c:slot.%s}" % cid
            if cart.get("ready_status", "estimated") != "confirmed":
                ready += " (estimated)"
            lines.append({"text": ready})
            lines += [{"text": h} for h in cart.get("highlights", [])[:2]]
            if cart.get("lock_note"):
                lines.append({"text": cart["lock_note"], "mark": "lock"})
            if cart.get("sponsored_note"):
                lines.append({"text": cart["sponsored_note"], "mark": "sponsored"})
        sections.append({"title": cart["label"], "option": cid, "lines": lines})

    actions = _vote_actions(carts, "Pick" if role != "kid" else "I pick")
    if "free_text" in rights:
        actions.append({"action_id": "free_text", "kind": "free_text", "label": "Tell the owner something", "max_len": 200})
    if "one_request" in rights:
        actions.append({"action_id": "request", "kind": "request", "label": "Ask for one thing", "max_len": 80})
    if "pick_add" in rights:
        for item in facts.get("pick_add", [])[:4]:  # Poll@1 pick_add_list entries, or plain words
            ref, label = (item["item_ref"], item["label"]) if isinstance(item, dict) else (item, item)
            actions.append({"action_id": f"pick_add:{ref}", "kind": "pick_add", "label": f"Please add {label}", "option": ref})
    header = facts.get("question", "Which taco night should we do?")
    return {"headline": header, "sections": sections, "actions": actions}


def approval(audience: dict, facts: dict) -> dict:
    cid = facts["decided_cart_id"]
    lines = [
        {"text": "Total {c:total.%s}" % cid},
        {"text": "Ready by {c:slot.%s}%s" % (cid, "" if facts.get("ready_status") == "confirmed" else " (estimated)")},
    ]
    if facts.get("policy_words"):
        lines.append({"text": f"Decided by: {facts['policy_words']}"})
    if facts.get("reason"):
        lines.append({"text": facts["reason"]})
    tally = [{"text": "%s: {c:votes.%s}" % (c["label"], c["cart_id"])} for c in facts.get("tally_carts", [])]
    sections = [{"title": facts["decided_label"], "lines": lines}]
    if tally:
        sections.append({"title": "Votes from the family", "lines": tally})
    actions = [
        {"action_id": "approve", "kind": "approve", "label": "Approve and check out"},
        {"action_id": "pick_other", "kind": "decline", "label": "Pick a different cart"},
    ]
    return {"headline": facts.get("headline", "Ready for your OK"), "sections": sections, "actions": actions}


def over_cap(audience: dict, facts: dict) -> dict:
    who = facts.get("requester_name", "Mom")
    sections = [
        {"title": f"{who} asked", "lines": [{"text": "“{c:words}”", "mark": "quote"}]},
        {
            "title": "Why you're seeing this",
            "lines": [
                {"text": "%s: {c:item_price}" % facts["item_title"]},
                {"text": "This order: {c:order_total}"},
                {"text": "%s's limit per order: {c:cap_per_order}" % facts.get("profile_name", who)},
                {"text": facts.get("ship_to_words", "Ships only to her address")},
            ],
        },
    ]
    call_label = facts.get("call_label", f"Call {who}")
    actions = [
        {"action_id": "approve", "kind": "approve", "label": "Approve this order"},
        {"action_id": "suggest_smaller", "kind": "counter", "label": "Suggest a smaller one"},
        {"action_id": "call", "kind": "defer", "label": call_label},
    ]
    return {"headline": facts.get("headline", f"{who}'s order is over her limit"), "sections": sections, "actions": actions}


def digest(audience: dict, facts: dict) -> dict:
    name = facts.get("profile_name", "Ruth")
    if facts.get("variant") == "profile":
        lines = [{"text": "Limit per order: {c:cap_per_order}"}, {"text": "Limit per month: {c:cap_per_month}"}]
        lines += [{"text": w, "mark": "ok"} for w in facts.get("settings_words", [])]
        return {"headline": facts.get("headline", f"A care profile for {name}"),
                "sections": [{"title": facts.get("profile_title", name), "lines": lines}], "actions": []}
    lines = [
        {"text": "Spent this month: {c:month_spend}"},
        {"text": "Monthly limit: {c:cap_per_month}"},
        {"text": "Orders this month: {c:orders_count}"},
    ]
    notes = [{"text": n, "mark": facts.get("note_mark", "info")} for n in facts.get("notes", [])]
    sections = [{"title": f"{name}'s month", "lines": lines}]
    if notes:
        sections.append({"title": "Worth knowing", "lines": notes})
    return {"headline": facts.get("headline", f"{name}'s groceries this month"), "sections": sections, "actions": []}


def readback(audience: dict, facts: dict) -> dict:
    items = facts["items"]
    joined = ", ".join(items[:-1]) + (" and " if len(items) > 1 else "") + items[-1]
    lines = [{"text": f"I'm getting {joined}."}, {"text": f"Coming {facts['when_words']} to {facts.get('place_words', 'your house')}."}]
    for held in facts.get("held_words", []):
        lines.append({"text": held, "mark": "lock"})
    return {"headline": facts.get("headline", "Here's your order"), "sections": [{"title": "Your order", "lines": lines}], "actions": []}


def packaging_change(audience: dict, facts: dict) -> dict:
    """Fork A's `packaging_change@1` copy (hw-taco@1, HW-PKG-01). Numbers moved off the buttons onto claim lines,
    one number per line, so every number carries its claim; the buttons keep A's words."""
    who = facts.get("member_name", "Maya")
    lines = [
        {"text": f"The {facts['item_words']} switch to new packaging on " + "{c:effective_date}."},
        {"text": f"Her rule is exact item and packaging, so I won't swap the new one in.", "mark": "lock"},
        {"text": "Tonight's cart has {c:tonight_packs} pack of the current packaging, in stock."},
    ]
    stock = [{"text": "Add {c:stockup_packs} more packs of the current packaging"}]
    if facts.get("stockup_separate"):
        stock.append({"text": "As a separate pickup order: {c:stockup_delta}"})
        stock.append({"text": "It would take tonight over your limit, so it stays apart."})
    else:
        stock.append({"text": "Adds {c:stockup_delta}"})
    sections = [{"title": "What's changing", "lines": lines},
                {"title": "If you want to stock up", "lines": stock},
                {"title": "Nothing changes until you pick.", "lines": []}]
    actions = [
        {"action_id": "stock_up", "kind": "approve", "label": "Stock up now"},
        {"action_id": "remind", "kind": "defer", "label": "Remind me before the next order"},
        {"action_id": "do_nothing", "kind": "decline", "label": "Do nothing"},
    ]
    return {"headline": f"Heads-up: {who}'s tortillas are changing", "sections": sections, "actions": actions}


def explanation(audience: dict, facts: dict) -> dict:
    """Poll@1 decision.explanation_card: says why (policy, tie rule, stale winner, default ran)."""
    lines = [{"text": facts["why"]}]
    if facts.get("winner_label"):
        lines.insert(0, {"text": f"Decided: {facts['winner_label']}"})
    lines += [{"text": "%s: {c:votes.%s}" % (c["label"], c["cart_id"])} for c in facts.get("tally_carts", [])]
    if facts.get("turnout"):
        lines.append({"text": "Phones that voted: {c:turnout.voted}"})
    return {"headline": facts.get("headline", "Why this cart"), "sections": [{"title": "How it was decided", "lines": lines}], "actions": []}


def _approval_or_variant(audience: dict, facts: dict) -> dict:
    return packaging_change(audience, facts) if facts.get("template") == "packaging_change@1" else approval(audience, facts)


def _digest_or_variant(audience: dict, facts: dict) -> dict:
    return explanation(audience, facts) if facts.get("template") == "explanation@1" else digest(audience, facts)


TEMPLATES = {"ballot": ballot, "approval": _approval_or_variant, "over_cap": over_cap, "digest": _digest_or_variant, "readback": readback}
