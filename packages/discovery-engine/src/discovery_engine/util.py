"""Shared helpers: canonical hashing, YAML/JSON loading, and number labels.

Number labels (engine guardrail "zero unlabeled numbers"):
  synthetic            an assumption or a synthetic-world value
  public:<src>         taken from a public source; <src> is a ref key (fork-c REFS) or a registry id (ST-###)
  derived:synthetic    computed from inputs at least one of which is synthetic
  derived:public       computed only from public inputs
  score:<version>      a rubric score or criterion value (e.g. score:rubric@2)
  weight:<version>     a control weight (e.g. weight:controls@2-fixture)
Anything numeric in a bank family's sizing block or in a Readout@0 must be a {"value", "label"} object.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

PKG_ROOT = Path(__file__).resolve().parents[2]          # packages/discovery-engine
PROTO_C = PKG_ROOT / "prototypes" / "fork_c"
FIXTURES = PKG_ROOT / "fixtures"

LABEL_RX = re.compile(r"^(synthetic|public:[A-Za-z0-9_\-]+|derived:(synthetic|public)|score:[\w@.\-]+|weight:[\w@.\-]+)$")


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def sha256_hex(obj: Any) -> str:
    data = obj if isinstance(obj, (bytes, bytearray)) else canonical(obj)
    return hashlib.sha256(data).hexdigest()


def load_yaml(path: Path | str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_json(path: Path | str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def L(value: float | int, label: str) -> dict:
    """A labeled number. Refuses unknown labels so a typo never ships an unlabeled number."""
    if not LABEL_RX.match(label):
        raise ValueError(f"bad number label: {label!r}")
    return {"value": value, "label": label}


def src_label(tag: str) -> str:
    """Map C's input tags onto labels: 'S:<ref>' -> public:<ref>; 'A' and 'A:<note>' -> synthetic."""
    if tag.startswith("S:"):
        return "public:" + tag[2:]
    return "synthetic"


def derived(*labels: str) -> str:
    return "derived:public" if labels and all(l.startswith("public:") or l == "derived:public" for l in labels) else "derived:synthetic"


def find_unlabeled(obj: Any, path: str = "", allow: frozenset = frozenset()) -> list[str]:
    """Paths of bare numbers. A number is fine inside {"value": n, "label": <valid>} or under an allowed key."""
    out: list[str] = []
    if isinstance(obj, dict):
        if set(obj) >= {"value", "label"} and isinstance(obj.get("value"), (int, float)):
            if not (isinstance(obj["label"], str) and LABEL_RX.match(obj["label"])):
                out.append(path + ".label")
            return out
        for k, v in obj.items():
            if k in allow:
                continue
            out += find_unlabeled(v, f"{path}.{k}", allow)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += find_unlabeled(v, f"{path}[{i}]", allow)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append(path)
    return out


def clean_axis(values: list) -> list[str]:
    """Lattice lists carry parenthetical notes with commas ('keep_a_routine (pet, shift, observance)'), which YAML
    flow syntax splits into several items. Re-join the pieces, then drop the note."""
    out, buf = [], None
    for raw in values:
        s = str(raw).strip()
        if buf is not None:
            buf += ", " + s
            if ")" in s:
                out.append(buf); buf = None
            continue
        if "(" in s and ")" not in s:
            buf = s
            continue
        out.append(s)
    if buf is not None:
        out.append(buf)
    return [re.sub(r"\s*\(.*\)\s*$", "", s).strip() for s in out]
