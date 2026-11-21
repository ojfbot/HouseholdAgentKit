"""Collect registry rows, apply date corrections, validate, and write statements.yaml."""
import collections, sys, yaml
import registry
import rows_01, rows_02, rows_03, rows_04, rows_05, rows_06, rows_07, rows_08, rows_09  # noqa: F401  (side effect: append rows)

# Dates we could not pin to the day: keep the year (or month) only, so nothing looks more precise than it is.
APPROX = {"ST-165": "2021", "ST-144": "2024-06", "ST-152": "2025", "ST-146": "2026", "ST-148": "2026",
          "ST-149": "2026", "ST-163": "2026", "ST-157": "2025-04", "ST-123": "2024", "ST-126": "2025",
          "ST-114": "2025", "ST-151": "2026-11", "ST-162": "2026-10", "ST-141": "2024-06-27 (filed)",
          "ST-100": "2026", "ST-113": "2026-10", "ST-168": "2023", "ST-176": "2026", "ST-182": "2025", "ST-186": "2026-04", "ST-187": "2026-05", "ST-178": "2026-07", "ST-188": "2026", "ST-200": "2026-11"}
FIX_URL = {"ST-150": "https://chiefmarketer.com/walmart-launches-generative-ai-shopping-chatbot"}

rows = registry.ROWS
for r in rows:
    if r["id"] in APPROX:
        r["published"] = APPROX[r["id"]]
        r["date_precision"] = "approximate"
    if r["id"] in FIX_URL:
        r["source_url"] = FIX_URL[r["id"]]

# One short quote per source (brief rule). Where a source yielded several, keep the one the synthesis relies on;
# the others stay as paraphrase only (their wording is already paraphrased in each row).
KEEP_QUOTE = {"ST-004", "ST-013", "ST-025", "ST-033", "ST-045", "ST-064", "ST-072", "ST-101", "ST-103", "ST-108", "ST-136", "ST-167"}
by_src = collections.defaultdict(list)
for r in rows:
    if r.get("short_quote"): by_src[r["source_url"]].append(r)
for src, rs in by_src.items():
    if len(rs) > 1:
        keep = [r for r in rs if r["id"] in KEEP_QUOTE]
        assert len(keep) == 1, (src, [r["id"] for r in rs])
        for r in rs:
            if r is not keep[0]: del r["short_quote"]
chk = collections.Counter(r["source_url"] for r in rows if r.get("short_quote"))
assert max(chk.values()) == 1
assert all(len(r["short_quote"].split()) < 15 for r in rows if r.get("short_quote"))

ids = [r["id"] for r in rows]
dupes = [i for i, c in collections.Counter(ids).items() if c > 1]
assert not dupes, dupes
urls = {r["source_url"].split("#")[0].rstrip("/") for r in rows}
stats = {
    "rows": len(rows),
    "unique_sources": len(urls),
    "by_source_type": dict(collections.Counter(r["source_type"] for r in rows)),
    "by_kind": dict(collections.Counter(r["kind"] for r in rows)),
    "walmart_primary_sources": len({r["source_url"] for r in rows if r["source_type"] == "walmart_primary"}),
    "with_short_quote": sum("short_quote" in r for r in rows),
}
doc = {
    "registry_version": "statements@1",
    "fork": "E",
    "as_of": max([registry.AS_OF] + [r["as_of"] for r in rows]),
    "rules": [
        "Public sources only; nothing behind a login; no scraping.",
        "short_quote is at most one phrase under 15 words, and at most one per source (enforced at build); everything else is paraphrase.",
        "Speaker and role as published. 'via X' means the words reached us through X, not from the speaker's own channel.",
        "source_type: walmart_primary = Walmart's own page, filing, posting or transcript; press quoting a Walmart executive stays 'press'.",
        "Inference is never stored here; it lives in the synthesis and is labeled there.",
        "confidence: high = primary or multiple consistent reports; medium = single reputable secondary; low = vendor, aggregator or forum.",
    ],
    "stats": stats,
    "statements": rows,
}
yaml.safe_dump(doc, open("statements.yaml", "w"), sort_keys=False, allow_unicode=True, width=140)
print(yaml.safe_dump(stats, sort_keys=False))
