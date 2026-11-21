"""Consumer-side contract checks for the demo console.

The console never trusts a message it renders. These are the console's half of each contract; the owners'
schemas land in packages/contracts/ at the Nov 22 freeze and replace the field lists here.

  Poll@1          owner A, fork-a/poll-v1.yaml (confirmed for Fork H, log Nov 19)
  Card@0          owner F (components@2) + Fork H's additive draft fields, checked by card_writer.guard
  Readout@0       owner F, draft fields by Fork G (fork-g/.../docs/contracts-proposed.yaml); served by G
  ControlDelta@0  owner F, draft fields by Fork G (same file)
  readout-view@0  Fork H internal: E16's render model built from Readout@0 on the server (e16_view.py)
  Request, Result@0  owner F (components@2)
"""
from __future__ import annotations

import re

ROLES = {"owner", "partner", "teen", "kid", "guest", "requester", "approver_payer", "key_holder", "treasurer", "fulfiller"}
REFUSALS = {"LOCK_VIOLATION", "OVER_CAP", "OUT_OF_MANDATE", "RIGHTS_DENIED", "PROFILE_SCOPE", "ADDRESS_MISMATCH",
            "INFEASIBLE", "UNVERIFIED_CLAIM", "CAPABILITY_UNAVAILABLE", "STALE", "AMBIGUOUS"}
# synthetic | public:<src> is the shared rule; observed:<src> (room votes) is Fork H's draft; score:/weight:/derived: are
# Fork G's draft labels. One vocabulary is asked of F in the coordination log.
LABEL = re.compile(r"^(synthetic|public:[\w.:/-]+|observed:[\w.:/-]+|score:[\w.@:/-]+|weight:[\w.:/-]+|derived:[\w.:/-]+)$")
NEVER_TUNABLE = {"price", "per_person_price", "hard_rules", "locks", "fairness_floor", "data_source"}

DRAFT_FIELDS = {
    "Poll@1": ["poll.opened.options[] for 'room is Jen' (asked of A)", "live turnout while open (asked of A)"],
    "Card@0": ["headline", "actions[]", "sections[].option", "lines[].mark", "claims[].label", "kind=readback"],
}


class ContractError(ValueError):
    pass


def _need(obj: dict, keys, where: str):
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ContractError(f"{where}: missing {missing}")


# ------------------------------------------------------------------ Poll@1
def check_poll_common(msg: dict, kind: str):
    _need(msg, ["type", "poll_version", "poll_id", "episode_id", "clock"], kind)
    if msg["type"] != kind or msg["poll_version"] != "poll@1":
        raise ContractError(f"{kind}: wrong type or version")
    _need(msg["clock"], ["sim_now", "wall_now", "rate"], f"{kind}.clock")


def check_poll_opened(msg: dict) -> None:
    check_poll_common(msg, "poll.opened")
    _need(msg, ["mandate_id", "household_hash", "opened_at", "closes_at", "reminder_at", "policy", "carts", "rights",
                "pick_add_list", "ballot_cards"], "poll.opened")
    if msg["policy"] not in ("owner_decides", "auto_plurality", "auto_approval", "weighted", "owner_only"):
        raise ContractError("poll.opened: unknown policy")
    if not msg["carts"] and not msg.get("options"):
        raise ContractError("poll.opened: no carts")
    for c in msg["carts"]:
        _need(c, ["cart_id", "label", "vector", "total", "budget_delta", "ready_by", "slot_status", "lines_hash",
                  "sponsored_count", "substitute_count", "claims_ref"], "poll.opened.carts[]")
        if not isinstance(c["total"], str):
            raise ContractError("poll.opened: totals travel as decimal strings")
    for role in msg["rights"]:
        if role not in ROLES:
            raise ContractError(f"poll.opened: unknown role {role}")


def check_poll_response(msg: dict, opened: dict) -> None:
    check_poll_common(msg, "poll.response")
    _need(msg, ["member_hash", "role", "vote", "request", "ballot_token_sha256", "idempotency_key", "sent_at"], "poll.response")
    if msg["poll_id"] != opened["poll_id"]:
        raise ContractError("poll.response: poll_id mismatch")
    rights = set(opened["rights"].get(msg["role"], []))
    if msg["vote"] is not None:
        if "vote" not in rights:
            raise ContractError(f"poll.response: role {msg['role']} may not vote")
        valid = {c["cart_id"] for c in opened["carts"]} | {o["option_id"] for o in opened.get("options", [])}
        if msg["vote"] not in valid:
            raise ContractError("poll.response: vote for an option not on the ballot")
    req = msg["request"]
    if req:
        need = {"free_text": "free_text", "one_request": "one_request", "pick_add": "pick_add", "flag": "flags_only"}[req["kind"]]
        if need not in rights:
            raise ContractError(f"poll.response: role {msg['role']} has no right {need}")
        if req["kind"] == "one_request" and len(req.get("text") or "") > 80:
            raise ContractError("poll.response: teen request over 80 characters")
        if req["kind"] == "pick_add" and req.get("item_ref") not in {p["item_ref"] for p in opened["pick_add_list"]}:
            raise ContractError("poll.response: pick not on the pick_add_list")


def check_poll_closed(msg: dict) -> None:
    check_poll_common(msg, "poll.closed")
    _need(msg, ["closed_at", "reason", "tally", "turnout"], "poll.closed")


def check_decision(msg: dict) -> None:
    check_poll_common(msg, "decision")
    _need(msg, ["decision_id", "cart_id", "policy", "tie_break", "recheck", "next_state", "decided_at", "explanation_card"], "decision")
    if msg["next_state"] not in ("awaiting_owner", "consent_pending", "booked", "lapsed"):
        raise ContractError("decision: bad next_state")


# ------------------------------------------------------------------ Request, Result@0
def check_request(req: dict) -> None:
    _need(req, ["text", "actor", "channel", "locale", "received_at"], "Request")
    if req["channel"] not in ("chat", "voice", "trigger"):
        raise ContractError("Request: bad channel")
    if req["actor"].get("role") not in ROLES:
        raise ContractError("Request: bad actor role")


def check_result(res: dict) -> None:
    if len(res) != 1 or next(iter(res)) not in ("ok", "refusal", "error"):
        raise ContractError("Result@0: exactly one of ok | refusal | error")
    if "refusal" in res and res["refusal"]["code"] not in REFUSALS:
        raise ContractError(f"Result@0: unknown refusal code {res['refusal']['code']}")


# ------------------------------------------------------------------ Fork G's Readout@0 / ControlDelta@0 (drafts)
def _labeled(v, where):
    if not (isinstance(v, dict) and "value" in v and "label" in v):
        raise ContractError(f"Readout@0: {where} is not a {{value, label}} number")


def check_g_readout(ro: dict) -> None:
    _need(ro, ["contract", "bank_id", "run_id", "profile_id", "lens", "answer_first", "top_k", "two_by_two", "clamp_log",
               "unlabeled_numbers", "readout_hash"], "Readout@0")
    if ro["unlabeled_numbers"] != 0:
        raise ContractError("Readout@0: unlabeled_numbers must be 0")
    for row in ro["top_k"]:
        _need(row, ["rank", "family_id", "title", "tier", "value_at_stake_usd"], "Readout@0.top_k[]")
        _labeled(row["value_at_stake_usd"], f"{row['family_id']}.value_at_stake_usd")
        _labeled(row["tier"], f"{row['family_id']}.tier")


def check_g_delta_event(ev: dict) -> None:
    _need(ev, ["delta_id", "seq", "session", "at", "bank_id", "profile_id", "op", "path", "requested", "prev", "applied",
               "status", "codes", "readout_hash", "prev_hash", "hash"], "ControlDelta@0")
    if ev["status"] not in ("applied", "clamped", "rejected"):
        raise ContractError("ControlDelta@0: bad status")


def check_delta_request(req: dict) -> None:
    _need(req, ["op"], "ControlDelta@0 request")
    if req["op"] not in ("set", "scale", "reset", "lens", "scenario", "switch"):
        raise ContractError("ControlDelta@0: unknown op")
    if any(p in NEVER_TUNABLE for p in req.get("path", []) or []):
        raise ContractError(f"ControlDelta@0: {'/'.join(req['path'])} is never tunable")


# ------------------------------------------------------------------ readout-view@0 (Fork H internal)
def check_view(v: dict) -> None:
    _need(v, ["view_id", "version", "kind", "source", "profile", "answer_first", "portfolio", "claims"], "readout-view@0")
    claims = {}
    for c in v["claims"]:
        _need(c, ["id", "display", "label", "verified_by"], "readout-view@0.claims[]")
        if not LABEL.match(c["label"]):
            raise ContractError(f"readout-view@0: claim {c['id']} has a bad label {c['label']}")
        claims[c["id"]] = c
    for p in v["portfolio"]:
        if p["vas_claim"] not in claims:
            raise ContractError(f"readout-view@0: row {p['family_id']} cites a missing claim")
    if v.get("quad"):
        for pt in v["quad"]["points"]:
            if not (0 <= pt["pos"]["x"] <= 1 and 0 <= pt["pos"]["y"] <= 1):
                raise ContractError("readout-view@0: 2x2 positions must be 0..1 (E12 normalises them)")
