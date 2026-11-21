"""P02 bundle manifest: `kit bundle build` and `kit bundle diff` (Fork D's bundle-manifest-v0).

bundle_id = sha256(model_id + harness_sha + context_version); each is the sha256 of the
canonical JSON of its block. CI recomputes and fails on drift. An experiment may change
exactly one block; a release may change any.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kit_contracts.hashing import canonical_json, sha256_hex

SCHEMA = "bundle-manifest/0"
BLOCKS = {"model": "model_id", "harness": "harness_sha", "context": "context_version"}
COMPUTED = ("model_id", "harness_sha", "context_version", "bundle_id", "needs_network")


class BundleError(ValueError):
    pass


def load(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text())


def validate(m: dict[str, Any]) -> list[str]:
    errs = []
    if m.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    if m.get("kind") not in ("experiment", "release"):
        errs.append("kind must be experiment | release")
    for b in BLOCKS:
        if not isinstance(m.get(b), dict):
            errs.append(f"missing block {b}")
    lanes = (m.get("model") or {}).get("lanes") or {}
    for lane, spec in lanes.items():
        prov = spec.get("provider")
        if prov not in ("local", "frontier", "none"):  # `none` = the named deterministic fallback (F's proposal to D)
            errs.append(f"{lane}: provider {prov!r} not in local|frontier|none")
        if prov == "local" and not (spec.get("base") or {}).get("revision"):
            errs.append(f"{lane}: local lanes pin base.revision")
        gen = spec.get("gen") or {}
        if prov in ("local", "frontier") and gen.get("temperature") not in (0, 0.0):
            errs.append(f"{lane}: gen.temperature must be 0 for a pinned bundle")
    return errs


def compute(m: dict[str, Any]) -> dict[str, Any]:
    errs = validate(m)
    if errs:
        raise BundleError("; ".join(errs))
    out = {k: v for k, v in m.items() if k not in COMPUTED}
    for block, key in BLOCKS.items():
        out[key] = sha256_hex(canonical_json(m[block]))
    out["bundle_id"] = sha256_hex(out["model_id"] + out["harness_sha"] + out["context_version"])
    out["needs_network"] = any(s.get("provider") == "frontier" for s in (m["model"].get("lanes") or {}).values())
    return out


def check_drift(m: dict[str, Any]) -> list[str]:
    """CI: recompute every derived field; any stored value that differs is drift."""
    c = compute(m)
    return [k for k in COMPUTED if k in m and m[k] != c[k]]


def diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ca, cb = compute(a), compute(b)
    changed = [blk for blk, key in BLOCKS.items() if ca[key] != cb[key]]
    lanes_changed = sorted(
        lane
        for lane in set(a["model"].get("lanes", {})) | set(b["model"].get("lanes", {}))
        if a["model"].get("lanes", {}).get(lane) != b["model"].get("lanes", {}).get(lane)
    )
    return {
        "schema": "bundle-diff/0",
        "a": ca["bundle_id"],
        "b": cb["bundle_id"],
        "kind": b.get("kind"),
        "changed_blocks": changed,
        "changed_lanes": lanes_changed,
        "one_part_ok": b.get("kind") == "release" or len(changed) <= 1,
    }
