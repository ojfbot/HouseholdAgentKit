# Fork H — demo console (D01–D06, E16, E19, K11)

Fork H, Demo & experience engineer (role DX), Nov 19 2026. This folder holds one offline demo console with three beats (hello world, engine map, Care Profiles), phone ballots, Ruth's voice request, Jen's over-cap card and a recorded fallback per beat. It also holds K11, the role-scoped card writer. The layout matches the repo's target paths; when the repo exists, `fork-h/` maps to its root.

**Status:** everything runs on contract fixtures today, because no upstream service is live yet. Each port flips from `fixture` to `http` as its owner ships. While a beat is on fixtures, the stage shows a "not for the room" banner.

## Layout

```
apps/demo-console/
  server/host.py            D01/D02/D03/D06 host: stdlib HTTP + SSE, beat controller, phone relay, ports
  server/contracts.py       consumer-side checks: Poll@1, Card@0 (+drafts), Readout@0/ControlDelta@0 (G drafts), Request, Result@0
  server/e16_view.py        E16 publisher: G's Readout@0 -> readout-view@0 (display strings, labels; no re-ranking)
  server/k10_stub.py        K10 stand-in speaking Poll@1 (sim clock, poll.closed, one decision per poll); PD's K10 replaces it
  server/stt_seam.py        D03 voice seam: mlx-whisper or whisper.cpp, 4 s timeout, then typed; Request(channel=voice)
  server/warmup.py          D06 pre-doors check (exit 0 = ready; --strict from Nov 30)
  web/stage.html, phone.html, js/*.js, css/*.css   no build step, ES modules, offline
  fixtures/{hello,engine,care,proof}/              contract fixtures (all synthetic)
  fixtures/build_engine_fixtures.py                run-0 bank extract -> readout-view fixtures (projection only)
  recordings/manifest.json, tools/register_recording.py   per-beat fallbacks, captured Nov 30
  tests/                    pytest: host flow, E16, no-business-math lint, AA contrast; tests/e2e/console.e2e.mjs (headless Chrome)
  console.example.json      copy to console.json on the stage host
packages/card-writer/       K11: CardWriter.write(claims, audience) -> Card@0; templates + model seam + number guard
```

## Run (the stage host, offline)

```bash
cd apps/demo-console && cp console.example.json console.json   # set public_url to the hotspot address
python3 fixtures/build_engine_fixtures.py    # writes fixtures/engine/readout.*.json + deltas.json (generated, not committed)
python3 server/host.py                       # stage at http://127.0.0.1:8765/  (presenter window: /?hud=1)
python3 server/warmup.py                     # checklist; --strict from Nov 30
python3 -m pytest -q tests ../../packages/card-writer/tests
CHROME=/path/to/chrome node tests/e2e/console.e2e.mjs   # needs puppeteer-core (dev only)
```

The host needs only CPython. `segno` (pure Python) renders the QR code; without it the stage shows the URL as text. `mlx-whisper` is optional.

**Keys:** `1` `2` `3` beats · `0` blank · Space/→ next step · ← back · `R` recording · `L` live · `P` proof view · `H` HUD · Shift+R reset beat.
- Beat 1: `A` flips the policy · `7` `8` `9` pick as owner.
- Beat 2: `M` `S` `B` control profiles · `N` lens · `D` drill into Care Profiles.
- Beat 3: `V` listen · `C` clip · `T` typed fallback.

## Beats (R5.1 default, A's hw-taco@1 beat)

| Beat | Steps (Space advances) | Live source when it ships |
| --- | --- | --- |
| 1 Hello world | Mom's text · Sparky today (the owner's recording, tier 0) · the brief (Brief@1 H1 text) · three priced carts · QR · 45 s poll · tally and policy flip · tortilla heads-up · approval and explanation · consent gate and order | K10/K23 bus (Poll@1), K27 hook (tier chips), K11 cards |
| 2 Engine map | the map · flip a control · flip the lens · drill into a cell | Fork G live API (`/readout`, `/delta`, `/family/<id>`) |
| 3 Care Profiles | today's model · Ruth's profile · through the care profile · over the cap (the room is Jen) · Jen decides · optional: locked bread, gift-card block, Ruth's month | K01 → K07/K08 → K11 chain; mock Gateway log for the compare rows |

## Rules the code enforces

- **No business math in the UI.** JS prints text and display strings. Only `layout.js` (positions) and `clock.js` (countdowns off the Poll@1 sim clock) do arithmetic, and `tests/test_no_business_math.py` trips on the rest.
- **Every number has a claim and a label.** K11 fills numbers from claims, one per line. The guard refuses a digit without a claim, an unlabeled claim, or a number in a button label. That rule caught A's "(10 ct)" and an unclaimed pickup time.
- **The model writes words only.** The K11 model seam returns sections with `{c:id}` placeholders. Any invented number, dropped number, schema miss or transport failure falls back to the template, and the result says `fallback_used`.
- **Tier chips light only from a live HelloWorldResult@1 with `pass`.** Fixtures show outlines.
- **Phones get their own role's card only.** Ballot links are single use, and only their sha256 travels in `poll.response`. Kids' inputs are masked in the log.

## Definition of done (brief) — where it stands

| Check | Target | Now (fixtures, headless Chrome) |
| --- | --- | --- |
| Every beat by one key | yes | yes: about 260 ms (keypress to render) |
| Cold start to ready | < 2 min | 0.12 s to health; warm-up < 1 s |
| Switch to a recording | < 10 s | 14–51 ms (the files themselves arrive Nov 30) |
| Flip re-renders | < 1 s | 4–12 ms (the fixture port; G's live E11 is about 1 ms plus a round trip) |
| Every number labeled and verified | 100% | guard + lint; stage-wide digit scan still to add (IQ) |
| WCAG AA on cards | AA | palette checked by `test_a11y.py`; 48 px tap targets |
| Typed fallback | < 5 s | 0.42–0.47 s |

## Contracts used and draft fields asked (coordination log, Nov 19)

- **Poll@1** (A): used as published. Asked: `options[]` for "room is Jen", and an optional live turnout while the poll is open.
- **Card@0** (F): asked additive, optional fields `headline`, `actions[]`, `sections[].option`, `lines[].mark`, `claims[].label`, kind `readback`.
- **Readout@0 / ControlDelta@0** (F, G's drafts): consumed as G drafted them. The console's own shape is internal (`readout-view@0`), built by E16.
- **Label vocabulary:** `synthetic | public:<src>` is shared. G adds `score:`, `weight:` and `derived:`, and H adds `observed:room` for votes from the room. One list is asked of F.
