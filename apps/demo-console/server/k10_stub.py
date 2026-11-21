"""K10 stand-in for rehearsal, speaking Poll@1 (fork-a/poll-v1.yaml). K10 itself belongs to PD.

It exists so the ballot can be built and timed before K10 ships. In http mode the host forwards every
poll.response unchanged to K10's bus and renders K10's poll.closed and decision instead of these.

Poll@1 behaviour implemented: a sim clock on every message (stage rate 20), close on time even while phones
join, poll.closed carries the tally and turnout, one decision per poll_id, last vote wins, idempotency keys,
owner_decides waits for the owner, auto_plurality decides at close, tie -> the owner breaks it
(tie_break=owner_weights), no votes -> the owner's default ran. Not implemented (K10's job): fairness
rotation, approval and weighted voting, the stale re-check at close (recheck is always ok here), reminders.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import threading
import time


def iso(t: dt.datetime) -> str:
    return t.isoformat(timespec="seconds")


class SimClock:
    def __init__(self, sim_start: str, rate: float):
        self.sim0 = dt.datetime.fromisoformat(sim_start)
        self.wall0 = time.time()
        self.rate = rate

    def sim_now(self) -> dt.datetime:
        return self.sim0 + dt.timedelta(seconds=(time.time() - self.wall0) * self.rate)

    def stamp(self) -> dict:
        return {"sim_now": iso(self.sim_now()), "wall_now": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
                "rate": self.rate}

    def wall_seconds_until(self, sim_iso: str) -> float:
        return max(0.0, (dt.datetime.fromisoformat(sim_iso) - self.sim_now()).total_seconds() / self.rate)


class PollStub:
    def __init__(self, opened: dict, *, clock: SimClock, default_option: str, eligible, on_change, explain=None):
        self.opened, self.clock, self.default_option = opened, clock, default_option
        self.eligible, self.on_change, self.explain = eligible, on_change, explain
        self.votes: dict[str, str] = {}
        self.requests: list[dict] = []
        self.seen_keys: set[str] = set()
        self.state = "open"
        self.closed: dict | None = None
        self.decision: dict | None = None
        self.lock = threading.Lock()
        self.options = [c["cart_id"] for c in opened["carts"]] or [o["option_id"] for o in opened.get("options", [])]
        self.labels = {c["cart_id"]: c["label"] for c in opened["carts"]} | {o["option_id"]: o["label"] for o in opened.get("options", [])}
        self._timer = threading.Timer(clock.wall_seconds_until(opened["closes_at"]), self.close, kwargs={"reason": "deadline"})
        self._timer.daemon = True
        self._timer.start()

    def _common(self, kind: str) -> dict:
        return {"type": kind, "poll_version": "poll@1", "poll_id": self.opened["poll_id"], "episode_id": self.opened["episode_id"],
                "clock": self.clock.stamp()}

    def respond(self, msg: dict) -> bool:
        with self.lock:
            if self.state != "open" or msg["idempotency_key"] in self.seen_keys:
                return False
            self.seen_keys.add(msg["idempotency_key"])
            if msg.get("vote"):
                self.votes[msg["member_hash"]] = msg["vote"]
            if msg.get("request"):
                self.requests.append({"role": msg["role"], **msg["request"]})
        self.on_change()
        return True

    def close(self, reason: str = "deadline"):
        eligible = self.eligible()  # read outside the stub lock: the callback takes the console lock
        with self.lock:
            if self.state != "open":
                return
            self.state = "closed"
            self._timer.cancel()
            tally = {o: 0 for o in self.options}
            for v in self.votes.values():
                tally[v] = tally.get(v, 0) + 1
            self.closed = {**self._common("poll.closed"), "closed_at": iso(self.clock.sim_now()), "reason": reason, "tally": tally,
                           "turnout": {"voted": len(self.votes), "eligible": max(len(self.votes), eligible)}}
        policy = self.opened["policy"]
        leaders = self._leaders()
        if not self.votes:
            self._decide(self.default_option, "none", "No votes came in before the deadline, so the owner's default ran.")
        elif policy == "auto_plurality" and len(leaders) == 1:
            self._decide(leaders[0], "none", "The family voted; the cart with the most votes won at close.")
        else:
            with self.lock:
                self.state = "awaiting_owner"
        self.on_change()

    def _leaders(self) -> list[str]:
        tally = self.closed["tally"] if self.closed else {}
        top = max(tally.values()) if tally else 0
        return [o for o, n in tally.items() if n == top and n > 0]

    def flip_policy(self, policy: str):
        """The stage toggle. Before close it changes the policy in force; after close it can still decide an
        awaiting poll under auto_plurality. A poll never gets a second decision."""
        self.opened["policy"] = policy
        if self.state == "awaiting_owner" and policy == "auto_plurality":
            leaders = self._leaders()
            if len(leaders) == 1:
                self._decide(leaders[0], "none", "Flipped to auto: the cart with the most votes won.")
        self.on_change()

    def owner_pick(self, option: str):
        if self.state == "open":
            self.close(reason="owner_closed")
        if self.decision:
            return self.decision
        tie = len(self._leaders()) > 1
        why = "The family was tied; the owner broke the tie." if tie else "The poll was advisory; the owner decided."
        return self._decide(option, "owner_weights" if tie else "none", why)

    def _decide(self, option: str, tie_break: str, why: str) -> dict:
        with self.lock:
            if self.decision:
                return self.decision
            did = "dec_" + hashlib.sha256(f"{self.opened['poll_id']}{option}".encode()).hexdigest()[:10]
            self.decision = {**self._common("decision"), "decision_id": did, "cart_id": option, "policy": self.opened["policy"],
                             "tie_break": tie_break, "recheck": {"status": "ok", "reason": None},
                             "next_state": "consent_pending" if option else "lapsed", "decided_at": iso(self.clock.sim_now()),
                             "explanation_card": None, "_why": why, "_label": self.labels.get(option)}
            self.state = "decided"
        if self.explain:
            self.decision["explanation_card"] = self.explain(self.decision, self.closed)
        self.on_change()
        return self.decision
