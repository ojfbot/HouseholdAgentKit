"""Demo console host (D01 shell server, D02 phone ballot relay, D03 Care seam, D06 beat controller, E16 views).

One process on the stage host, Python stdlib only, offline. Serves the stage (/) and the phones (/p, via QR over the
hotspot), keeps the beat state, and pushes snapshots over Server-Sent Events.

The host renders; it does not decide. Every business number it shows arrives in a shared contract:
Poll@1 (A) for the ballot, Card@0 written by K11 from verified claims, Readout@0 / ControlDelta@0 (G) for the
engine, Result@0 for Care. Its own logic is the beat controller, E16's formatting and the rehearsal
stand-ins (K10 stub, fixture engine, scripted Care results).

Run:  python3 server/host.py [--config console.json] [--port 8765]
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import io
import json
import pathlib
import random
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP.parents[1] / "packages" / "card-writer"))
sys.path.insert(0, str(APP / "server"))

from card_writer import CardRejected, ModelCardWriter, OpenAICompatPort, TemplateCardWriter  # noqa: E402
from contracts import (ContractError, check_decision, check_delta_request, check_g_delta_event, check_g_readout,  # noqa: E402
                       check_poll_closed, check_poll_opened, check_poll_response, check_request, check_result, check_view)
from e16_view import delta_view, drill_from_g, view_from_g  # noqa: E402
from k10_stub import PollStub, SimClock  # noqa: E402
from stt_seam import SpeechToText, voice_request  # noqa: E402

FIX = APP / "fixtures"
WEB = APP / "web"
TZ = dt.timezone(dt.timedelta(hours=-6))  # Plano, Dec 2 (CST)
FAMILY_ROLES = ["partner", "teen", "kid"]
DEFAULT_CONFIG = {
    "bind": "0.0.0.0", "port": 8765, "public_url": None,
    "mode": {"poll": "fixture", "engine": "fixture", "care": "fixture", "cards": "template"},
    "engine_url": "http://127.0.0.1:8790", "poll_bus_url": None, "model_url": "http://127.0.0.1:8080", "card_model": "k11-local",
    "stt": {"engine": "auto", "timeout_s": 4.0, "model": None},
    "stage_guard": True, "log_dir": "logs", "seed": 1202,
}
ENGINE_STEPS = [
    {"id": "map", "title": "The map", "say": "Every cell is a problem family, placed on the value ladder."},
    {"id": "flip", "title": "Flip a control", "say": "Marketing's weights move Marketing's portfolio. Floors hold."},
    {"id": "lens", "title": "Flip the lens", "say": "Same world, partner builders' view."},
    {"id": "drill", "title": "Drill into a cell", "say": "Care Profiles: the components it needs."},
]


def now_iso() -> str:
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


def load(path: pathlib.Path):
    return json.loads(path.read_text())


def public(msg: dict | None) -> dict | None:
    return {k: v for k, v in msg.items() if not k.startswith("_")} if msg else None


def sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Telemetry:
    """K26 local JSONL exporter shape. Members appear as role + hash; kids' free inputs are masked."""

    def __init__(self, log_dir: pathlib.Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"console-{dt.date.today().isoformat()}.jsonl"
        self.lock = threading.Lock()

    def emit(self, event: str, component_id: str, **meta):
        if meta.get("role") == "kid" and meta.get("text"):
            meta["text"] = "***"
        rec = {"at": now_iso(), "event": event, "component_id": component_id, "component_version": "fork-h@0", **meta}
        with self.lock, self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")


# ---------------------------------------------------------------- K11 inputs from Poll@1 (mapping, no arithmetic)

def claims_from_carts(carts: list) -> list:
    """Each CartSummary number is a K03-verified claim (claims_ref = the VerifyReport id)."""
    out = []
    for c in carts:
        out.append({"id": f"total.{c['cart_id']}", "value": {"amount": c["total"], "currency": "USD"},
                    "verified_by": f"k03:{c['claims_ref']}#total", "label": "synthetic"})
        out.append({"id": f"slot.{c['cart_id']}", "value": c["ready_by"], "verified_by": f"k03:{c['claims_ref']}#ready_by", "label": "synthetic"})
    return out


def ballot_facts(fx: dict, carts: list, rights: dict) -> dict:
    words = fx["ballot_words"]
    return {"question": words["question"], "teen_sees_prices": words["teen_sees_prices"], "rights": rights,
            "pick_add": fx["poll_opened"]["pick_add_list"],
            "carts": [{"cart_id": c["cart_id"], "label": c["label"], "ready_status": c["slot_status"], **words["carts"][c["cart_id"]]} for c in carts]}


def tally_view(closed: dict, labels: dict) -> dict:
    """poll.closed -> bar rows. Shares are bar lengths for layout, from K10's counts; the UI never counts."""
    tally = closed["tally"]
    top = max(tally.values()) if tally else 0
    return {"turnout": closed["turnout"], "options": [{"option_id": o, "label": labels.get(o, o), "votes": n,
                                                       "share": round(n / top, 3) if top else 0.0} for o, n in tally.items()]}


def empty_poll_view():
    return {"state": None, "opened": None, "closed": None, "decision": None, "clock": None, "tally": None}


def poll_view(p) -> dict:
    if not p:
        return empty_poll_view()
    closed = public(p.closed) if p.closed else None
    return {"state": p.state, "opened": public(p.opened), "closed": closed, "decision": public(p.decision),
            "decision_why": (p.decision or {}).get("_why"), "decision_label": (p.decision or {}).get("_label"),
            "clock": p.clock.stamp(), "tally": tally_view(closed, p.labels) if closed else None}


# ---------------------------------------------------------------- engine ports (fixture | http)

class FixtureEngine:
    """Stored readout-views from the run-0 extract; answers with G-shaped ControlDelta@0 events (hash-chained)."""
    adapter_id = "engine.fixture@run-0"

    def __init__(self):
        meta = load(FIX / "engine" / "deltas.json")
        self.views = {k: load(FIX / "engine" / v) for k, v in meta["readouts"].items()}
        self.flips = meta["flips"]
        for v in self.views.values():
            check_view(v)
        self.reset()

    def reset(self):
        self.current, self.last_in_house, self.seq, self.prev_hash = "default", "default", 0, "0" * 64

    def view(self):
        return self.views[self.current]

    def apply(self, req: dict):
        before = self.current
        if req["op"] == "lens":
            target = "partner" if req["value"] == "partner" else self.last_in_house
        elif req["op"] == "switch":
            if req["value"] not in self.views:
                raise ContractError(f"unknown profile {req['value']}")
            target = self.last_in_house = req["value"]
        else:
            raise ContractError(f"the fixture engine does switch and lens only, not {req['op']} (Fork G's live E11 does all ops)")
        self.current, self.seq = target, self.seq + 1
        v = self.views[target]
        ev = {"contract": "ControlDelta@0 (draft)", "seq": self.seq, "session": "stage",
              "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"), "bank_id": v.get("bank_id") or "bank:run-0@fork-c",
              "profile_id": v["profile"]["profile_id"], "base_profile_hash": before, "profile_hash": target, "op": req["op"],
              "path": req.get("path", []), "requested": req["value"], "prev": before, "applied": target, "status": "applied", "codes": [],
              "clamps_in_readout": len(v.get("clamps", [])), "actor": req.get("actor", {"role": "DX"}), "reason": req.get("reason", "stage flip"),
              "readout_hash": v["view_id"], "prev_hash": self.prev_hash}
        ev["delta_id"] = "CD-" + hashlib.sha256(json.dumps([ev["seq"], ev["session"], ev["op"], ev["path"], ev["applied"], ev["prev_hash"]]).encode()).hexdigest()[:12]
        ev["hash"] = hashlib.sha256(json.dumps(ev, sort_keys=True).encode()).hexdigest()
        self.prev_hash = ev["hash"]
        return ev, v

    def drill(self, family_id: str):
        v = self.views[self.last_in_house]
        d = v["drill"].get(family_id)
        if d:
            c = next((c for c in v["claims"] if c["id"] == d.get("vas_claim")), None)
            d = {**d, "vas": {"display": c["display"], "label": c["label"], "note": c.get("note")} if c else None}
        return d


class HttpEngine:
    """Fork G's live API (fork-g/.../live/server.py): /profiles, /readout, /delta, /family/<id>."""
    adapter_id = "engine.http@E11"

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.flips = load(FIX / "engine" / "deltas.json")["flips"]
        self.functions = {p["profile_id"]: p["function"] for p in self._get("/profiles")}
        self.reset()

    def reset(self):
        self.profile = "default"
        self._view = self._to_view(self._get("/readout?profile=default&session=stage"))

    def _get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=1.0) as r:
            return json.load(r)

    def _to_view(self, ro, ev=None):
        check_g_readout(ro)
        v = view_from_g(ro, function_words=self.functions.get(ro["profile_id"]), delta=ev)
        check_view(v)
        return v

    def view(self):
        return self._view

    def apply(self, req):
        body = json.dumps({**req, "profile_id": self.profile, "session": "stage"}).encode()
        r = urllib.request.Request(self.url + "/delta", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=1.0) as resp:
                out = json.load(resp)
        except urllib.error.HTTPError as e:  # 422 = rejected; the body still carries the event and the readout
            out = json.load(e)
        check_g_delta_event(out["event"])
        if req["op"] == "switch" and out["event"]["status"] != "rejected":
            self.profile = req["value"]
        self._view = self._to_view(out["readout"], out["event"])
        return out["event"], self._view

    def drill(self, family_id):
        return drill_from_g(self._get(f"/family/{urllib.parse.quote(family_id)}"))


# ---------------------------------------------------------------- the console

class Console:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.cond = threading.Condition(self.lock)
        self.version = 0
        self.rng = random.Random(cfg["seed"])
        self.tel = Telemetry(APP / cfg["log_dir"])
        self.template = TemplateCardWriter()
        self.cards = (ModelCardWriter(OpenAICompatPort(cfg["model_url"], cfg["card_model"]), self.template)
                      if cfg["mode"]["cards"] == "model" else self.template)
        self.card_store: dict[str, dict] = {}
        self.stt = SpeechToText(cfg["stt"]["engine"], cfg["stt"]["timeout_s"], cfg["stt"]["model"])
        self.recordings = load(APP / "recordings" / "manifest.json")
        self.hello_fx = load(FIX / "hello" / "episode.json")
        self.tiers_fx = load(FIX / "hello" / "tier-evidence.json")
        self.care_fx = load(FIX / "care" / "episode.json")
        self.compare_fx = load(FIX / "care" / "compare.json")
        self.proof_fx = load(FIX / "proof" / "eval-report.json")
        self.engine = HttpEngine(cfg["engine_url"]) if cfg["mode"]["engine"] == "http" else FixtureEngine()
        self.members: dict[str, dict] = {}
        self.tokens: dict[str, str] = {}  # sha256(ballot token) -> member_hash
        self.beat = 0
        self.steps = {1: 0, 2: 0, 3: 0}
        self.view = {1: "live", 2: "live", 3: "live"}
        self.proof_open = False
        self.hello = self.care = None
        for b in (1, 2, 3):
            self.reset_beat(b)

    # ------------------------------------------------------------ state helpers
    def bump(self):
        with self.cond:
            self.version += 1
            self.cond.notify_all()

    def source(self, beat: int) -> str:
        if self.view[beat] == "recording":
            return "recording"
        key = {1: "poll", 2: "engine", 3: "care"}[beat]
        return "live" if self.cfg["mode"][key] == "http" else "fixture"

    def write(self, kind, audience, claims, facts):
        card = self.cards.write(claims, audience, kind=kind, facts=facts)
        fb = getattr(self.cards, "last_fallback_reason", None)
        self.tel.emit("card.written", "K11", kind=kind, role=audience["role"], card_id=card["card_id"],
                      adapter_id=getattr(self.cards, "adapter_id", "k11"), fallback_used=bool(fb) or self.cards is self.template)
        self.card_store[card["card_id"]] = card
        return card

    def reset_beat(self, beat: int):
        with self.lock:
            self.steps[beat] = 0
            if beat == 1:
                if self.hello and self.hello.get("poll"):
                    self.hello["poll"]._timer.cancel()
                fx = self.hello_fx
                carts = fx["poll_opened"]["carts"]
                self.hello = {"poll": None, "approval": None, "explanation": None, "policy": fx["poll_opened"]["policy"],
                              "menu": self.write("ballot", {"member_hash": "m_owner", "role": "owner"}, claims_from_carts(carts),
                                                 ballot_facts(fx, carts, {"owner": ["vote"]})),
                              "ballots": {}, "tortilla": None, "consent": None}
            elif beat == 2:
                self.engine.reset()
                self.eng = {"view": self.engine.view(), "last_delta": None, "drill": None, "drill_view": None, "history": []}
            elif beat == 3:
                if self.care and self.care.get("poll"):
                    self.care["poll"]._timer.cancel()
                prof = self.care_fx["profile"]
                self.care = {"transcripts": {}, "request": None, "result": None, "cards": {}, "poll": None, "notice": None,
                             "profile_card": self.write("digest", prof["approver"], prof["claims"],
                                                        {"variant": "profile", "profile_title": prof["name"], "profile_name": "Ruth",
                                                         "headline": "One profile for Ruth, inside Jen's account",
                                                         "settings_words": prof["settings_words"]})}
        self.bump()

    # ------------------------------------------------------------ beat controller (D06)
    def set_beat(self, beat: int):
        with self.lock:
            self.beat = beat
        self.tel.emit("beat.enter", "D06", beat=beat, source=self.source(beat) if beat else None)
        self.bump()

    def set_view(self, beat: int, view: str):
        with self.lock:
            self.view[beat] = view
        self.tel.emit("beat.view", "D06", beat=beat, view=view)
        self.bump()

    def step(self, delta: int):
        b = self.beat
        if b == 0:
            return
        steps = {1: self.hello_fx["steps"], 2: ENGINE_STEPS, 3: self.care_fx["steps"]}[b]
        with self.lock:
            new = max(0, min(len(steps) - 1, self.steps[b] + delta))
            if new == self.steps[b]:
                return
            self.steps[b] = new
            sid = steps[new]["id"]
        if delta > 0:
            {1: self._hello_enter, 2: self._engine_enter, 3: self._care_enter}[b](sid)
        self.bump()

    # ------------------------------------------------------------ beat 1: hello world (Poll@1)
    def _hello_enter(self, sid):
        p = self.hello["poll"]
        if sid == "vote" and not p:
            self.open_family_poll()
        elif sid == "tally" and p and p.state == "open":
            p.close(reason="owner_closed")
        elif sid == "tortilla" and not self.hello["tortilla"]:
            fx = self.hello_fx["packaging_change"]
            self.hello["tortilla"] = self.write(fx["kind"], fx["audience"], fx["claims"], fx["facts"])
        elif sid == "approve" and p and p.state == "awaiting_owner":
            leaders = p._leaders()
            if len(leaders) == 1:  # the presenter, as owner, takes the family's clear favourite; a tie waits for 7/8/9
                p.owner_pick(leaders[0])
        elif sid == "order" and self.hello["approval"] and not self.hello["consent"]:
            self.hello["consent"] = copy.deepcopy(self.hello_fx["consent"])
            self.tel.emit("consent.approved", "K17", poll_id=p.opened["poll_id"] if p else None, source="twin stand-in")

    def open_family_poll(self):
        fx = self.hello_fx
        clock = SimClock(fx["clock"]["sim_start"], fx["clock"]["rate"])
        opened = copy.deepcopy(fx["poll_opened"])
        opened["clock"] = clock.stamp()
        opened["policy"] = self.hello["policy"]
        ballots = {r: self.write("ballot", {"member_hash": f"role:{r}", "role": r}, claims_from_carts(opened["carts"]),
                                 ballot_facts(fx, opened["carts"], opened["rights"])) for r in FAMILY_ROLES}
        opened["ballot_cards"] = {r: c["card_id"] for r, c in ballots.items()}
        check_poll_opened(opened)
        with self.lock:
            self.hello.update(ballots=ballots, approval=None, explanation=None, consent=None)
            self.hello["poll"] = PollStub(opened, clock=clock, default_option=fx["no_quorum_default_cart_id"],
                                          eligible=lambda: len(self.members), on_change=self._on_hello_poll, explain=self._explain_hello)
        self._forward("poll.opened", opened)
        self.tel.emit("poll.opened", "D02", poll_id=opened["poll_id"], policy=opened["policy"], rate=clock.rate)

    def _explain_hello(self, decision, closed):
        carts = [{"cart_id": c["cart_id"], "label": c["label"]} for c in self.hello_fx["poll_opened"]["carts"]]
        claims = [{"id": f"votes.{c['cart_id']}", "value": (closed or {}).get("tally", {}).get(c["cart_id"], 0),
                   "verified_by": f"k10:{decision['poll_id']}#poll.closed.tally", "label": "observed:room"} for c in carts]
        facts = {"template": "explanation@1", "why": decision["_why"], "winner_label": decision["_label"], "tally_carts": carts}
        if closed:
            claims.append({"id": "turnout.voted", "value": closed["turnout"]["voted"],
                           "verified_by": f"k10:{decision['poll_id']}#poll.closed.turnout", "label": "observed:room"})
            facts["turnout"] = True
        card = self.write("digest", {"member_hash": "m_owner", "role": "owner"}, claims, facts)
        self.hello["explanation"] = card
        return card["card_id"]

    def _on_hello_poll(self):
        p = self.hello["poll"]
        if not p:
            return
        if p.closed and not p.closed.get("_seen"):
            check_poll_closed(p.closed)
            p.closed["_seen"] = True
            self._forward("poll.closed", p.closed)
        if p.decision and p.decision.get("explanation_card") and not self.hello["approval"]:
            check_decision(public(p.decision))
            self._forward("decision", p.decision)
            self._write_approval(p.decision)
        self.bump()

    def _write_approval(self, decision):
        win = decision["cart_id"]
        cart = next(c for c in self.hello_fx["poll_opened"]["carts"] if c["cart_id"] == win)
        self.hello["approval"] = self.write("approval", {"member_hash": "m_owner", "role": "owner"}, claims_from_carts([cart]),
                                            {"decided_cart_id": win, "decided_label": cart["label"],
                                             "policy_words": "the owner (the family was tied)" if decision["tie_break"] == "owner_weights"
                                             else "the owner" if decision["policy"] == "owner_decides" or decision["_why"].startswith("The poll was advisory")
                                             else "the family vote" if decision["policy"] == "auto_plurality" else "the owner's default",
                                             "ready_status": cart["slot_status"],
                                             "reason": "Walmart's consent gate still asks the owner before checkout.",
                                             "headline": "Ready for your OK"})

    def owner_pick(self, cart_id):
        p = self.hello["poll"]
        if p:
            p.owner_pick(cart_id)

    def flip_policy(self, policy):
        with self.lock:
            self.hello["policy"] = policy
        p = self.hello["poll"]
        self.tel.emit("policy.flip", "D02", policy=policy)
        if p:
            p.flip_policy(policy)
        self.bump()

    # ------------------------------------------------------------ beat 2: engine map (G's Readout@0 via E16)
    def _engine_enter(self, sid):
        if sid == "flip":
            self.engine_flip(self.engine.flips[0]["request"])
        elif sid == "lens":
            self.engine_flip({"op": "lens", "path": [], "value": "partner"})
        elif sid == "drill":
            self.engine_flip({"op": "lens", "path": [], "value": "in_house"})
            self.drill("PF-28")

    def engine_flip(self, req):
        req = {**req, "path": req.get("path", []), "actor": {"role": "DX"}, "reason": req.get("reason", "stage flip")}
        try:
            check_delta_request(req)
        except ContractError:
            self.tel.emit("control.rejected", "E19", op=req.get("op"), path=req.get("path"))
            raise
        t0 = time.perf_counter()
        ev, view = self.engine.apply(req)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        dv = delta_view(ev, {"compute_ms": view.get("compute_ms") if view.get("compute_ms") is not None else ms})
        dv["adapter_id"], dv["roundtrip_ms"] = self.engine.adapter_id, ms
        with self.lock:
            self.eng.update(view=view, last_delta=dv, drill=None, drill_view=None)
            self.eng["history"] = (self.eng["history"] + [dv])[-6:]
        self.tel.emit("control.delta", "E19", delta_id=ev["delta_id"], op=ev["op"], applied=ev["applied"], status=ev["status"],
                      profile_id=ev["profile_id"], roundtrip_ms=ms)
        self.bump()
        return dv

    def drill(self, family_id):
        d = self.engine.drill(family_id) if family_id else None
        with self.lock:
            self.eng["drill"], self.eng["drill_view"] = family_id, d
        self.tel.emit("engine.drill", "E19", family_id=family_id)
        self.bump()

    # ------------------------------------------------------------ beat 3: Care Profiles
    def care_step_id(self):
        return self.care_fx["steps"][self.steps[3]]["id"]

    def _care_enter(self, sid):
        res = self.care_fx["results"]
        if sid == "care" and "usual" in self.care["transcripts"]:
            t = self.care["transcripts"]["usual"]
            self.care_request(t["text"], t["input_mode"], reuse=True)
        elif sid == "decision" and self.care["poll"] and self.care["poll"].state == "open":
            self.care["poll"].close(reason="owner_closed")
        elif sid == "lock":
            fx = res["lock"]["readback"]
            self.care["cards"]["ruth"] = self.write(fx["kind"], fx["audience"], fx["claims"], fx["facts"])
            self.care["notice"] = {"kind": "lock", "text": "Locked item out of stock: held, never swapped."}
        elif sid == "scam":
            r = res["scam"]["result"]
            check_result(r)
            self.care["result"] = r
            self.care["notice"] = {"kind": "refusal", "code": r["refusal"]["code"],
                                   "text": "Gift cards are off on Ruth's profile. Nothing reached checkout; one line in Jen's digest."}
        elif sid == "month":
            fx = res["month"]["digest"]
            self.care["cards"]["jen_digest"] = self.write(fx["kind"], fx["audience"], fx["claims"], fx["facts"])

    def care_request(self, text: str, input_mode: str, reuse: bool = False):
        sid = self.care_step_id()
        step = next(s for s in self.care_fx["steps"] if s["id"] == sid)
        utt_key = step.get("utterance")
        if not utt_key:
            return {"ignored": True, "reason": f"step {sid} takes no request"}
        req = voice_request(text, member_hash="m_ruth", received_at=now_iso())
        check_request(req)
        utt = self.care_fx["utterances"][utt_key]
        matched = any(k in text.lower() for k in utt["match_any"])
        utt_id = "utt_" + hashlib.sha256((text + req["received_at"]).encode()).hexdigest()[:8]
        self.tel.emit("request.voice", "D03", input_mode=input_mode, utterance=utt_key, matched=matched, utt_id=utt_id, step=sid)
        res = self.care_fx["results"]
        with self.lock:
            self.care["request"] = {**req, "_input_mode": input_mode, "_matched": matched, "_utt_id": utt_id}
            if not reuse:
                self.care["transcripts"][utt_key] = {"text": req["text"], "input_mode": input_mode, "utt_id": utt_id}
            if sid == "today":
                self.care["result"] = res["today"]["result"]
            elif sid == "care":
                self.care["result"] = res["care"]["result"]
                fx = res["care"]["readback"]
                self.care["cards"]["ruth"] = self.write(fx["kind"], fx["audience"], fx["claims"], fx["facts"])
            elif sid == "heater":
                self.care["result"] = res["heater"]["result"]
                fx = res["heater"]["over_cap"]
                claims = [dict(c, value=req["text"], verified_by=f"stt:{utt_id}#transcript") if c["id"] == "words" else c for c in fx["claims"]]
                card = self.write(fx["kind"], fx["audience"], claims, fx["facts"])
                self.care["cards"]["jen"] = card
                self._open_jen_poll(card)
            check_result(self.care["result"])
        self.bump()
        return {"ok": True, "matched": matched, "step": sid}

    def _open_jen_poll(self, card):
        """'Room is Jen' (B ask 7) on Poll@1's envelope. Jen's choices are actions, not carts: `options[]` is Fork H's
        draft until A answers (coordination log)."""
        pfx = self.care_fx["results"]["heater"]["poll"]
        clock = SimClock(now_iso(), 1.0)
        start = dt.datetime.fromisoformat(clock.stamp()["sim_now"])
        opened = {"type": "poll.opened", "poll_version": "poll@1", "poll_id": pfx["poll_id"], "episode_id": "ep_care_ruth_01",
                  "clock": clock.stamp(), "mandate_id": "mandate_ruth", "household_hash": "hh_jen", "opened_at": start.isoformat(),
                  "closes_at": (start + dt.timedelta(seconds=pfx["closes_in_s"])).isoformat(),
                  "reminder_at": (start + dt.timedelta(seconds=pfx["closes_in_s"] / 2)).isoformat(),
                  "policy": pfx["policy"], "carts": [], "options": [{"option_id": a["action_id"], "label": a["label"]} for a in card["actions"]],
                  "rights": {"approver_payer": ["vote"]}, "pick_add_list": [], "ballot_cards": {"approver_payer": card["card_id"]}}
        check_poll_opened(opened)
        self.care["poll"] = PollStub(opened, clock=clock, default_option=pfx["no_quorum_default"], eligible=lambda: len(self.members),
                                     on_change=self.bump)
        self._forward("poll.opened", opened)

    # ------------------------------------------------------------ phones (D02, Poll@1 room_mode)
    def join(self, member_hash: str | None, token: str | None = None):
        with self.lock:
            if member_hash and token and self.tokens.get(sha(token)) == member_hash:
                return self._join_reply(member_hash, token)
            mh = "m_" + hashlib.sha256(f"{time.time()}{self.rng.random()}".encode()).hexdigest()[:10]
            counts = {r: sum(1 for m in self.members.values() if m["role"] == r) for r in FAMILY_ROLES}
            fewest = min(counts.values())
            role = self.rng.choice([r for r in FAMILY_ROLES if counts[r] == fewest])
            token = secrets.token_urlsafe(16)
            self.tokens[sha(token)] = mh
            self.members[mh] = {"role": role, "joined_at": now_iso(), "seq": 0, "token_sha": sha(token)}
        self.tel.emit("member.join", "D02", member_hash=mh, role=role)
        self.bump()
        return self._join_reply(mh, token)

    def _join_reply(self, mh, token):
        m = self.members[mh]
        p = self.hello["poll"]
        card_id = p.opened["ballot_cards"].get(m["role"]) if p else None
        return {"member_hash": mh, "role": m["role"], "ballot_link": f"{(self.cfg['public_url'] or '').rstrip('/')}/p?b={token}",
                "card_id": card_id, "ballot_token": token}

    def act(self, member_hash: str, token: str | None, action_id: str, text: str | None = None):
        m = self.members.get(member_hash)
        if not m or not token or sha(token) != m["token_sha"]:
            raise ContractError("unknown member or ballot link: scan the code again")
        jen = self.beat == 3 and self.care["poll"] is not None and self.care["poll"].state == "open"
        poll = self.care["poll"] if jen else self.hello["poll"]
        if not poll or poll.state != "open":
            raise ContractError("the poll is closed")
        opened = poll.opened
        role = "approver_payer" if jen else m["role"]
        with self.lock:
            m["seq"] += 1
            seq = m["seq"]
        msg = {"type": "poll.response", "poll_version": "poll@1", "poll_id": opened["poll_id"], "episode_id": opened["episode_id"],
               "clock": poll.clock.stamp(), "member_hash": member_hash, "role": role, "vote": None, "request": None,
               "ballot_token_sha256": m["token_sha"], "idempotency_key": f"{member_hash}-{opened['poll_id']}-{seq}",
               "sent_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        if action_id.startswith("vote:"):
            msg["vote"] = action_id.split(":", 1)[1]
        elif jen:
            msg["vote"] = action_id
        elif action_id.startswith("pick_add:"):
            msg["request"] = {"kind": "pick_add", "item_ref": action_id.split(":", 1)[1]}
        elif action_id == "request":
            msg["request"] = {"kind": "one_request", "text": (text or "")[:80]}
        elif action_id == "free_text":
            msg["request"] = {"kind": "free_text", "text": (text or "")[:200]}
        else:
            raise ContractError(f"unknown action {action_id}")
        check_poll_response(msg, opened)
        poll.respond(msg)
        self._forward("poll.response", msg)
        self.tel.emit("poll.response", "D02", poll_id=msg["poll_id"], role=role, member_hash=member_hash, vote=msg["vote"],
                      request_kind=(msg["request"] or {}).get("kind"), text=(msg["request"] or {}).get("text"))
        return {"ok": True}

    def _forward(self, kind: str, msg: dict):
        """http mode: hand Poll@1 messages to the bus (K23) unchanged. Fixture mode: local stub only."""
        url = self.cfg.get("poll_bus_url")
        if self.cfg["mode"]["poll"] != "http" or not url:
            return
        try:
            req = urllib.request.Request(url.rstrip("/") + "/publish", data=json.dumps({"topic": kind, "message": public(msg)}, default=str).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=0.5).close()
        except Exception as exc:
            self.tel.emit("bus.forward_failed", "K23", kind=kind, error=str(exc))

    def phone_view(self, member_hash: str) -> dict:
        m = self.members.get(member_hash)
        if not m:
            return {"screen": "join"}
        if self.beat == 3 and self.care["poll"]:
            p = self.care["poll"]
            if p.state == "open":
                return {"screen": "card", "role": "approver_payer", "as": "You are Jen", "card": self.care["cards"]["jen"],
                        "opened_at": p.opened["opened_at"], "closes_at": p.opened["closes_at"], "clock": p.clock.stamp(), "voted": member_hash in p.votes,
                        "your_vote": p.votes.get(member_hash)}
            label = (p.decision or {}).get("_label")
            return {"screen": "result", "text": f"Jen's answer: {label}" if label else "Thanks. Jen's answer is in."}
        p = self.hello["poll"]
        if p and p.state == "open":
            return {"screen": "card", "role": m["role"], "as": f"You are the {m['role']}", "card": self.hello["ballots"][m["role"]],
                    "opened_at": p.opened["opened_at"], "closes_at": p.opened["closes_at"], "clock": p.clock.stamp(), "voted": member_hash in p.votes,
                    "your_vote": p.votes.get(member_hash)}
        if p:
            label = (p.decision or {}).get("_label")
            return {"screen": "result", "text": f"Decided: {label}" if label else "The poll is closed. The owner decides."}
        return {"screen": "wait", "role": m["role"], "as": f"You are the {m['role']}"}

    # ------------------------------------------------------------ snapshot for the stage
    def snapshot(self) -> dict:
        with self.lock:
            roles = {r: sum(1 for m in self.members.values() if m["role"] == r) for r in FAMILY_ROLES}
            return {
                "version": self.version, "beat": self.beat, "steps": self.steps, "view": self.view,
                "sources": {b: self.source(b) for b in (1, 2, 3)}, "stage_guard": self.cfg["stage_guard"],
                "join_url": (self.cfg["public_url"] or "").rstrip("/") + "/p", "members": {"total": len(self.members), "roles": roles},
                "proof_open": self.proof_open,
                "hello": {"steps": self.hello_fx["steps"], "request": self.hello_fx["request"], "brief": self.hello_fx["brief"],
                          "sparky": self.hello_fx["sparky_recording"], "menu": self.hello["menu"], "tiers": self.tiers_fx,
                          "policy": self.hello["policy"], "poll": poll_view(self.hello["poll"]), "approval": self.hello["approval"],
                          "explanation": self.hello["explanation"], "tortilla": self.hello["tortilla"], "consent": self.hello["consent"]},
                "engine": {"steps": ENGINE_STEPS, "readout": self.eng["view"], "last_delta": self.eng["last_delta"],
                           "history": self.eng["history"], "drill": self.eng["drill"], "drill_view": self.eng["drill_view"],
                           "flips": self.engine.flips, "adapter_id": self.engine.adapter_id},
                "care": {"steps": self.care_fx["steps"], "step_id": self.care_step_id(), "request": self.care["request"],
                         "result": self.care["result"], "cards": self.care["cards"], "profile_card": self.care["profile_card"],
                         "compare": self.compare_fx, "notice": self.care["notice"], "poll": poll_view(self.care["poll"]),
                         "stt": self.stt.status(), "clip": self.recordings["beats"].get("3v")},
                "proof": self.proof_fx,
                "recordings": self.recordings["beats"],
            }


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    console: Console = None  # set in main
    server_version = "fork-h-console/0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _json(self) -> dict:
        raw = self._body()
        return json.loads(raw) if raw else {}

    def _static(self, rel: str):
        path = (WEB / rel).resolve()
        if WEB not in path.parents or not path.is_file():
            return self._send(404, {"error": "not found"})
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}.get(path.suffix, "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)

    def _sse(self, render):
        c = self.console
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = -1
        try:
            while True:
                with c.cond:
                    if c.version == seen:
                        c.cond.wait(timeout=15)
                    v = c.version
                if v == seen:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    seen = v
                    self.wfile.write(b"data: " + json.dumps(render(), default=str).encode() + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):
        c = self.console
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/stage"):
            return self._static("stage.html")
        if u.path == "/p":
            return self._static("phone.html")
        if u.path.startswith("/static/"):
            return self._static(u.path[len("/static/"):])
        if u.path.startswith("/recordings/"):
            path = APP / "recordings" / pathlib.Path(u.path).name
            if not path.is_file():
                return self._send(404, {"error": "not captured yet"})
            return self._send(200, path.read_bytes(), "video/mp4" if path.suffix == ".mp4" else "audio/mp4")
        if u.path == "/events/stage":
            return self._sse(c.snapshot)
        if u.path == "/events/phone":
            mh = (q.get("m") or [""])[0]
            return self._sse(lambda: c.phone_view(mh))
        if u.path == "/api/state":
            return self._send(200, c.snapshot())
        if u.path == "/api/qr.svg":
            try:
                import segno
                buf = io.BytesIO()
                segno.make(c.snapshot()["join_url"], error="m").save(buf, kind="svg", scale=10, border=2, dark="#14110d", light="#f4ecdc")
                return self._send(200, buf.getvalue(), "image/svg+xml")
            except Exception as exc:
                return self._send(404, {"error": f"QR unavailable ({exc}); show join_url as text"})
        if u.path == "/api/health":
            return self._send(200, {"ok": True, "version": c.version, "stt": c.stt.status(), "mode": c.cfg["mode"],
                                    "engine": c.engine.adapter_id, "cards": getattr(c.cards, "adapter_id", "k11")})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        c = self.console
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/care/voice":
                ctype = self.headers.get("Content-Type", "audio/webm")
                suffix = ".m4a" if "mp4" in ctype else ".ogg" if "ogg" in ctype else ".webm"
                return self._send(200, c.stt.transcribe(self._body(), suffix))
            b = self._json()
            if u.path == "/api/beat":
                c.set_beat(int(b["beat"]))
            elif u.path == "/api/step":
                c.step(int(b.get("delta", 1)))
            elif u.path == "/api/view":
                c.set_view(int(b["beat"]), b["view"])
            elif u.path == "/api/reset":
                c.reset_beat(int(b["beat"]))
            elif u.path == "/api/proof":
                c.proof_open = bool(b.get("open", not c.proof_open))
                c.bump()
            elif u.path == "/api/join":
                return self._send(200, c.join(b.get("member_hash"), b.get("ballot_token")))
            elif u.path == "/api/act":
                return self._send(200, c.act(b["member_hash"], b.get("ballot_token"), b["action_id"], b.get("text")))
            elif u.path == "/api/hello/owner_pick":
                c.owner_pick(b["cart_id"])
            elif u.path == "/api/hello/policy":
                c.flip_policy(b["policy"])
            elif u.path == "/api/engine/delta":
                return self._send(200, c.engine_flip(b["request"]))
            elif u.path == "/api/engine/drill":
                c.drill(b.get("family_id"))
            elif u.path == "/api/care/request":
                return self._send(200, c.care_request(b["text"], b.get("input_mode", "typed")))
            elif u.path == "/api/sim/voters":
                return self._send(200, simulate_voters(c, int(b.get("n", 20))))
            else:
                return self._send(404, {"error": "not found"})
            return self._send(200, {"ok": True, "version": c.version})
        except (ContractError, CardRejected, KeyError, ValueError) as exc:
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})


def simulate_voters(c: Console, n: int) -> dict:
    """Rehearsal only: n scripted phones join and vote. On stage, empty roles are K25's job (Poll@1 room_mode)."""
    done = 0
    for _ in range(n):
        m = c.join(None)
        jen = c.beat == 3 and c.care["poll"] is not None
        try:
            if jen:
                c.act(m["member_hash"], m["ballot_token"], c.rng.choice(["approve", "approve", "suggest_smaller", "call"]))
            else:
                c.act(m["member_hash"], m["ballot_token"], "vote:" + c.rng.choice(["c_a", "c_a", "c_b", "c_c"]))
                if m["role"] == "kid":
                    c.act(m["member_hash"], m["ballot_token"], "pick_add:syn-queso-01")
            done += 1
        except ContractError:
            pass
    return {"voted": done}


def load_config(path: str | None, port: int | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    p = pathlib.Path(path) if path else APP / "console.json"
    if p.is_file():
        for k, v in json.loads(p.read_text()).items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            elif not k.startswith("_"):
                cfg[k] = v
    if port:
        cfg["port"] = port
    if not cfg["public_url"]:
        cfg["public_url"] = f"http://127.0.0.1:{cfg['port']}"
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)
    cfg = load_config(args.config, args.port)
    console = Console(cfg)
    Handler.console = console
    srv = ThreadingHTTPServer((cfg["bind"], cfg["port"]), Handler)
    srv.daemon_threads = True
    print(json.dumps({"ready": True, "url": f"http://127.0.0.1:{cfg['port']}/", "join": cfg["public_url"] + "/p", "mode": cfg["mode"],
                      "stt": console.stt.status()}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
