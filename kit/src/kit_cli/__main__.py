"""kit doctor | kit eval hello-world | kit conformance | kit mutate | kit bundle build|diff | kit gate |
kit review status | kit merge-queue plan | kit digest

Exit codes: 0 green / pass; 1 red / fail (with the reason printed); 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


def _write(obj: Any, out: str | None) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n")
    else:
        print(text)


def cmd_eval(a: argparse.Namespace) -> int:
    from kit_eval.cases import load_cases
    from kit_eval.report import build_report, load_hook, run_hello_world

    cases = load_cases(a.cases)
    hook = load_hook(a.hook)
    res = run_hello_world(hook, cases, k=a.k, seed=a.seed)
    rep = build_report(res, cases, bundle_id=a.bundle_id, hook_name=hook.name, k=a.k)
    _write(rep, a.out)
    m = rep["metrics"]
    print(
        f"hello-world [{hook.name}] pass^{a.k}={m['pass_k']['value']:.3f} tier0={m['tier0_parity_rate']['value']:.3f} "
        f"tier1={m['tier1_rate']['value']:.3f} tier2={m['tier2_rate']['value']:.3f} locks={m['locks']['value']:.0f}",
        file=sys.stderr,
    )
    return 0 if m["pass_k"]["value"] == 1.0 else 1


def cmd_hello_world(a: argparse.Namespace) -> int:
    """Fork A's hook CLI (hw-taco@1): kit hello-world --mode smoke|full|live|blind --bundle <id> [--k] [--seed-base]."""
    from kit_eval import hello_world
    from kit_eval.report import load_hook

    res = hello_world.run(a.mode, a.bundle, k=a.k, seed_base=a.seed_base, hook=load_hook(a.hook))
    _write(res, a.out)
    print(f"hello-world {a.mode}: status={res['status']} highest_tier={res.get('highest_tier')} zero_tolerance={res.get('zero_tolerance')}", file=sys.stderr)
    zt = res.get("zero_tolerance") or {}
    broken = any(v for name, v in zt.items() if name != "orders_per_mandate_max") or zt.get("orders_per_mandate_max", 0) > 1
    return 0 if res["status"] in ("pass", "placement_only") and not broken else 1


def cmd_conformance(a: argparse.Namespace) -> int:
    from kit_eval.conformance import run_all, summary

    s = summary(run_all())
    _write(s, a.out)
    print(f"conformance {s['passed']}/{s['ran']} (skipped {len(s['skipped'])} core checks)", file=sys.stderr)
    return 0 if s["passed"] == s["ran"] else 1


def cmd_mutate(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
    from kit_verifier.mutations import run_mutation_suite
    from mutation.test_verifier_mutations import _bases

    r = run_mutation_suite(_bases())
    _write(r.as_dict(), a.out)
    print(f"mutation kill rate {r.kill_rate:.3f} over {r.total_applied} mutants; false alarms {len(r.clean_false_alarms)}", file=sys.stderr)
    return 0 if r.kill_rate == 1.0 and not r.clean_false_alarms and not r.never_applied() and not r.wrong_reasons() else 1


def cmd_bundle(a: argparse.Namespace) -> int:
    from kit_gate import bundle

    if a.action == "build":
        _write(bundle.compute(bundle.load(a.manifest)), a.out)
        return 0
    if a.action == "check":
        drift = bundle.check_drift(bundle.load(a.manifest))
        print("drift: " + (", ".join(drift) if drift else "none"), file=sys.stderr)
        return 1 if drift else 0
    d = bundle.diff(bundle.load(a.manifest), bundle.load(a.other))
    _write(d, a.out)
    return 0 if d["one_part_ok"] else 1


def cmd_gate(a: argparse.Namespace) -> int:
    from kit_gate.gate import GateConfig, run_gate

    cand = json.loads(Path(a.candidate).read_text())
    base = json.loads(Path(a.baseline).read_text()) if a.baseline else None
    diff = json.loads(Path(a.diff).read_text()) if a.diff else None
    rec = run_gate(cand, base, diff, GateConfig.load(a.config), today=date.fromisoformat(a.today) if a.today else None)
    _write(rec, a.out)
    print(f"kit gate: {rec['verdict'].upper()}" + ("" if rec["verdict"] == "green" else f" — {rec['reasons']}"), file=sys.stderr)
    return 0 if rec["verdict"] == "green" else 1


def cmd_review(a: argparse.Namespace) -> int:
    from kit_gate import review

    pr = json.loads(Path(a.pr_json).read_text())
    st, why = review.status(pr)
    _write({"state": st, "description": why}, a.out)
    return 0 if st == "success" else 1


def cmd_queue(a: argparse.Namespace) -> int:
    from kit_gate.merge_queue import plan

    prs = json.loads(Path(a.prs).read_text())
    gates = json.loads(Path(a.gates).read_text()) if a.gates else {}
    _write([d.__dict__ for d in plan(prs, gates)], a.out)
    return 0


def cmd_digest(a: argparse.Namespace) -> int:
    from kit_gate import digest
    from kit_gate.merge_queue import Decision

    d = json.loads(Path(a.input).read_text())
    md = digest.render(
        date.fromisoformat(d["day"]),
        [Decision(**x) for x in d.get("decisions", [])],
        d.get("gate"),
        d.get("merged_since", []),
        d.get("queue_items", []),
        d.get("eval_cases_added", []),
        [tuple(x) for x in d.get("milestones", [])],
        d.get("notes", []),
    )
    if a.out:
        Path(a.out).write_text(md)
    else:
        print(md)
    return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    """kit doctor [--rung N] [--self-test]: one plain status line per rung of the integration ladder."""
    from kit_cli import doctor

    if a.self_test:
        return doctor.self_test()
    return doctor.run(upto=a.rung, today=date.fromisoformat(a.today) if a.today else None, as_json=a.json)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kit")
    sub = p.add_subparsers(dest="cmd", required=True)

    dr = sub.add_parser("doctor")
    dr.add_argument("--rung", type=int, default=2, help="check rungs 0..N (default 2)")
    dr.add_argument("--self-test", action="store_true", help="prove every check: red on each planted break, green on a working setup")
    dr.add_argument("--today", help="ISO date, for the date lines")
    dr.add_argument("--json", action="store_true")
    dr.set_defaults(fn=cmd_doctor)

    e = sub.add_parser("eval")
    e.add_argument("suite", choices=["hello-world"])
    e.add_argument("--cases", default="data/seeds/cases")
    e.add_argument("--hook", default=None, help="module:attr of a HelloWorldHook (default: IQ reference, tier none)")
    e.add_argument("--k", type=int, default=5)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--bundle-id", default="unpinned")
    e.add_argument("--out")
    e.set_defaults(fn=cmd_eval)

    h = sub.add_parser("hello-world")
    h.add_argument("--mode", choices=["smoke", "full", "live", "blind"], default="smoke")
    h.add_argument("--bundle", default="unpinned")
    h.add_argument("--k", type=int, default=None)
    h.add_argument("--seed-base", type=int, default=0)
    h.add_argument("--hook", default=None)
    h.add_argument("--out")
    h.set_defaults(fn=cmd_hello_world)

    c = sub.add_parser("conformance")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_conformance)

    mu = sub.add_parser("mutate")
    mu.add_argument("--out")
    mu.set_defaults(fn=cmd_mutate)

    b = sub.add_parser("bundle")
    b.add_argument("action", choices=["build", "check", "diff"])
    b.add_argument("manifest")
    b.add_argument("other", nargs="?")
    b.add_argument("--out")
    b.set_defaults(fn=cmd_bundle)

    g = sub.add_parser("gate")
    g.add_argument("--candidate", required=True)
    g.add_argument("--baseline")
    g.add_argument("--diff")
    g.add_argument("--config", default="bundles/gate-config.yaml")
    g.add_argument("--today")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_gate)

    r = sub.add_parser("review")
    r.add_argument("action", choices=["status"])
    r.add_argument("pr_json")
    r.add_argument("--out")
    r.set_defaults(fn=cmd_review)

    q = sub.add_parser("merge-queue")
    q.add_argument("action", choices=["plan"])
    q.add_argument("--prs", required=True)
    q.add_argument("--gates")
    q.add_argument("--out")
    q.set_defaults(fn=cmd_queue)

    d = sub.add_parser("digest")
    d.add_argument("--input", required=True)
    d.add_argument("--out")
    d.set_defaults(fn=cmd_digest)

    a = p.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    sys.exit(main())
