"""WCAG AA contrast for the card palette (definition of done: 'WCAG AA on cards') and the stage text tokens."""
import pathlib
import re

CSS = pathlib.Path(__file__).resolve().parents[1] / "web" / "css"


def tokens(text):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", text))


def lum(hexcolor):
    rgb = [int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


# Dark theme: every text colour against every surface it sits on, and dark text on the bright buttons.
CARD_PAIRS = [("crema", "char"), ("crema", "comal"), ("crema", "comal-2"), ("crema", "comal-3"), ("masa", "char"), ("masa", "comal"),
              ("masa", "comal-2"), ("masa", "comal-3"), ("masa-2", "char"), ("masa-2", "comal"), ("masa-2", "comal-2"), ("corn", "comal"), ("corn", "corn-deep"), ("agave", "comal-2"), ("agave", "agave-deep"),
              ("avocado", "comal"), ("avocado", "avocado-deep"), ("salsa", "comal"), ("salsa", "salsa-deep"), ("sky", "sky-deep"),
              ("on-bright", "salsa"), ("on-bright", "avocado"), ("on-bright", "corn"), ("on-bright", "crema"), ("on-bright", "sky")]
STAGE_PAIRS = [("fg", "bg"), ("fg-2", "bg"), ("fg", "panel"), ("fg-2", "panel"), ("accent", "bg"), ("accent", "panel"), ("good", "panel"),
               ("warn", "panel"), ("rec", "panel")]


def test_card_palette_meets_aa():
    t = tokens((CSS / "cards.css").read_text())
    bad = [(a, b, round(ratio(t[a], t[b]), 2)) for a, b in CARD_PAIRS if ratio(t[a], t[b]) < 4.5]
    assert not bad, bad


def test_stage_palette_meets_aa():
    t = tokens((CSS / "console.css").read_text())
    bad = [(a, b, round(ratio(t[a], t[b]), 2)) for a, b in STAGE_PAIRS if ratio(t[a], t[b]) < 4.5]
    assert not bad, bad


def test_tap_targets_are_at_least_44px():
    css = (CSS / "cards.css").read_text()
    assert re.search(r"\.btn \{[^}]*min-height: 48px", css)
