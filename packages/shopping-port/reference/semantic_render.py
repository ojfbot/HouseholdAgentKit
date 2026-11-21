"""semantic@1: render Brief@1 as text a structure-blind reader (Sparky) can act on.

Deterministic. Every hard constraint is stated in words, twice (goal or Must list, and the closing check).
Opaque refs always travel with a plain-language label. Optional JSON appendix last, never instead.
"""
from datetime import datetime
import json

VECTOR_WORDS = {"savings": "costs the least", "delight": "is the most fun to eat", "repeat": "repeats what we usually buy",
                "festive": "feels like a party", "fresh": "leans on fresh produce", "healthy": "is the lightest",
                "low_waste": "leaves the fewest leftovers", "speed": "is fastest to put on the table"}
RULE_WORDS = {"brand_only": "same brand, any size", "exact_item": "the same product", "exact_item_and_packaging": "the same product in the same package"}
DEADLINE_WORDS = {"pickup_ready_by": "bagged and ready for pickup", "deliver_by": "delivered", "deliver_window": "delivered"}
NUM = {1: "one", 2: "two", 3: "three", 4: "four"}

def _label(ref):        # usual:tortilla#a1 -> "our usual tortilla"; role token only, never a reason
    role = ref.split(":", 1)[-1].split("#")[0].replace("_", " ")
    return f"our usual {role}"

def _when(iso):
    t = datetime.fromisoformat(iso)
    return t.strftime("%-I:%M %p on %A, %b %-d").replace(":00 ", " ") , t

def _money(x): return f"${x:,.2f}"

def render(b, store_label=None, include_json=False):
    hc, dl, bud, ask = b["headcount"], b["deadline"], b["budget"], b["ask"]
    people = f"{hc['adults'] + hc['kids']} people ({hc['adults']} adults, {hc['kids']} kids)" if hc.get("kids") else f"{hc['adults']} adults"
    when, _ = _when(dl["time"])
    store = f"{store_label} (store {dl['store']})" if store_label else f"store {dl['store']}"
    occasion = b["occasion"].replace("_", " ")
    incl = " and ".join(bud.get("includes", []))
    total_rule = f"{_money(bud['max'])} or less{' including ' + incl if incl else ''}"
    hard_ex = [e for e in b.get("exclude", []) if e.get("hard")]
    soft_ex = [e for e in b.get("exclude", []) if not e.get("hard")]
    locks = b.get("locks", [])

    goal = (f"I'm an assistant shopping for a customer. I need products I can put in a cart, not recipes. "
            f"Goal: everything for {occasion} for {people}, {DEADLINE_WORDS[dl['type']]} at {store} by {when}. "
            f"That is the {'pickup' if dl['type']=='pickup_ready_by' else 'delivery'} time, not a cooking time. "
            f"The whole order must total {total_rule}.")
    must = [f"{DEADLINE_WORDS[dl['type']].capitalize()} by {when}, or tell me the earliest time that works.",
            f"Total {total_rule}{'' if bud.get('hard') else ' if possible'}. Show each item's price and the total."]
    for l in locks:
        must.append(f"Use {_label(l['item_ref'])} ({l['item_ref']}): {RULE_WORDS[l['rule']]}, no substitutes.")
    if locks:
        must.append("If an item above is out of stock, tell me; don't swap it.")
    for e in hard_ex:
        must.append(f"No {e['value']}" + (", including products that may contain it." if e['kind'] == 'allergen' else "."))
    prefer = [f"Leave out {e['value']} if you can." for e in soft_ex]
    if b.get("on_hand"):
        oh = [x.replace('_', ' ') for x in b['on_hand']]
        prefer.append(f"Skip {', '.join(oh[:-1]) + ' and ' + oh[-1] if len(oh) > 1 else oh[0]}: we already have {'it' if len(oh) == 1 else 'them'}.")
    vecs = ask["vectors"]
    opts = "; ".join(f"one that {VECTOR_WORDS[v]}" for v in vecs)
    back = (f"Please send back {NUM.get(ask['options'], ask['options'])} complete options: {opts}. "
            f"For each option, list one item per line as: item, quantity, price, in stock or not. Then the total"
            f"{' and the pickup times open before the deadline' if 'slot_options' in ask.get('include', []) else ''}. "
            f"If you don't know a price or stock level, write \"unknown\" rather than guessing. Mark any sponsored item and any substitute.")
    check = [f"total {total_rule}", f"{'ready' if dl['type']=='pickup_ready_by' else 'delivered'} by {when}"]
    check += [f"{_label(l['item_ref'])} not substituted" for l in locks]
    check += [f"no {e['value']}" for e in hard_ex]
    check.append(f"{NUM.get(ask['options'], ask['options'])} options")
    parts = [goal, "Must:\n" + "\n".join(f"- {m}" for m in must)]
    if prefer: parts.append("Prefer:\n" + "\n".join(f"- {p}" for p in prefer))
    parts += [back, "Before you answer, check: " + " · ".join(check) + "."]
    if include_json:
        parts.append("The same request as data, in case it helps:\n```json\n" + json.dumps(b, separators=(",", ":")) + "\n```")
    return "\n\n".join(parts)
