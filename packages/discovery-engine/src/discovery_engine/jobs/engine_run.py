"""`engine-run` — Fork D's Kit Fleet job kind (job-kinds-v0), the overnight half of the engine as an installed command.

Command contract (job-kinds-v0 `common.command_contract`):
  stdin : {"job": <claimed job>, "outDir": <folder>}
  writes: <job.key>.<job.fence>.jsonl in outDir   (one record per line: header, families, readouts, eval report)
  stdout: {"file": "<key>.<fence>.jsonl", "sha256": "<64 hex>"}
  exit  : 0 on success; nonzero with an error-code line otherwise
Refusals (before any work): params outside the lane's fixed values (temperature), credential-shaped fields, the
holdout seed, a teacher that is not local or names a frontier model (D-ADR-003), a missing hello-world input when
params.require_live_hello_world is true. Network: none (night kind); the only socket is the local teacher, if pinned.
Pass (job-kinds-v0 engine-run): hello world passed (placement or live), zero unlabeled numbers, guardrail evals.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from ..evals import no_diagnoses, stereotype_counterfactual, unlabeled
from ..live.engine import Bank, ControlEngine
from ..live.profiles import standard_set
from ..pipeline import RunConfig, run
from ..stages.e04_cards import FIXED_TEMPERATURE, TeacherRefused, check_local

CRED_RX = re.compile(r"(api[_-]?key|token|secret|password|bearer|authorization|credential)", re.I)
ALLOWED_PARAMS = {"seeds", "lens", "control_profiles", "model_pins", "cell_budget", "n_per_cell", "profiles_source",
                  "temperature", "require_live_hello_world", "holdout_commitment", "run_id"}


class Refused(Exception):
    code = "REFUSED"


def _walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from _walk_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{path}[{i}]")


def check_params(job: dict) -> dict:
    p = job.get("params", {})
    for path, k in _walk_keys(job):
        if CRED_RX.search(k):
            raise Refused(f"credential-shaped field refused: {path}")
    extra = set(p) - ALLOWED_PARAMS
    if extra:
        raise Refused(f"unknown params: {sorted(extra)}")
    if p.get("temperature", FIXED_TEMPERATURE) != FIXED_TEMPERATURE:
        raise Refused("generation settings outside the lane's fixed values (temperature)")
    hold = p.get("holdout_commitment")
    for s in p.get("seeds", [1]):
        if hold and hashlib.sha256(str(s).encode()).hexdigest() == hold:
            raise Refused("holdout seed refused (engine-run is not bundle-eval)")
    teacher = (p.get("model_pins") or {}).get("E04")
    if teacher:
        try:
            check_local(teacher["endpoint"], teacher["model"])
        except (TeacherRefused, KeyError) as e:
            raise Refused(f"E04 teacher refused: {e}")
    return p


def execute(job: dict, out_dir: str) -> dict:
    p = check_params(job)
    hw = (job.get("payload") or {}).get("hello_world_result")      # host-local path to a passing bundle-eval result
    if p.get("require_live_hello_world") and not hw:
        raise Refused("engine-run requires a passing hello-world bundle-eval result")
    teacher = (p.get("model_pins") or {}).get("E04")
    profiles, params = standard_set(p.get("profiles_source", "priors"))
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    name = f"{job['key']}.{job['fence']}.jsonl"
    records, verdict = [], {"hello_world": None, "unlabeled_numbers": None, "guardrails": None}
    for s in p.get("seeds", [1]):
        cfg = RunConfig(run_id=p.get("run_id", f"{job['key']}-s{s}"), seed=int(s), hello_world_result=hw, teacher=teacher,
                        cell_budget=p.get("cell_budget", 216), n_per_cell=p.get("n_per_cell", 3),
                        profiles_source=p.get("profiles_source", "priors"))
        bank = run(cfg)
        eng = ControlEngine(Bank(bank), profiles, params)
        g = [stereotype_counterfactual(bank), no_diagnoses(bank)]
        u = unlabeled(bank, eng, profiles)
        verdict = {"hello_world": bank["hello_world"]["status"], "unlabeled_numbers": u["value"],
                   "guardrails": all(r["pass"] for r in g)}
        records.append({"type": "header", "run_id": bank["run_id"], "seed": s, "bank_id": bank["bank_id"],
                        **{k: bank[k] for k in ("versions", "generator", "fallback_used", "judge", "hello_world", "hypotheses", "coverage", "cut")}})
        records += [{"type": "family", "bank_id": bank["bank_id"], **f} for f in bank["families"]]
        records.append({"type": "readouts", "bank_id": bank["bank_id"], "readouts": bank["readouts"]})
        records.append({"type": "checks", "bank_id": bank["bank_id"], "rows": g + [u], "verdict": verdict})
        if u["value"] != 0 or not verdict["guardrails"]:
            raise Refused(f"pass criteria failed: {verdict}")
    path = out / name
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    return {"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> int:
    try:
        req = json.loads(sys.stdin.read())
        res = execute(req["job"], req["outDir"])
    except Refused as e:
        print(f"error REFUSED {e}", file=sys.stderr); return 3
    except Exception as e:   # keys, kinds and error codes only in logs
        print(f"error ENGINE_RUN_FAILED {type(e).__name__}", file=sys.stderr); return 2
    print(json.dumps(res)); return 0


if __name__ == "__main__":
    sys.exit(main())
