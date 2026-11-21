"""CLI: python -m discovery_engine <command>

  run     --seed N [--out DIR] [--run-id ID] [--hello-world PATH]   overnight run -> bank.json, labels.csv, run-report.json
  evals   [--seeds 1,2,3] [--out PATH]                              E18 report over seeds
  serve   --bank PATH [--port 8790] [--log PATH]                    live API (E11, E12, E14 drill) for the console
  replay0 [--out PATH]                                              run 0 replayed through the engine (parity bank)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evals import report
from .live.engine import Bank, ControlEngine
from .live.profiles import standard_set
from .live.server import serve
from .pipeline import RunConfig, label_sheet, replay_run0, run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="discovery_engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--seed", type=int, default=1); r.add_argument("--out", default="out")
    r.add_argument("--run-id", default=None); r.add_argument("--hello-world", default=None); r.add_argument("--cells", type=int, default=216)
    e = sub.add_parser("evals"); e.add_argument("--seeds", default="1,2,3"); e.add_argument("--out", default="out/eval-report.json")
    s = sub.add_parser("serve"); s.add_argument("--bank", required=True); s.add_argument("--port", type=int, default=8790)
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--log", default=None)
    z = sub.add_parser("replay0"); z.add_argument("--out", default="out/run-0-replay.json")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        bank = run(RunConfig(run_id=a.run_id or f"run-1-s{a.seed}", seed=a.seed, hello_world_result=a.hello_world, cell_budget=a.cells))
        (out / "bank.json").write_text(json.dumps(bank, indent=1, default=str))
        (out / "labels.csv").write_text(label_sheet(bank))
        print(json.dumps({"bank_id": bank["bank_id"], "families": len(bank["families"]), "hello_world": bank["hello_world"]["status"],
                          "default_top10": bank["readouts"]["default"]["top_k"]}))
    elif a.cmd == "evals":
        rep = report(tuple(int(x) for x in a.seeds.split(",")))
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(rep, indent=1, default=str))
        print(json.dumps({"pass": rep["pass"], "failed": rep["failed"], "rows": len(rep["rows"])}))
    elif a.cmd == "serve":
        profiles, params = standard_set()
        eng = ControlEngine(Bank.load(a.bank), profiles, params, log_path=a.log)
        srv = serve(eng, a.host, a.port)
        print(f"discovery-engine live API on http://{a.host}:{a.port} (bank {eng.bank.bank_id})")
        srv.serve_forever()
    elif a.cmd == "replay0":
        b = replay_run0(); Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(b, indent=1, default=str))
        print(json.dumps({"bank_id": b["bank_id"], "families": len(b["families"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
