"""Scripted stand-in for Sparky in gateway mode (text in, text out) for push@1 tests.

Not a model and not a claim about how Sparky behaves: each persona starts from the clean BASE answer
with a set of flaws, and a flaw is fixed when a follow-up line names it (its target word and its
option) at or above the flaw's ladder level. HP's mock Sparky should grow the same personas.
"""
import copy

from taco_twin import CATALOG, BASE, SLOTS, TAX, FEE

LABEL_ITEM = {"our usual tortilla": "T1", "our usual cheddar": "C1"}
HEADERS = {"repeat": "repeats what you usually buy", "fresh": "leans on fresh produce", "savings": "costs the least"}

PERSONAS = {
    "clean": {"flaws": []},
    "eager": {"flaws": [
        {"kind": "swap", "opt": 2, "from": "T1", "to": "T3", "fix_at": 1, "target": "our usual tortilla"},
        {"kind": "add", "opt": 0, "item": "D1", "fix_at": 1, "target": "churro"},
        {"kind": "unknown_price", "opt": 1, "item": "P2", "fix_at": 1, "target": "turkey"},
        {"kind": "add", "opt": 1, "item": "L2", "fix_at": 1, "target": "tomato"}]},
    "stubborn": {"flaws": [
        {"kind": "swap", "opt": 0, "from": "C1", "to": "C2", "fix_at": 4, "target": "our usual cheddar"},
        {"kind": "total_off", "opt": 1, "delta": 3.0, "fix_at": 1, "target": "total"}]},
    "regressor": {"flaws": [
        {"kind": "swap", "opt": 2, "from": "T1", "to": "T3", "fix_at": 1, "target": "our usual tortilla",
         "on_fix": [{"kind": "swap", "opt": 1, "from": "C1", "to": "C2", "fix_at": 1, "target": "our usual cheddar"}]}]},
    "recipe": {"flaws": [{"kind": "recipe", "opt": None, "fix_at": 1, "target": "not a recipe"}]},
    "asker": {"flaws": [{"kind": "ask", "opt": None, "fix_at": 1, "target": ""}]},
    "oos": {"flaws": [{"kind": "oos", "opt": None, "item": "T1", "sub": "T3", "fix_at": 1, "target": "our usual tortilla"}],
            "out_of_stock": ["T1"]},
    "never": {"flaws": [{"kind": "add", "opt": 0, "item": "A1", "fix_at": 99, "target": "lager"}]},
    "goodgap": {"flaws": [{"kind": "remove", "opt": 1, "items": ["L3", "L4", "L5"], "fix_at": 99, "target": "fresh produce"}]},
}


def level_of(text, reset):
    if reset:
        return 5
    t = text.lower()
    if "you confirmed" in t:
        return 4
    if "yes or no" in t:
        return 3
    if "pick one:" in t:
        return 2
    return 1


class SimSparky:
    def __init__(self, persona, latency=12.0):
        p = PERSONAS[persona]
        self.flaws = copy.deepcopy(p["flaws"])
        self.oos_items = set(p.get("out_of_stock", []))
        self.latency, self.turn, self.oos_said, self.log = latency, 0, False, []

    def _hit(self, f, lines, lvl):
        if lvl == 5:
            return True
        return any(f["target"] in ln and (f["opt"] is None or f"option {f['opt'] + 1}" in ln) for ln in lines)

    def _fix(self, pred, lvl):
        for f in list(self.flaws):
            if pred(f) and lvl >= f["fix_at"]:
                self.flaws.remove(f)
                if f["kind"] == "oos":
                    self.oos_said = True
                self.flaws += copy.deepcopy(f.get("on_fix", []))

    def send(self, text, new_conversation):
        self.turn += 1
        lvl = level_of(text, new_conversation and self.turn > 1)
        lines = [ln.lower() for ln in text.splitlines()]
        reply = None
        if self.turn > 1 and lvl == 3:
            t = text.lower()
            for label, iid in LABEL_ITEM.items():
                if label in t:
                    it = CATALOG[iid]
                    reply = (f"No, {it['name']} is out of stock." if iid in self.oos_items
                             else f"Yes, {it['name']} is in stock at ${it['price']:.2f}.")
                    self._fix(lambda f: f["target"] == label, lvl)
                    break
        elif self.turn > 1:
            self._fix(lambda f: self._hit(f, lines, lvl), lvl)
        reply = reply or self._render()
        self.log.append((text, reply))
        return reply, self.latency

    def _render(self):
        kinds = {f["kind"] for f in self.flaws}
        if "ask" in kinds:
            return "Happy to help. Do you want flour or corn tortillas? Do the kids have any allergies, or ages I should plan around?"
        if "recipe" in kinds:
            return ("Here's a simple recipe for taco night. Step 1: brown the beef with the seasoning. "
                    "Step 2: warm the tortillas. Step 3: top with cheese and lettuce.")
        opts = [[v, [list(x) for x in items], 0.0, set()] for v, items in BASE]   # vector, [[id, qty]], delta, unknown
        for f in self.flaws:
            k = f["kind"]
            if k == "swap":
                for x in opts[f["opt"]][1]:
                    if x[0] == f["from"]:
                        x[0] = f["to"]
            elif k == "add":
                opts[f["opt"]][1].append([f["item"], 1])
            elif k == "remove":
                opts[f["opt"]][1] = [x for x in opts[f["opt"]][1] if x[0] not in f["items"]]
            elif k == "unknown_price":
                opts[f["opt"]][3].add(f["item"])
            elif k == "total_off":
                opts[f["opt"]][2] += f["delta"]
            elif k == "oos":
                for o in opts:
                    for x in o[1]:
                        if x[0] == f["item"]:
                            x[0] = f["sub"]
        out = []
        if self.oos_said:
            name = CATALOG["T1"]["name"]
            out.append(f"{name} is out of stock, so I left tortillas out of every option.")
            for o in opts:
                o[1] = [x for x in o[1] if x[0] not in self.oos_items]
        out.append("Here are three options for taco night.")
        for i, (v, items, delta, unknown) in enumerate(opts):
            out.append(f"\nOption {i + 1}: {HEADERS[v]}")
            sub = 0.0
            for iid, q in items:
                it = CATALOG[iid]
                sub += it["price"] * q
                price = "unknown" if iid in unknown else f"${it['price'] * q:.2f}"
                out.append(f"- {it['name']}, {q}, {price}, in stock")
            out.append(f"Total: ${sub * (1 + TAX) + FEE + delta:.2f}")
        out.append("\nOpen pickup times: " + ", ".join(SLOTS))
        return "\n".join(out)
