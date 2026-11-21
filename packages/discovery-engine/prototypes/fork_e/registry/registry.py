"""Tiny registry builder: rows_*.py call R(...); build.py collects, validates and dumps statements.yaml."""
ROWS = []
AS_OF = "2026-11-19"
KINDS = {"problem", "desire", "goal", "metric", "capability_claim", "constraint", "risk", "non_goal"}
STYPES = {"walmart_primary", "partner", "press", "analyst", "forum"}


def R(id, url, published, speaker, role, source_type, kind, theme, functions, actors, org_rows, confidence,
      paraphrase, short_quote=None, as_of=AS_OF):
    assert kind in KINDS, (id, kind)
    assert source_type in STYPES, (id, source_type)
    if short_quote:
        assert len(short_quote.split()) < 15, (id, "quote too long")
    ROWS.append({
        "id": id, "source_url": url, "published": published, "as_of": as_of,
        "speaker": speaker, "role": role, "source_type": source_type,
        "paraphrase": paraphrase, **({"short_quote": short_quote} if short_quote else {}),
        "kind": kind, "theme": theme, "business_functions": functions, "actor_types": actors,
        "org_rows": org_rows, "confidence": confidence,
    })
