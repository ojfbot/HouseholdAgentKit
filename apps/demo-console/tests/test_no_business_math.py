"""Tripwire for 'never compute business numbers in the UI'.

The UI may lay out positions and count down time (layout.js, clock.js). Everywhere else, JavaScript must not
parse, format or combine numbers: it prints text and display strings that arrived in a contract. This lint
is a tripwire, not a proof; code review still owns the rule.
"""
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parents[1] / "web" / "js"
ALLOW = {"layout.js", "clock.js"}
BANNED = [r"parseFloat\s*\(", r"parseInt\s*\(", r"\bNumber\s*\(", r"\.toFixed\s*\(", r"toLocaleString\s*\(", r"Intl\.NumberFormat",
          r"\bMath\.", r"\.reduce\s*\(", r"\bsum\s*\(", r"\$\{[^}]*\b(total|amount|price|votes|cap|vas|value)\b[^}]*[-+*/][^}]*\}"]


def test_ui_has_no_business_math():
    hits = []
    for f in sorted(WEB.glob("*.js")):
        if f.name in ALLOW:
            continue
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.strip().startswith("//"):
                continue
            for pat in BANNED:
                if re.search(pat, line):
                    hits.append(f"{f.name}:{n}: {pat}: {line.strip()[:90]}")
    assert not hits, "\n".join(hits)


def test_allowlisted_files_touch_only_time_and_geometry():
    layout = (WEB / "layout.js").read_text()
    assert "pos" in layout and "claim" not in layout and "amount" not in layout
    clock = (WEB / "clock.js").read_text()
    assert "Date" in clock and "claim" not in clock and "amount" not in clock
