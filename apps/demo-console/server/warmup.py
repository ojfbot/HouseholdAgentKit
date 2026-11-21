"""D06 warm-up: run on the stage host after `host.py` starts, before doors open. Exit 0 = ready.

Checks, in the order they would bite on stage:
  host answers · every fixture and card passes its contract · each beat's recording is present and matches
  its sha256 · QR renders for the hotspot URL · speech-to-text engine (or the typed fallback is the plan) ·
  live ports reachable when configured (engine, poll bus, K11 model) · time from host start to ready.
Usage: python3 server/warmup.py [--url http://127.0.0.1:8765] [--strict]
  --strict fails on missing recordings and on fixture mode (use from Nov 30).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.request

APP = pathlib.Path(__file__).resolve().parents[1]


def get(url, timeout=2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    rows, blockers = [], 0

    def row(ok, name, detail="", blocker=True):
        nonlocal blockers
        rows.append(("ok " if ok else ("ERR" if blocker else "warn"), name, detail))
        if not ok and blocker:
            blockers += 1

    try:
        _, body = get(a.url + "/api/health")
        health = json.loads(body)
        row(True, "host", f"{health['engine']} · {health['cards']}")
    except Exception as exc:
        row(False, "host", str(exc))
        print_rows(rows, t0)
        return 2

    state = json.loads(get(a.url + "/api/state")[1])
    for b, src in state["sources"].items():
        row(src != "fixture" or not a.strict, f"beat {b} source", src, blocker=a.strict)

    sys.path.insert(0, str(APP.parents[1] / "packages" / "card-writer"))
    sys.path.insert(0, str(APP / "server"))
    from card_writer import check_card
    from contracts import check_view
    try:
        for c in [state["hello"]["menu"], state["care"]["profile_card"]]:
            check_card(c)
        check_view(state["engine"]["readout"])
        row(True, "contracts", "cards guarded, readout valid")
    except Exception as exc:
        row(False, "contracts", str(exc))

    man = json.loads((APP / "recordings" / "manifest.json").read_text())["beats"]
    for beat, m in man.items():
        f = APP / "recordings" / m["file"]
        if not f.is_file():
            row(False, f"recording {beat}", f"{m['file']} not captured (Nov 30)", blocker=a.strict)
            continue
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        ok = m.get("sha256") in (None, sha)
        row(ok, f"recording {beat}", f"{m['file']} {f.stat().st_size // 1024} KiB" + ("" if ok else " sha256 MISMATCH"))
        try:
            get(f"{a.url}/recordings/{m['file']}", timeout=5)  # warm the OS file cache
        except Exception:
            pass

    try:
        code, body = get(a.url + "/api/qr.svg")
        row(code == 200 and body.startswith(b"<?xml") or b"<svg" in body[:200], "qr", state["join_url"])
    except Exception as exc:
        row(False, "qr", f"{exc}: show {state['join_url']} as text", blocker=False)
    if "127.0.0.1" in state["join_url"] or "localhost" in state["join_url"]:
        row(False, "join url", "points at localhost: set public_url to the stage host's hotspot address", blocker=a.strict)

    stt = health["stt"]
    row(stt["available"], "speech-to-text", stt["engine"] or "none: typed fallback and the clip carry Ruth's request", blocker=False)

    cfg_path = APP / "console.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.is_file() else {}
    mode = cfg.get("mode", {})
    for key, url_key, path in (("engine", "engine_url", "/readout"), ("poll", "poll_bus_url", "/health")):
        if mode.get(key) == "http":
            try:
                get(cfg[url_key].rstrip("/") + path, timeout=1.0)
                row(True, f"{key} port", cfg[url_key])
            except Exception as exc:
                row(False, f"{key} port", f"{cfg.get(url_key)}: {exc}")
    if mode.get("cards") == "model":
        try:
            get(cfg["model_url"].rstrip("/") + "/v1/models", timeout=1.0)
            row(True, "K11 model", cfg["model_url"])
        except Exception as exc:
            row(False, "K11 model", f"{exc}: templates will answer (fallback_used)", blocker=False)

    print_rows(rows, t0)
    return 1 if blockers else 0


def print_rows(rows, t0):
    for status, name, detail in rows:
        print(f"[{status:4}] {name:18} {detail}")
    print(f"warm-up checks took {time.time() - t0:.1f} s")


if __name__ == "__main__":
    sys.exit(main())
