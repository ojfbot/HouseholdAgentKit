"""What `console_on_fixtures` fetches: every asset the stage and phone pages would load, and nothing they would not.

Cases from the Codex review of #49. Missing a reference is a false green (the page breaks, the check passes);
fetching one the browser never loads is a false red (the page works, the check fails).
"""

from __future__ import annotations

import pytest

from kit_cli import doctor

pytestmark = pytest.mark.doctor

PAGE = "http://127.0.0.1:9/"


@pytest.mark.parametrize(
    ("html", "want"),
    [
        pytest.param('<img srcset="/a.svg 1x, /b.svg 2x">', {"/a.svg", "/b.svg"}, id="srcset"),
        pytest.param('<picture><source srcset="/c.webp"></picture>', {"/c.webp"}, id="source-srcset"),
        pytest.param('<script src = "/spaced.js"></script>', {"/spaced.js"}, id="spaces-around-equals"),
        pytest.param("<script src=/unquoted.js></script>", {"/unquoted.js"}, id="unquoted"),
        pytest.param('<link rel="stylesheet" href="/s.css">', {"/s.css"}, id="stylesheet"),
        pytest.param('<video src="/v.mp4" poster="/p.png"></video>', {"/v.mp4", "/p.png"}, id="video-poster"),
        pytest.param('<base href="/static/"><script src="entry.js"></script>', {"/static/entry.js"}, id="base-href"),
        pytest.param('<base href="/static/js/"><link href="../css/x.css" rel="stylesheet">', {"/static/css/x.css"}, id="base-href-relative"),
    ],
)
def test_the_page_references_a_browser_loads_are_found(html: str, want: set[str]) -> None:
    assert {doctor.urlpath(u) for u in doctor.html_refs(html, PAGE)} == want


@pytest.mark.parametrize(
    "html",
    [
        pytest.param('<!-- <script src="/unused.js"></script> -->', id="commented-out-script"),
        pytest.param('<a href="/elsewhere.html">link</a>', id="a-link-is-not-loaded"),
        pytest.param('<img srcset="data:image/png;base64,AAAA 1x">', id="data-url"),
    ],
)
def test_references_a_browser_does_not_load_are_not_fetched(html: str) -> None:
    assert doctor.html_refs(html, PAGE) == []


@pytest.mark.parametrize(
    ("js", "want"),
    [
        pytest.param('import { h } from "./dom.js";', ["./dom.js"], id="static-import"),
        pytest.param('import "./side.js";', ["./side.js"], id="side-effect-import"),
        pytest.param('export { x } from "./re.js";', ["./re.js"], id="re-export"),
        pytest.param('import("./lazy.js")', ["./lazy.js"], id="dynamic-quoted"),
        pytest.param("import(`./lazy-template.js`)", ["./lazy-template.js"], id="dynamic-template-literal"),
        pytest.param("import(`./${name}.js`)", [], id="dynamic-interpolated-is-out-of-scope"),
    ],
)
def test_module_imports_are_found(js: str, want: list[str]) -> None:
    assert doctor.js_refs(js) == want


@pytest.mark.parametrize(
    ("css", "want"),
    [
        pytest.param('@import "cards.css";', ["cards.css"], id="import-string"),
        pytest.param('@import url("cards.css");', ["cards.css"], id="import-url"),
        pytest.param("background: url(a.svg)", ["a.svg"], id="url-unquoted"),
        pytest.param('background: url( "b.svg" )', ["b.svg"], id="url-quoted-spaces"),
        pytest.param('background: url("a(b).svg")', ["a(b).svg"], id="url-quoted-parens"),
        pytest.param("background: url('c(d).svg')", ["c(d).svg"], id="url-single-quoted-parens"),
        pytest.param('background: url("data:image/png;base64,AAAA")', [], id="data-url"),
        pytest.param('/* background: url("gone.svg") */ color: red', [], id="commented-out"),
    ],
)
def test_stylesheet_references_are_found(css: str, want: list[str]) -> None:
    assert doctor.css_refs(css) == want
