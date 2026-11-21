"""push@1: keep working with Sparky until the answer is good, not only correct.

Sparky's first answer is a draft. The loop reads it back (parse), grades it (assess) and, while it
is not good yet, writes a follow-up that says what to change, in the same plain words as semantic@1
(compose). It keeps the best version of every option it has seen, so a fix that breaks something
else never costs us. Building the cart ourselves (K04) is the last resort: only when no correct and
accurate answer arrives within the turn and time budget.

Three levels, all required for "good":
  correct   the rules hold: locks, hard excludes, budget, deadline, complete plates, sponsored
            marks, the number of options asked for, products not a recipe
  accurate  the facts hold: every product resolves, prices, stock and totals check out,
            nothing left unknown
  good      it is worth choosing: each option true to its goal, options distinct, soft
            preferences honoured, nothing we already have, sized for the headcount, nothing
            padded in, a pickup time with margin

Ladder per open finding (one step per push about it):
  1 ask      say what to change
  2 pin      quote their line back and offer a choice
  3 isolate  one yes/no question about one item, nothing else
  4 apply    "you confirmed X; put it in option N"
  5 reset    a new conversation: the brief plus what we learned
Isolate and apply exist only for item facts (locks, stock, price); other findings go 1, 2, reset.

Rules the loop keeps:
  - At most three asks per push, most serious first (correct, then accurate, then good).
  - Options already right are named and kept ("send it again unchanged"); a regressed option is
    restored from Sparky's own earlier lines.
  - Questions Sparky asks are answered from the brief; anything about the household gets one fixed
    sentence and nothing else. Every outgoing message passes the disclosure guard.
  - A good first answer gets no push at all.
  - An honest "that item is out of stock" for a locked item is a good answer: the loop stops with
    INFEASIBLE and the family decides. It never swaps a locked item itself.
Deterministic: no model writes these words. Same inputs, same transcript.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from semantic_render import render, _label, _money, RULE_WORDS, VECTOR_WORDS, NUM

DISCLOSURE_NEVER = ["mandate_id", "m_hw_c21_001", "age", "years old", "allerg", "because", "diagnos", "autis",
                    "arfid", "snap", "ebt", "household_hash", "@", "phone"]
LEVEL_ORDER = {"correct": 0, "accurate": 1, "good": 2}
ISOLABLE = {"C_LOCK_SUB", "C_LOCK_MISSING", "A_STOCK", "A_UNKNOWN", "A_PRICE"}
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4}
VECTOR_KEYS = {"repeat": ["usually", "repeat"], "fresh": ["fresh", "produce"], "savings": ["least", "cheapest", "lowest"]}
MAX_ASKS = 3
GOOD_MEAN, GOOD_MIN = 0.9, 0.5
SLOT_MARGIN_MIN = 15
PRIVACY_REPLY = "I can't share more about the household; the rules in my request are everything you need."


class DisclosureError(Exception):
    pass


def guard(text):
    low = text.lower()
    for w in DISCLOSURE_NEVER:
        if re.search(r"\b" + re.escape(w), low):
            raise DisclosureError(w)
    return text


# ---------------------------------------------------------------- parse
@dataclass
class Line:
    raw: str
    name: str
    qty: int | None
    price: float | None
    stock: str                    # in | out | unknown
    sponsored: bool
    substitute: bool
    item_id: str | None = None


@dataclass
class Option:
    idx: int
    vector: str | None
    lines: list
    total: float | None
    turn: int = 0


@dataclass
class Answer:
    options: list
    slots: list
    questions: list
    oos: list
    recipe: bool
    yes_no: str | None
    raw: str


def _toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def resolve(name, world):
    """Product name -> catalog id. On the twin this is a catalog lookup; live, K24 asks discover()."""
    toks, best, score = _toks(name), None, 0.0
    for iid, it in world["catalog"].items():
        ct = _toks(it["name"])
        if toks == ct:
            return iid
        j = len(toks & ct) / max(1, len(toks | ct))
        if j > score:
            best, score = iid, j
    return best if score >= 0.6 else None


def _dollars(s):
    m = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", s)
    return float(m.group(1).replace(",", "")) if m else None


def minutes(t):
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([AP])\.?M", t.strip(), re.I)
    return (int(m.group(1)) % 12 + (12 if m.group(3).upper() == "P" else 0)) * 60 + int(m.group(2) or 0)


def parse(text, brief, world):
    """Sparky's prose -> Answer. The fixed-pattern fallback for K24's H1 extractor."""
    vectors = brief["ask"]["vectors"]
    opts, cur, slots, questions, oos, yes_no = [], None, [], [], [], None
    for n, raw in enumerate(text.splitlines()):
        s = raw.strip()
        line = s.strip("*").strip()
        if not line:
            continue
        if n == 0 or yes_no is None and not opts:
            m = re.match(r"(yes|no)\b", line, re.I)
            if m:
                yes_no = m.group(1).lower()
        h = re.match(r"option\s+(\d+|one|two|three|four)\b(.*)", line, re.I)
        if h:
            k = int(h.group(1)) if h.group(1).isdigit() else WORDNUM[h.group(1).lower()]
            rest = h.group(2).lower()
            vec = next((v for v, kws in VECTOR_KEYS.items() if v in vectors and any(w in rest for w in kws)), None)
            if vec is None and k - 1 < len(vectors):
                vec = vectors[k - 1]
            cur = Option(idx=k - 1, vector=vec, lines=[], total=None)
            opts.append(cur)
            continue
        if re.match(r"[-•*]\s+", s) and cur is not None:
            body = re.sub(r"^[-•*]\s+", "", s)
            sponsored, substitute = "(sponsored)" in body.lower(), "(substitute)" in body.lower()
            body = re.sub(r"\s*\((sponsored|substitute)\)", "", body, flags=re.I).strip()
            f = [x.strip() for x in body.split(",")]
            if len(f) >= 4:
                name, qs, ps, ss = ", ".join(f[:-3]), f[-3], f[-2], f[-1].lower()
                qty = int(re.sub(r"\D", "", qs)) if re.search(r"\d", qs) else None
                price = None if "unknown" in ps.lower() else _dollars(ps)
                stock = "unknown" if "unknown" in ss else ("out" if ("out" in ss or ss.startswith("not")) else "in")
                cur.lines.append(Line(body, name, qty, price, stock, sponsored, substitute, resolve(name, world)))
                continue
        if re.match(r"total\b", line, re.I) and cur is not None:
            cur.total = _dollars(line)
            continue
        if "pickup" in line.lower() and re.search(r"\d\s*[AP]\.?M", line, re.I):
            seg = line.split(": ", 1)[1] if ": " in line else line
            slots = re.findall(r"\b\d{1,2}(?::\d{2})?\s*[AP]\.?M", seg, re.I)
            continue
        for m in re.finditer(r"([^.;?!]+?)\s+(?:is|are)\s+out of stock", line, re.I):
            oos.append(m.group(1).strip())
        questions += [q.strip() + "?" for q in re.findall(r"([^.?!]+)\?", line)]
    recipe = not opts and bool(re.search(r"\b(recipe|brown the|simmer|preheat|step \d|cook the)\b", text, re.I))
    return Answer(opts, slots, questions, oos, recipe, yes_no, text)


# ---------------------------------------------------------------- assess
@dataclass
class Finding:
    code: str
    level: str
    option: int | None
    key: str
    d: dict = field(default_factory=dict)


@dataclass
class Assessment:
    findings: list
    good: dict                      # check -> 0..1
    score: float
    correct: bool
    accurate: bool
    is_good: bool

    def local_rank(self, i):
        """Option-local quality, lower is better: (correct misses, accurate misses, good shortfall)."""
        fs = [f for f in self.findings if f.option == i]
        short = sum(1 - v for k, v in self.good.items() if k.endswith(f":{i}"))
        return (sum(f.level == "correct" for f in fs), sum(f.level == "accurate" for f in fs), round(short, 3))

    def summary(self):
        return {"correct": self.correct, "accurate": self.accurate, "good": self.is_good,
                "score": round(self.score, 3), "codes": sorted({f.code for f in self.findings})}


def people(brief):
    hc = brief["headcount"]
    return hc["adults"] + hc.get("kids", 0)


def _lock_ok(it, lock_it, rule):
    if rule == "brand_only":
        return it["brand"] == lock_it["brand"]
    if rule == "exact_item":
        return it["product"] == lock_it["product"]
    return it["upc"] == lock_it["upc"]


def _excluded(it, e):
    if e["kind"] == "category":
        return it.get("category") == e["value"]
    if e["kind"] == "allergen":
        return e["value"] in it.get("contains", []) + it.get("may_contain", [])
    return e["value"] in it.get("contains", [])


def computed_total(o, world):
    cat = world["catalog"]
    if not o.lines or any(l.item_id is None for l in o.lines):
        return None
    sub = sum(cat[l.item_id]["price"] * (l.qty or 1) for l in o.lines)
    return round(sub * (1 + world["tax"]) + world["fee"], 2)


def deadline_minutes(brief):
    t = datetime.fromisoformat(brief["deadline"]["time"])
    return t.hour * 60 + t.minute


def assess(ans, brief, world, known_oos=frozenset()):
    cat, n, F, good = world["catalog"], people(brief), [], {}
    tmpl = world["template"]
    allowed_roles = set(tmpl["required"]) | set(tmpl["optional"])
    hard_ex = [e for e in brief.get("exclude", []) if e.get("hard")]
    soft_ex = [e for e in brief.get("exclude", []) if not e.get("hard")]
    on_hand = set(brief.get("on_hand", []))
    oos_roles = {cat[x]["role"] for x in known_oos}
    budget = brief["budget"]["max"]

    if ans.recipe:
        F.append(Finding("C_RECIPE", "correct", None, "recipe"))
    elif len(ans.options) < brief["ask"]["options"]:
        F.append(Finding("C_OPTION_COUNT", "correct", None, "count", {"got": len(ans.options)}))

    for o in ans.options:
        i = o.idx
        items = [(l, cat.get(l.item_id)) for l in o.lines]
        roles = {}
        for l, it in items:
            if it is None:
                F.append(Finding("A_UNRESOLVED", "accurate", i, f"unres:{i}:{l.name.lower()}", {"line": l}))
            else:
                roles.setdefault(it["role"], []).append((l, it))
        lock_roles = set()
        for lk in brief.get("locks", []):
            lock_it = cat[world["usuals"][lk["item_ref"]]]
            lock_roles.add(lock_it["role"])
            got = roles.get(lock_it["role"], [])
            key = f"lock:{lk['item_ref']}:{i}"
            if not got and lock_it["upc"] not in known_oos:
                F.append(Finding("C_LOCK_MISSING", "correct", i, key, {"lock": lk}))
            for l, it in got:
                if not _lock_ok(it, lock_it, lk["rule"]):
                    F.append(Finding("C_LOCK_SUB", "correct", i, key, {"lock": lk, "line": l}))
        for role in tmpl["required"]:
            cover = sum(it["serves"] * (l.qty or 1) for l, it in roles.get(role, []))
            if cover < n and role not in lock_roles and role not in oos_roles:
                F.append(Finding("C_INCOMPLETE", "correct", i, f"role:{role}:{i}", {"role": role}))
        soft = onhand = pad = over = 1.0
        for l, it in items:
            if it is None:
                continue
            for e in hard_ex:
                if _excluded(it, e):
                    F.append(Finding("C_HARD_EXCLUDE", "correct", i, f"ex:{e['value']}:{i}", {"line": l, "value": e["value"]}))
            padding = it["role"] not in allowed_roles and it.get("category") not in {e["value"] for e in hard_ex}
            if it.get("sponsored") and not l.sponsored:
                F.append(Finding("C_UNMARKED_SPONSORED", "correct", i, f"item:{l.item_id}:{i}", {"line": l, "padding": padding}))
            if l.price is None or l.stock == "unknown":
                F.append(Finding("A_UNKNOWN", "accurate", i, f"fact:{l.item_id}:{i}",
                                 {"line": l, "what": "price" if l.price is None else "stock"}))
            elif not any(abs(l.price - it["price"] * q) <= 0.01 for q in {1, l.qty or 1}):
                F.append(Finding("A_PRICE", "accurate", i, f"fact:{l.item_id}:{i}", {"line": l, "true": it["price"]}))
            if l.stock in ("in", "out") and (l.stock == "in") != it.get("in_stock", True):
                F.append(Finding("A_STOCK", "accurate", i, f"stock:{l.item_id}:{i}", {"line": l}))
            for e in soft_ex:
                if _excluded(it, e):
                    soft = 0.0
                    F.append(Finding("G_SOFT_EXCLUDE", "good", i, f"item:{l.item_id}:{i}", {"line": l, "value": e["value"]}))
            if it.get("kind") in on_hand:
                onhand = 0.0
                F.append(Finding("G_ON_HAND", "good", i, f"item:{l.item_id}:{i}", {"line": l, "value": it["kind"].replace("_", " ")}))
            if padding:
                pad = 0.0
                F.append(Finding("G_PADDING", "good", i, f"item:{l.item_id}:{i}", {"line": l}))
            if (l.qty or 1) > 1 and ((l.qty or 1) - 1) * it["serves"] >= n:   # one unit fewer would still be enough
                over = 0.0
                F.append(Finding("G_OVERBUY", "good", i, f"qty:{l.item_id}:{i}", {"line": l, "role": it["role"]}))
        good.update({f"soft:{i}": soft, f"onhand:{i}": onhand, f"padding:{i}": pad, f"qty:{i}": over})
        if o.vector == "repeat":
            missed = [r for r in tmpl["required"] if any(it.get("usual") and it["role"] == r for it in cat.values())
                      and roles.get(r) and not any(it.get("usual") for _, it in roles[r])]
            good[f"vec:{i}"] = 0.0 if missed else 1.0
            if missed:
                F.append(Finding("G_VECTOR", "good", i, f"vec:repeat:{i}", {"vector": "repeat"}))

        computed, stated = computed_total(o, world), o.total
        worst = max(x for x in (stated, computed, 0) if x is not None)
        if worst > budget + 1e-9:
            F.append(Finding("C_OVER_BUDGET", "correct", i, f"budget:{i}", {"total": worst}))
        if stated is None:
            F.append(Finding("A_NO_TOTAL", "accurate", i, f"total:{i}"))
        elif computed is not None and abs(stated - computed) > 0.05:
            F.append(Finding("A_TOTAL", "accurate", i, f"total:{i}", {"stated": stated, "computed": computed}))

    # cross-option goodness
    byvec = {o.vector: o for o in ans.options}
    if "fresh" in byvec and len(ans.options) > 1:
        fo = byvec["fresh"]
        pc = lambda o: sum((cat[l.item_id].get("produce", False)) for l in o.lines if l.item_id)
        best_other = max(pc(o) for o in ans.options if o is not fo)
        good[f"vec:{fo.idx}"] = 1.0 if pc(fo) > best_other else 0.0
        if pc(fo) <= best_other:
            j = max((o for o in ans.options if o is not fo), key=pc).idx
            F.append(Finding("G_VECTOR", "good", fo.idx, f"vec:fresh:{fo.idx}", {"vector": "fresh", "other": j}))
    if "savings" in byvec and len(ans.options) > 1:
        so = byvec["savings"]
        tot = lambda o: computed_total(o, world) or o.total or 1e9
        cheapest = min(ans.options, key=tot)
        ok = cheapest is so or tot(so) <= tot(cheapest)
        if ok and world.get("oracle_min_total"):
            ok = tot(so) <= 1.10 * world["oracle_min_total"]
        good[f"vec:{so.idx}"] = 1.0 if ok else 0.0
        if not ok:
            F.append(Finding("G_VECTOR", "good", so.idx, f"vec:savings:{so.idx}",
                             {"vector": "savings", "other": cheapest.idx, "other_total": tot(cheapest)}))
    sets = [(o.idx, {l.item_id or l.name for l in o.lines}) for o in ans.options]
    dist = 1.0
    for a_i, (ia, sa) in enumerate(sets):
        for ib, sb in sets[a_i + 1:]:
            if sa and sb and len(sa & sb) / len(sa | sb) >= 0.8:
                dist = 0.0
                F.append(Finding("G_DISTINCT", "good", ib, f"distinct:{ia}:{ib}", {"a": ia, "b": ib}))
    good["distinct"] = dist

    dl = deadline_minutes(brief)
    if ans.options:
        if not ans.slots:
            F.append(Finding("C_NO_SLOT", "correct", None, "slot"))
        else:
            ok = [s for s in ans.slots if minutes(s) <= dl]
            if not ok:
                F.append(Finding("C_LATE", "correct", None, "slot", {"slots": ans.slots}))
            else:
                margin = dl - min(minutes(s) for s in ok)
                good["slot_margin"] = 1.0 if margin >= SLOT_MARGIN_MIN else 0.5
                if margin < SLOT_MARGIN_MIN:
                    F.append(Finding("G_SLOT_MARGIN", "good", None, "slot_margin"))

    score = sum(good.values()) / len(good) if good else 0.0
    correct = not any(f.level == "correct" for f in F)
    accurate = not any(f.level == "accurate" for f in F)
    is_good = correct and accurate and bool(good) and score >= GOOD_MEAN and min(good.values()) >= GOOD_MIN
    return Assessment(F, good, score, correct, accurate, is_good)


# ---------------------------------------------------------------- compose
@dataclass
class Plan:
    text: str
    kind: str                       # push | isolate | reset
    keys: list
    finding: Finding | None = None


def next_level(code, done, resets_left):
    lvl = done + 1
    if code not in ISOLABLE and lvl in (3, 4):
        lvl = 5
    if lvl >= 5:
        lvl = 5 if resets_left else 2
    return lvl


def _lock_label(lk):
    return f"{_label(lk['item_ref'])} ({lk['item_ref']})"


def _q(l):
    return f'"{l.raw}"'


def _deadline_words(brief):
    t = datetime.fromisoformat(brief["deadline"]["time"])
    return t.strftime("%-I:%M %p on %A, %b %-d")


def ask_text(f, lvl, brief, world, facts):
    i = None if f.option is None else f.option + 1
    n, d, nopt = people(brief), f.d, NUM.get(brief["ask"]["options"], brief["ask"]["options"])
    cap = f"{_money(brief['budget']['max'])} or less including {' and '.join(brief['budget'].get('includes', []))}"
    if f.code in ("C_LOCK_SUB", "C_LOCK_MISSING"):
        lk = d["lock"]
        label, rule = _lock_label(lk), RULE_WORDS[lk["rule"]]
        if lvl == 4 and f.key in facts:
            return f"You confirmed {facts[f.key]}. Please put {_label(lk['item_ref'])} in option {i}: {rule}, no substitutes."
        if f.code == "C_LOCK_MISSING":
            return f"Option {i} is missing {label}. Add it ({rule}), or tell me it is out of stock."
        if lvl >= 2:
            return (f"Option {i} still has {_q(d['line'])} instead of {label}. Pick one: (a) put {_label(lk['item_ref'])} "
                    f"in option {i}, or (b) tell me it is out of stock.")
        return (f"In option {i} you listed {_q(d['line'])}. That isn't {label}. Use {_label(lk['item_ref'])}: {rule}, "
                f"no substitutes. If it's out of stock, say so; don't swap it.")
    base = {
        "C_RECIPE": f"I need products I can put in a cart, not a recipe. Please send {nopt} options as product lists.",
        "C_OPTION_COUNT": f"Please send {nopt} options; I got {NUM.get(d.get('got'), d.get('got')) if d.get('got') else 'none'}.",
        "C_HARD_EXCLUDE": f"Option {i} includes {_q(d['line']) if 'line' in d else ''}. No {d.get('value')}, in any option.",
        "C_OVER_BUDGET": f"Option {i} comes to {_money(d.get('total', 0))}. Bring it to {cap}, keeping every rule.",
        "C_NO_SLOT": f"Please list the pickup times open before {_deadline_words(brief)}, or tell me the earliest time that works.",
        "C_LATE": f"None of those pickup times is before {_deadline_words(brief)}. Is anything earlier open? If not, tell me the earliest time.",
        "C_INCOMPLETE": f"Option {i} has no {world['role_words'].get(d.get('role'), d.get('role'))}. Every option needs to be a complete taco night for {n} people.",
        "A_UNRESOLVED": f"In option {i}, which product is {_q(d['line']) if 'line' in d else ''} exactly? Please give its full product name.",
        "A_UNKNOWN": f"In option {i}, please check the {d.get('what')} of {_q(d['line']) if 'line' in d else ''}. If you still can't, keep \"unknown\".",
        "A_PRICE": f"In option {i}, I see a different price for {_q(d['line']) if 'line' in d else ''}. Please check it.",
        "A_STOCK": f"In option {i}, please check whether {_q(d['line']) if 'line' in d else ''} is really in stock for pickup.",
        "A_TOTAL": f"Option {i}'s total says {_money(d.get('stated', 0))}, but its lines come to about {_money(d.get('computed', 0))} with tax and fees. Please recheck it.",
        "A_NO_TOTAL": f"Please give the total for option {i}, including tax and fees.",
        "G_SOFT_EXCLUDE": f"Option {i} includes {_q(d['line']) if 'line' in d else ''}. We'd rather leave out {d.get('value')}; please swap it if you can.",
        "G_ON_HAND": f"Option {i} includes {_q(d['line']) if 'line' in d else ''}. We already have {d.get('value')}; please take it out.",
        "G_PADDING": f"Please take {_q(d['line']) if 'line' in d else ''} out of option {i}; it isn't part of taco night.",
        "G_OVERBUY": f"Option {i} has more than {n} people need: {_q(d['line']) if 'line' in d else ''}. Please size it for {n}.",
        "G_DISTINCT": f"Options {d.get('a', 0) + 1} and {d.get('b', 0) + 1} are almost the same. Please make them different, each true to its goal.",
        "G_SLOT_MARGIN": f"Is there a pickup time at least {SLOT_MARGIN_MIN} minutes before {_deadline_words(brief)}?",
    }
    if f.code == "C_UNMARKED_SPONSORED":
        t = f"In option {i}, {_q(d['line'])} is sponsored but not marked. Please mark sponsored items"
        return t + (", and leave it out unless it belongs in taco night." if d.get("padding") else ".")
    if f.code == "G_VECTOR":
        v = d["vector"]
        if v == "repeat":
            t = f"Option {i} should repeat what we usually buy. Please use our usual items where we have them."
        elif v == "fresh":
            t = f"Option {i} should lean on fresh produce; option {d['other'] + 1} has more right now. Please add fresh produce to option {i}."
        else:
            t = (f"Option {i} should cost the least, but option {d['other'] + 1} costs less ({_money(d['other_total'])}). "
                 f"Please make option {i} the cheapest that still follows every rule.")
    else:
        t = base[f.code]
    if lvl >= 2:
        t = f"Still open: {t} If it can't be done, tell me what stops it."
    return t


def isolate_text(f, brief, world):
    if f.code in ("C_LOCK_SUB", "C_LOCK_MISSING"):
        lk = f.d["lock"]
        subject = _lock_label(lk)
    else:
        subject = f"\"{f.d['line'].name}\""
    return (f"One separate question: is {subject} in stock for pickup by {_deadline_words(brief)}? "
            f"Please answer yes or no, and if yes, give its price.")


def fact_sentence(f, reply):
    price = _dollars(reply)
    subject = _lock_label(f.d["lock"]) if "lock" in f.d else f"\"{f.d['line'].name}\""
    return f"{subject} is in stock" + (f" at {_money(price)}" if price else "")


QUESTION_RULES = [
    (r"allerg|diet|health|medical|\bage|how old|who is|who's|\bwhy\b|condition|reason", None),
    (r"deliver", "Pickup, not delivery."),
    (r"tortilla|flour|corn", "tortilla"),
    (r"brand", "Any brand is fine, except our usuals, which must be exactly as listed."),
    (r"how many|serving|size|portion", "people"),
]


def answer_question(q, brief, world):
    low = q.lower()
    for pat, ans in QUESTION_RULES:
        if re.search(pat, low):
            if ans is None:
                return PRIVACY_REPLY
            if ans == "tortilla":
                for lk in brief.get("locks", []):
                    if world["catalog"][world["usuals"][lk["item_ref"]]]["role"] == "tortilla":
                        return f"For tortillas, use {_lock_label(lk)}: {RULE_WORDS[lk['rule']]}."
                return "Either is fine; pick what fits each option's goal."
            if ans == "people":
                return f"Enough for {people(brief)} people."
            return ans
    return "Use your judgment within the rules in my request."


def _checklist(brief, store_label):
    return render(brief, store_label=store_label).split("Before you answer, check: ")[1].split("\n")[0]


def compose(a, ans, brief, world, ladder, facts, resets_left, best, regressed, store_label=None):
    nopt = NUM.get(brief["ask"]["options"], brief["ask"]["options"])
    uniq, seen = [], set()
    for f in sorted(a.findings, key=lambda f: (LEVEL_ORDER[f.level], -1 if f.option is None else f.option, f.code)):
        if f.key not in seen:
            seen.add(f.key)
            uniq.append(f)
    top = uniq[:MAX_ASKS]
    lvls = {f.key: next_level(f.code, ladder[f.key], resets_left) for f in top}

    # The most serious open finding decides whether this turn escalates; the others wait at "pin".
    for f in top[1:]:
        if lvls[f.key] in (3, 5):
            lvls[f.key] = 2
    if top and lvls[top[0].key] == 5:
        known = [f"- {s}." for s in facts.values()]
        known += [f"- Leave out \"{f.d['line'].name}\"." for f in uniq
                  if f.code in ("C_HARD_EXCLUDE", "C_UNMARKED_SPONSORED", "G_PADDING", "G_ON_HAND", "G_SOFT_EXCLUDE") and "line" in f.d]
        text = render(brief, store_label=store_label)
        if known:
            text += "\n\nWhat we already know:\n" + "\n".join(dict.fromkeys(known))
        return Plan(guard(text), "reset", [f.key for f in uniq])
    if top and lvls[top[0].key] == 3:
        return Plan(guard(isolate_text(top[0], brief, world)), "isolate", [top[0].key], top[0])

    parts = list(dict.fromkeys(answer_question(q, brief, world) for q in ans.questions))
    flagged = {f.option for f in a.findings if f.option is not None}
    keep = [o.idx + 1 for o in sorted(best, key=lambda o: o.idx) if o.idx not in flagged]
    for o in sorted(best, key=lambda o: o.idx):
        if o.idx in regressed and o.idx not in flagged:
            names = "; ".join(f"{l.name}, {l.qty or 1}" for l in o.lines)
            parts.append(f"For option {o.idx + 1}, go back to what you sent before: {names}.")
            keep.remove(o.idx + 1)
    if keep:
        ks = " and ".join(str(k) for k in keep)
        parts.append(f"Option{'s' if len(keep) > 1 else ''} {ks} {'are' if len(keep) > 1 else 'is'} right as "
                     f"{'they are' if len(keep) > 1 else 'it is'}; send {'them' if len(keep) > 1 else 'it'} again unchanged.")
    if top:
        parts.append("Please change:\n" + "\n".join(f"- {ask_text(f, lvls[f.key], brief, world, facts)}" for f in top))
    parts.append(f"Send all {nopt} options again in the same format: one item per line as: item, quantity, price, "
                 f"in stock or not; then the total and the pickup times.")
    parts.append("Still required: " + _checklist(brief, store_label))
    return Plan(guard("\n".join(parts)), "push", [f.key for f in top])


# ---------------------------------------------------------------- loop
@dataclass
class Turn:
    n: int
    kind: str                       # brief | push | isolate | reset
    sent: str
    received: str
    summary: dict
    secs: float
    regressed: list = field(default_factory=list)

    def telemetry(self):
        return {"component_id": "K24.push_loop", "adapter_id": "H3", "loop_turn": self.n, "push_kind": self.kind,
                "codes": self.summary["codes"], "score": self.summary["score"], "regressed": self.regressed}


@dataclass
class LoopResult:
    status: str                     # GOOD | ACCEPTABLE | INFEASIBLE | FALLBACK
    options: list
    slots: list
    turns: list
    first: dict
    final: dict
    facts: dict
    open: list
    elapsed: float
    known_oos: list


def run(brief, sparky, world, store_label=None, max_turns=6, time_budget_s=180.0, max_resets=1):
    """sparky.send(text, new_conversation) -> (reply_text, seconds)."""
    text, kind = guard(render(brief, store_label=store_label)), "brief"
    ladder, facts, best, slots, turns = Counter(), {}, {}, [], []
    known_oos, elapsed, resets_left, plan, a, first = set(), 0.0, max_resets, None, None, None
    cat = world["catalog"]
    lock_upcs = {cat[world["usuals"][lk["item_ref"]]]["upc"] for lk in brief.get("locks", [])}

    for n in range(1, max_turns + 1):
        reply, secs = sparky.send(text, new_conversation=kind in ("brief", "reset"))
        elapsed += secs
        ans = parse(reply, brief, world)
        if plan is not None and plan.kind == "isolate" and ans.yes_no:
            f = plan.finding
            if ans.yes_no == "yes":
                facts[f.key] = fact_sentence(f, reply)
            elif "lock" in f.d:
                known_oos.add(cat[world["usuals"][f.d["lock"]["item_ref"]]]["upc"])
        for name in ans.oos:
            iid = resolve(name, world)
            if iid and cat[iid].get("in_stock", False) is False:   # the twin agrees (live: trust Sparky's report)
                known_oos.add(iid)
        cur = assess(ans, brief, world, frozenset(known_oos))
        regressed = []
        for o in ans.options:
            o.turn = n
            r = cur.local_rank(o.idx)
            if o.idx not in best or r <= best[o.idx][0]:
                best[o.idx] = (r, o)
            else:
                regressed.append(o.idx)
        if ans.slots:
            slots = ans.slots
        assembled = Answer([best[k][1] for k in sorted(best)], slots, [], [], ans.recipe and not best, None, "")
        a = assess(assembled, brief, world, frozenset(known_oos)) if best or ans.recipe else cur
        if first is None:
            first = cur.summary()
        turns.append(Turn(n, kind, text, reply, a.summary(), secs, regressed))

        if known_oos & lock_upcs:
            return _result("INFEASIBLE", best, slots, turns, first, a, facts, elapsed, known_oos)
        if a.is_good:
            return _result("GOOD", best, slots, turns, first, a, facts, elapsed, known_oos)
        if n == max_turns or elapsed >= time_budget_s:
            break
        plan = compose(a, ans, brief, world, ladder, facts, resets_left,
                       [best[k][1] for k in sorted(best)], set(regressed), store_label)
        for k in plan.keys:
            ladder[k] += 1
        if plan.kind == "reset":
            resets_left -= 1
        text, kind = plan.text, plan.kind

    only_unknowns = all(f.code == "A_UNKNOWN" for f in a.findings if f.level == "accurate")
    status = "ACCEPTABLE" if a and a.correct and only_unknowns and best else "FALLBACK"
    return _result(status, best, slots, turns, first, a, facts, elapsed, known_oos)


def _result(status, best, slots, turns, first, a, facts, elapsed, known_oos):
    return LoopResult(status, [best[k][1] for k in sorted(best)], slots, turns, first, a.summary(), facts,
                      [(f.code, f.option) for f in a.findings], round(elapsed, 1), sorted(known_oos))
