"""Live engine API for the demo console (E19, D01; Fork H renders, never computes). Stdlib only, offline on the stage host.

  GET  /health                       -> {"ok", "bank_id", "families"}
  GET  /bank                         -> bank metadata (run, versions, hello world, hypotheses, coverage); no family text
  GET  /profiles                     -> profile ids, lens, function
  GET  /readout?profile=<id>&session=<s>  -> Readout@0 for the session's current state (default: base profile)
  POST /delta  {ControlDelta request}      -> {"event": ControlDelta@0, "readout": Readout@0}
  GET  /family/<id>                  -> drill: ladder, evidence, sizing driver tree, components (E14), partner fit
  GET  /log?session=<s>              -> the session's ControlDelta@0 events (hash-chained); /log/verify -> chain check
Request shape for /delta: {"op": "set|scale|reset|lens|scenario|switch", "path": ["segment","shopper"], "value": 2.0,
  "profile_id": "marketing_crm", "session": "stage", "actor": {"role": "EL"}, "reason": "..."}
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .engine import ControlEngine

META_KEYS = ("contract", "run_id", "seed", "bank_id", "versions", "controls_source", "generator", "fallback_used", "judge",
             "hello_world", "coverage", "dedupe", "cut", "hypotheses", "novel_families", "unreached_seed_families")


def make_handler(eng: ControlEngine):
    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body):
            data = json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-headers", "content-type")
            self.send_header("content-length", str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def log_message(self, *a):   # keys and counts only (job-kinds-v0 logs rule); no bodies
            pass

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
            sid = q.get("session", "stage")
            if u.path == "/health":
                return self._send(200, {"ok": True, "bank_id": eng.bank.bank_id, "families": len(eng.bank.families)})
            if u.path == "/bank":
                return self._send(200, {k: eng.bank.data.get(k) for k in META_KEYS})
            if u.path == "/profiles":
                return self._send(200, [{"profile_id": k, "lens": p["lens"], "function": p["function"], "source": p["source"]}
                                        for k, p in eng.profiles.items()])
            if u.path == "/readout":
                pid = q.get("profile")
                if pid and pid not in eng.profiles:
                    return self._send(404, {"error": "unknown profile"})
                if pid and (sid not in eng.sessions or eng.sessions[sid]["base"] != pid):
                    eng.sessions.pop(sid, None)
                s = eng.session(sid, pid or "default")
                return self._send(200, eng.readout(s["profile"], s["base"], s["deltas"]))
            if u.path.startswith("/family/"):
                fid = u.path.split("/", 2)[2]
                return self._send(200, eng.drill(fid)) if fid in eng.bank.by_id else self._send(404, {"error": "unknown family"})
            if u.path == "/log":
                return self._send(200, [e for e in eng.events if e["session"] == sid])
            if u.path == "/log/verify":
                return self._send(200, {"chain_ok": eng.verify_chain(), "events": len(eng.events)})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            u = urlparse(self.path)
            if u.path != "/delta":
                return self._send(404, {"error": "not found"})
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "bad json"})
            if req.get("profile_id") and req["profile_id"] not in eng.profiles:
                return self._send(404, {"error": "unknown profile"})
            ev, ro = eng.apply(req, req.get("session", "stage"))
            return self._send(200 if ev["status"] != "rejected" else 422, {"event": ev, "readout": ro})
    return H


def serve(eng: ControlEngine, host: str = "127.0.0.1", port: int = 8790) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(eng))
    return srv
