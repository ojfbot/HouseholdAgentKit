"""K11 role-scoped card writer.

Seam (components@2): CardWriter.write(claims, audience) -> Card@0. Kind, facts and locale ride as keywords.

Input  = CardInput  {kind, audience: MemberRef, claims: [Card@0 claim], facts: {words only}, locale}
Output = Card@0     {card_id, audience, kind, headline*, sections, actions*, claims, locale, a11y}
         (* = additive draft fields proposed by Fork H for the Nov 22 freeze; see README)

Two writers share one contract:
- TemplateCardWriter: deterministic, tier `none`, always available.
- ModelCardWriter: a local model (P01, OpenAI-compatible, JSON Schema) rewrites the *words* of the template
  draft for the audience. It returns sections with `{c:<id>}` placeholders; this module fills every number,
  so the model cannot type one. Any schema, guard or transport failure falls back to the template,
  and the result says so (fallback_used). This is the second fine-tune target's seam (R3.1 option A).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import urllib.request
from typing import Protocol

from .format import render_value
from .guard import CardRejected, check_card
from .readability import grade
from .templates import TEMPLATES

PLACEHOLDER = re.compile(r"\{c:([A-Za-z0-9_.:-]+)\}")


def _card_id(kind: str, audience: dict, claims: list, facts: dict) -> str:
    blob = json.dumps({"k": kind, "a": audience, "c": claims, "f": facts}, sort_keys=True, separators=(",", ":"))
    return "card_" + hashlib.sha256(blob.encode()).hexdigest()[:12]


def assemble(draft: dict, *, kind: str, audience: dict, claims: list, facts: dict, locale: str) -> dict:
    """Fill placeholders, set claim_ref, keep only the claims this card shows, compute a11y."""
    by_id = {c["id"]: c for c in claims}
    sections, used, texts = [], [], []
    for s in draft["sections"]:
        lines = []
        for line in s["lines"]:
            refs = PLACEHOLDER.findall(line["text"])
            if len(refs) > 1:
                raise CardRejected("SCHEMA", f"more than one number on a line: {line['text']}")
            out = {"text": line["text"]}
            if refs:
                ref = refs[0]
                if ref not in by_id:
                    raise CardRejected("UNVERIFIED_CLAIM", f"placeholder for unknown claim {ref}")
                out["text"] = PLACEHOLDER.sub(render_value(by_id[ref]["value"]), line["text"])
                out["claim_ref"] = ref
                if ref not in used:
                    used.append(ref)
            if line.get("mark"):
                out["mark"] = line["mark"]
            lines.append(out)
            texts.append(out["text"])
        sec = {"title": s["title"], "lines": lines}
        if s.get("option"):
            sec["option"] = s["option"]
        sections.append(sec)
    shown = [copy.deepcopy(by_id[i]) for i in used]
    card = {
        "card_id": _card_id(kind, audience, shown, facts),
        "audience": audience,
        "kind": kind,
        "headline": draft.get("headline", ""),
        "sections": sections,
        "actions": draft.get("actions", []),
        "claims": shown,
        "locale": locale,
        "a11y": {"contrast": "AA", "reading_level": grade(texts + [draft.get("headline", "")])},
    }
    check_card(card)
    return card


class CardWriter(Protocol):
    def write(self, claims: list, audience: dict, *, kind: str, facts: dict, locale: str = "en-US") -> dict: ...


class TemplateCardWriter:
    adapter_id = "k11.template@0"

    def draft(self, *, kind: str, audience: dict, facts: dict) -> dict:
        if kind not in TEMPLATES:
            raise CardRejected("SCHEMA", f"no template for kind {kind}")
        return TEMPLATES[kind](audience, facts)

    def write(self, claims, audience, *, kind, facts, locale="en-US"):
        return assemble(self.draft(kind=kind, audience=audience, facts=facts), kind=kind, audience=audience,
                        claims=claims, facts=facts, locale=locale)


class ModelPort(Protocol):
    def structured(self, *, schema: dict, messages: list) -> dict: ...


class OpenAICompatPort:
    """P01: local MLX serving behind an OpenAI-compatible endpoint with fail-closed JSON Schema decoding."""

    def __init__(self, base_url: str, model: str, timeout_s: float = 2.5):
        self.base_url, self.model, self.timeout_s = base_url.rstrip("/"), model, timeout_s

    def structured(self, *, schema, messages):
        body = json.dumps({
            "model": self.model, "temperature": 0, "messages": messages,
            "response_format": {"type": "json_schema", "json_schema": {"name": "card_draft", "schema": schema, "strict": True}},
        }).encode()
        req = urllib.request.Request(self.base_url + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
            payload = json.load(r)
        return json.loads(payload["choices"][0]["message"]["content"])


DRAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "sections"],
    "properties": {
        "headline": {"type": "string", "maxLength": 80},
        "sections": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["title", "lines"],
            "properties": {
                "title": {"type": "string", "maxLength": 60},
                "lines": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["text"],
                    "properties": {"text": {"type": "string", "maxLength": 120}, "mark": {"type": "string"}}}},
            }}},
    },
}

SYSTEM = (
    "You write one role-scoped card for a household shopping agent. Rewrite the draft's words for the reader "
    "named in audience.role: plain words, short lines, dignified for older readers, simple for kids. "
    "Keep every {c:<id>} placeholder exactly as written, at most one per line, and never write a digit "
    "outside a placeholder. Do not add facts. Keep section order and section count."
)


class ModelCardWriter:
    adapter_id = "k11.model@0"

    def __init__(self, port: ModelPort, fallback: TemplateCardWriter | None = None):
        self.port = port
        self.fallback = fallback or TemplateCardWriter()
        self.last_fallback_reason: str | None = None

    def write(self, claims, audience, *, kind, facts, locale="en-US"):
        template_draft = self.fallback.draft(kind=kind, audience=audience, facts=facts)
        self.last_fallback_reason = None
        try:
            words = self.port.structured(schema=DRAFT_SCHEMA, messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps({"audience": audience, "kind": kind, "locale": locale,
                                                        "draft": {"headline": template_draft["headline"], "sections": [
                                                            {"title": s["title"], "lines": [{k: v for k, v in l.items() if k in ("text", "mark")} for l in s["lines"]]}
                                                            for s in template_draft["sections"]]}})},
            ])
            if len(words["sections"]) != len(template_draft["sections"]):
                raise CardRejected("SCHEMA", "model changed the section count")
            draft = {"headline": words["headline"], "actions": template_draft["actions"], "sections": []}
            for got, want in zip(words["sections"], template_draft["sections"]):
                want_refs = sorted(r for l in want["lines"] for r in PLACEHOLDER.findall(l["text"]))
                got_refs = sorted(r for l in got["lines"] for r in PLACEHOLDER.findall(l["text"]))
                if want_refs != got_refs:
                    raise CardRejected("UNVERIFIED_CLAIM", "model dropped or added a number")
                sec = {"title": got["title"], "lines": got["lines"]}
                if want.get("option"):
                    sec["option"] = want["option"]
                draft["sections"].append(sec)
            return assemble(draft, kind=kind, audience=audience, claims=claims, facts=facts, locale=locale)
        except Exception as exc:  # transport, schema or guard: the template answers instead
            self.last_fallback_reason = f"{type(exc).__name__}: {exc}"
            return self.fallback.write(claims, audience, kind=kind, facts=facts, locale=locale)


def write_card(writer, card_input: dict, *, trace: str | None = None) -> dict:
    """Result@0 envelope around a write. CardInput in, Card@0 out (or a refusal)."""
    try:
        card = writer.write(card_input["claims"], card_input["audience"], kind=card_input["kind"],
                            facts=card_input.get("facts", {}), locale=card_input.get("locale", "en-US"))
    except CardRejected as exc:
        return {"refusal": {"code": exc.code if exc.code != "SCHEMA" else "UNVERIFIED_CLAIM", "reason": exc.reason,
                            "retryable": False, "owner_action": None, "evidence": []}}
    fallback = isinstance(writer, ModelCardWriter) and writer.last_fallback_reason is not None
    return {"ok": {"value": card, "trace": trace, "fallback_used": fallback or isinstance(writer, TemplateCardWriter),
                   "adapter_id": writer.fallback.adapter_id if fallback else writer.adapter_id}}
