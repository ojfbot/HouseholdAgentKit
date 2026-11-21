// D01 stage console: three beats, one key each, a recorded fallback per beat (ADR-009).
// Renders host snapshots. Keys post to the host, so a presenter window (?hud=1) and the projector window
// stay in step. Nothing here computes a business number: text, display strings and K10's tally arrive ready.
import { h, post, subscribe } from "./dom.js";
import { renderCard, labelChip } from "./render-card.js";
import { renderEngine } from "./render-readout.js";
import { closesAtWall, mmss, secondsLeftWall, since, spanWall, stamp, tickCountdowns, ticker } from "./clock.js";
import { pct, series } from "./layout.js";

const params = new URLSearchParams(location.search);
const BEATS = { 0: "Ready", 1: "Taco night", 2: "The engine map", 3: "Care Profiles" };
let S = null;
let hud = params.get("hud") === "1";
let conn = "connecting";
let flipT0 = null, lastFlipMs = null, lastSwitchMs = null;
const ends = {};  // poll_id -> wall ms when it closes (from the sim clock at receipt)
const app = document.getElementById("app");
const recLayer = document.getElementById("recordings");
const videos = {};

// ------------------------------------------------------------------ recordings (D06) + the Sparky clip (beat 1, tier 0)
function setupRecordings(manifest) {
  for (const beat of ["1", "2", "3"]) {
    if (videos[beat]) continue;
    const m = manifest[beat];
    const v = h("video", { class: "rec", preload: "auto", muted: true, playsinline: true, src: `/recordings/${m.file}`, "data-beat": beat });
    v.muted = true;
    v.addEventListener("error", () => v.classList.add("is-missing"));
    const slate = h("div", { class: "rec-slate" }, h("strong", {}, `Recording for beat ${beat} not captured yet`), h("span", {}, "Captured at the Nov 30 dress rehearsal. Press L for live."));
    const wrap = h("div", { class: "rec-wrap", "data-beat": beat }, v, slate, h("div", { class: "rec-badge" }, "Recorded at the Nov 30 rehearsal"));
    videos[beat] = { wrap, v };
    recLayer.append(wrap);
  }
}

function syncRecordings() {
  for (const [beat, { wrap, v }] of Object.entries(videos)) {
    const on = S && String(S.beat) === beat && S.view[beat] === "recording";
    wrap.classList.toggle("is-on", on);
    if (on && v.paused && !v.classList.contains("is-missing")) v.play().catch(() => {});
    if (!on && !v.paused) v.pause();
  }
}

let sparkyEl = null;
function sparkyClip() {
  const m = S.recordings["1s"];
  if (!sparkyEl) {
    sparkyEl = h("video", { class: "sparky-video", preload: "auto", muted: true, playsinline: true, controls: true, src: m ? `/recordings/${m.file}` : "" });
    sparkyEl.addEventListener("error", () => sparkyEl.classList.add("is-missing"));
  }
  const when = m && m.captured_at ? m.captured_at.slice(0, 10) : "date pending";
  return h("figure", { class: "sparky" }, sparkyEl,
    h("div", { class: "sparky-slate" }, "An optional recording of the retailer's own assistant goes here."),
    h("figcaption", {}, h("span", { class: "chip chip-public" }, `${S.hello.sparky.label} · ${when}`), " Real app, not the twin."));
}

// ------------------------------------------------------------------ shared pieces
function badge(beat) {
  const src = S.sources[beat];
  return h("span", { class: `source source-${src}` }, h("i", {}), { live: "Live", fixture: "Rehearsal data", recording: "Recorded Nov 30" }[src]);
}

const MARK = `<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 17 A10 10 0 0 1 22 17 Z" fill="#ffc940"/><circle cx="8" cy="11" r="2.2" fill="#ff5b3a"/><circle cx="14" cy="10" r="2.2" fill="#93d36b"/></svg>`;
function topBar(b) {
  const brand = h("div", { class: "brand", html: MARK });
  brand.append("Household Agent Kit", h("small", {}, "an open proof of concept"));
  const parts = h("nav", { class: "parts", "aria-label": "The talk" }, [1, 2, 3].map((n) =>
    h("span", { class: `part ${n === b ? "is-on" : ""} ${b && n < b ? "is-done" : ""}` }, h("b", {}, n), BEATS[n])));
  return h("header", { class: "top" }, brand, parts, b ? badge(b) : h("span", {}));
}

function guardBanner(beat) {
  if (!beat || S.sources[beat] !== "fixture" || !S.stage_guard) return null;
  return h("div", { class: "guard" }, "Fixture data: not for the room. Switch to live, or press R for the recording.");
}

function tallyBars(tally, opts = {}) {
  if (!tally) return h("p", { class: "muted" }, "Votes are counted when the poll closes.");
  return h("div", { class: "tally" }, tally.options.map((o) => h("div", { class: `bar-row ${opts.winner === o.option_id ? "is-winner" : ""}`,
    onclick: opts.onPick ? () => opts.onPick(o.option_id) : null },
    h("span", { class: "bar-label" }, o.label),
    h("span", { class: "bar" }, h("span", { class: "fill", style: `width:${pct(o.share)}` })),
    h("span", { class: "bar-n" }, o.votes, h("span", { class: "chip chip-observed" }, "observed:room")))),
    h("p", { class: "turnout" }, "Phones that voted: ", tally.turnout.voted, " ", h("span", { class: "chip chip-observed" }, "observed:room")));
}

function countdown(poll, small = false) {
  const id = poll.opened && poll.opened.poll_id;
  if (id && poll.state === "open" && poll.clock) ends[id] = closesAtWall(poll.opened.closes_at, poll.clock);
  const end = id && poll.state === "open" ? ends[id] : null;
  const span = poll.opened ? spanWall(poll.opened.opened_at, poll.opened.closes_at, poll.clock || poll.opened.clock) : null;
  const ring = h("div", { class: `ring ${small ? "is-small" : ""}`, style: poll.state === "open" ? "" : "--left:0", html:
    `<svg viewBox="0 0 100 100" aria-hidden="true"><circle class="track" cx="50" cy="50" r="46" pathLength="100"/><circle class="arc" cx="50" cy="50" r="46" pathLength="100"/></svg>` });
  ring.append(h("div", { class: "countdown", "data-closes-wall": end ?? "", "data-span-ms": span ?? "" }, poll.state === "open" ? mmss(secondsLeftWall(end)) : "0:00"));
  return ring;
}

function stepInfo(beat) {
  const steps = beat === 1 ? S.hello.steps : beat === 2 ? S.engine.steps : S.care.steps;
  return { steps, i: S.steps[beat], cur: steps[S.steps[beat]] };
}

// ------------------------------------------------------------------ beat 1: hello world (Poll@1)
function viewHello() {
  const { cur } = stepInfo(1);
  const H = S.hello;
  const P = H.poll;
  const sid = cur.id;
  const wrap = h("div", { class: `beat beat-hello step-${sid}` });
  if (cur.tier !== null) wrap.append(tierChips(H.tiers, cur.tier));
  if (sid === "request") {
    wrap.append(h("div", { class: "hero" },
      h("div", { class: "thread" }, h("span", { class: "who" }, "Mom, to the family agent"), h("p", { class: "bubble" }, H.request.text)),
      h("p", { class: "lede" }, "The chore is a delivered dinner, not a recipe.")));
  } else if (sid === "sparky") {
    wrap.append(sparkyClip());
  } else if (sid === "brief") {
    wrap.append(h("div", { class: "brief-grid" },
      h("div", { class: "thread" }, h("span", { class: "who" }, "What Mom typed"), h("p", { class: "bubble sm" }, H.request.text),
        h("p", { class: "label", style: "margin-top:1.6rem" }, "What stays home"), h("ul", { class: "stays" }, ["Names and ages", "Why a food is locked", "The household's history", "Anything a member typed"].map((t) => h("li", {}, t)))),
      h("div", { class: "brief" }, h("p", { class: "label" }, "The brief Sparky gets"), h("p", { class: "brief-text" }, H.brief.h1_text),
        h("p", { class: "muted small" }, h("span", { class: "chip chip-draft" }, "K02 template text"), ` round trip checked (${H.brief.verified_by})`))));
  } else if (sid === "menu") {
    wrap.append(h("div", { class: "menu-head" }, h("h1", { class: "display md" }, "Show the trade-off. Keep the lock."),
      h("p", { class: "lede" }, "Three carts from Walmart's own backend, each tuned for a different kind of value.")),
      renderCard(H.menu, { className: "menu", noHeadline: true }));
  } else if (sid === "join") {
    wrap.append(joinPanel("You're the family tonight."));
  } else if (sid === "vote") {
    wrap.append(h("div", { class: "vote-grid" }, countdown(P),
      h("div", {}, h("h1", { class: "display xl" }, "Vote on your phone."),
        h("p", { class: "phones-in" }, h("strong", {}, S.members.total), h("span", {}, "phones in the family tonight")),
        h("p", { class: "lede" }, "The poll service counts the votes when the timer ends. This screen never does."),
        h("div", { style: "display:flex;gap:2rem;align-items:center;margin-top:1.6rem" }, joinMini(), policyToggle(H.policy)))));
  } else if (sid === "tally") {
    const d = P.decision;
    wrap.append(h("div", { class: "tally-grid" },
      h("div", {}, h("h1", { class: "display md", style: "margin-bottom:1.4rem" }, "The family voted."), tallyBars(P.tally, { winner: d?.cart_id,
        onPick: P.state === "awaiting_owner" ? (id) => post("/api/hello/owner_pick", { cart_id: id }) : null })),
      h("div", { class: "decision" }, policyToggle(H.policy),
        d ? h("div", {}, h("p", { class: "decision-status" }, `Decided: ${P.decision_label}`), h("p", { class: "muted" }, P.decision_why))
          : P.state === "awaiting_owner" ? h("div", {}, h("p", { class: "decision-status" }, "Waiting for the owner"),
            h("p", { class: "hint" }, "The owner picks. Click a bar.")) : h("p", { class: "muted" }, "Closing the poll…"))));
  } else if (sid === "tortilla") {
    wrap.append(H.tortilla ? h("div", { class: "tortilla-grid" }, renderCard(H.tortilla, { className: "tortilla", showActions: true }),
      h("div", { class: "side-note" }, h("h1", { class: "display md" }, "The riskiest line in the cart isn't the most expensive one."),
        h("p", { class: "lede" }, "A locked item never gets swapped, even when the swap looks identical."))) : null);
  } else if (sid === "approve") {
    if (!H.approval && P.state === "awaiting_owner") {
      wrap.append(h("h1", { class: "display md" }, "A tie. The owner picks."), tallyBars(P.tally, { onPick: (id) => post("/api/hello/owner_pick", { cart_id: id }) }));
    } else {
      wrap.append(H.approval ? h("div", { class: "approve-grid" }, renderCard(H.approval, { className: "approval", showActions: true }),
        H.explanation ? renderCard(H.explanation, { className: "explanation" }) : null)
        : h("p", { class: "muted" }, "No decision yet: go back one step."));
    }
  } else if (sid === "order") {
    wrap.append(H.consent ? h("div", { class: "consent" },
      h("div", {}, h("h1", { class: "display" }, "Mom says yes. Walmart still asks."),
        h("p", { class: "lede", style: "margin-top:1.2rem" }, "Consent gate, then checkout under her profile, on the synthetic twin. Every step is a ledger entry.")),
      h("ol", {}, H.consent.steps.map((s) => h("li", { class: `st-${s.status}` }, h("span", { class: "mark" }, s.status === "done" ? "✓" : "…"),
        h("span", {}, s.name, h("span", { class: "ev" }, s.evidence))))))
      : h("p", { class: "muted" }, "The owner hasn't approved yet."));
  }
  return wrap;
}

function tierChips(t, current) {
  // D04: a chip lights only from the hook's HelloWorldResult@1 (server side), never from the UI.
  const live = t.source === "live";
  return h("div", { class: "tiers" }, ["0", "1", "2"].map((k) => {
    const res = t.result.tiers[k] || {};
    const lit = live && res.pass === true;
    return h("span", { class: `tier ${lit ? "is-lit" : live ? "is-off" : "is-fixture"} ${String(current) === k ? "is-current" : ""}`,
      title: `${t.result.oracle_version} · status ${t.result.status}` }, h("b", {}, `Tier ${k}`), t.names[k]);
  }));
}

function policyToggle(policy) {
  return h("div", { class: "policy" }, h("span", { class: "label" }, "Who decides"),
    h("button", { class: `flip ${policy === "owner_decides" ? "is-on" : ""}`, onclick: () => post("/api/hello/policy", { policy: "owner_decides" }) }, "Owner decides"),
    h("button", { class: `flip ${policy === "auto_plurality" ? "is-on" : ""}`, onclick: () => post("/api/hello/policy", { policy: "auto_plurality" }) }, "Auto: plurality"));
}

function joinPanel(title) {
  const r = S.members.roles;
  const count = (n, what) => h("div", { class: "role-count" }, h("strong", {}, n), h("span", {}, what));
  return h("div", { class: "join" }, h("div", { class: "qr-tile" }, h("img", { class: "qr", src: "/api/qr.svg", alt: `Join at ${S.join_url}` })),
    h("div", {}, h("h1", { class: "display xl" }, title), h("p", { class: "url" }, S.join_url),
      h("div", { class: "roles" }, count(r.partner, "partners"), count(r.teen, "teens"), count(r.kid, "kids")),
      h("p", { class: "lede", style: "margin-top:1.2rem" }, "No sign-in, no personal data. Your phone gets a family role at random.")));
}

function joinMini() {
  return h("div", { class: "join-mini" }, h("div", { class: "qr-tile" }, h("img", { class: "qr", src: "/api/qr.svg", alt: "" })), h("span", { class: "url" }, S.join_url));
}

// ------------------------------------------------------------------ beat 2: engine map
function viewEngine() {
  return h("div", { class: "beat beat-engine" }, renderEngine(S.engine, {
    onDrill: (id) => post("/api/engine/drill", { family_id: id }),
    onFlip: (request) => flip(request),
  }));
}

function flip(request) {
  flipT0 = stamp();
  post("/api/engine/delta", { request }).catch(showError);
}

// ------------------------------------------------------------------ beat 3: Care Profiles
function viewCare() {
  const C = S.care;
  const sid = C.step_id;
  const wrap = h("div", { class: `beat beat-care step-${sid}` });
  const left = h("div", { class: "ruth" },
    h("div", { class: "persona" }, h("span", { class: "avatar" }, "R"), h("div", {}, h("strong", {}, "Ruth, 82, Tampa"), h("span", {}, "Asks by voice. Synthetic persona."))),
    h("div", { class: "persona" }, h("span", { class: "avatar jen" }, "J"), h("div", {}, h("strong", {}, "Jen, her daughter, Columbus"), h("span", {}, "Pays and approves over the limit."))),
    voicePanel(C));
  const right = h("div", { class: "care-main" });
  if (sid === "today") right.append(comparePanel(C.compare, ["today"]), h("p", { class: "muted" }, "Through Jen's account, as Agent Profiles were announced: one profile per agent, account-level usuals."));
  if (sid === "profile") right.append(renderCard(C.profile_card, { className: "profile" }));
  if (sid === "care") right.append(comparePanel(C.compare, ["today", "care"]), C.cards.ruth ? renderCard(C.cards.ruth, { className: "readback" }) : null,
    h("p", { class: "quiet" }, "Jen's phone: quiet. It's inside the rules."));
  if (sid === "heater") right.append(C.cards.jen ? h("div", { class: "jen-grid" }, renderCard(C.cards.jen, { className: "over-cap", showActions: true }),
    h("div", { class: "jen-side" }, h("h1", { class: "display md" }, "Now you're Jen."), joinMini(), countdown(C.poll, true), tallyBars(C.poll.tally)))
    : h("p", { class: "waiting" }, "Waiting for Ruth's next request…"));
  if (sid === "decision") right.append(decisionPanel(C));
  if (sid === "lock") right.append(C.cards.ruth ? renderCard(C.cards.ruth, { className: "readback" }) : null, notice(C.notice));
  if (sid === "scam") right.append(notice(C.notice));
  if (sid === "month") right.append(C.cards.jen_digest ? renderCard(C.cards.jen_digest, { className: "digest" }) : null);
  if (C.result && hud) right.append(resultChip(C.result));
  wrap.append(left, right);
  return wrap;
}

function voicePanel(C) {
  const req = C.request;
  const needs = (C.steps.find((s) => s.id === C.step_id) || {}).utterance;
  const box = h("div", { class: `voice ${needs ? "is-waiting" : ""}` });
  if (req) {
    box.append(h("p", { class: "transcript" }, req.text),
      h("p", { class: "muted" }, h("span", { class: `chip chip-mode-${req._input_mode}` }, { stt: "heard", typed: "typed fallback", clip: "recorded clip" }[req._input_mode] || req._input_mode),
        req._matched ? "" : h("span", { class: "chip chip-warn" }, "didn't match the scripted request")));
  }
  if (needs) {
    box.append(...[h("div", { class: "voice-controls" },
      h("button", { class: `btn btn-mic ${recording ? "is-on" : ""}`, onclick: toggleMic, "aria-label": recording ? "Stop listening" : "Listen",
        html: recording ? "■" : `<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" fill="#14110d"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke="#14110d" stroke-width="2" fill="none" stroke-linecap="round"/></svg>` }),
      h("button", { class: "btn btn-clip", onclick: playClip }, "Play clip"),
      h("form", { class: "typed", onsubmit: (ev) => { ev.preventDefault(); const t = ev.target.elements.t.value.trim(); if (t) { sendRequest(t, "typed"); ev.target.elements.t.value = ""; } } },
        h("input", { name: "t", id: "typed", placeholder: "Or type what Ruth said", "aria-label": "Typed fallback", autocomplete: "off" }))),
      hud ? h("p", { class: "muted small" }, C.stt.available ? `Speech to text: ${C.stt.engine}, ${C.stt.timeout_s} s then type` : "No local speech-to-text on this host: type it, or play the clip.") : null].filter(Boolean));
  }
  return box;
}

function comparePanel(cmp, cols) {
  const names = { today: "Today's model", care: "Care profile" };
  return h("table", { class: `compare src-${cmp.source}` }, h("thead", {}, h("tr", {}, h("th", {}, ""), cols.map((c) => h("th", {}, names[c])))),
    h("tbody", {}, cmp.rows.map((r) => h("tr", {}, h("th", {}, r.plain),
      cols.map((c) => h("td", { class: `st-${r[c].status}`, title: `${r.metric} · ${r[c].evidence}` }, h("span", { class: "mark" }, r[c].status === "pass" ? "✓" : "✗"), " ", r[c].observed))))));
}

function decisionPanel(C) {
  const d = C.poll.decision;
  if (!d) return h("p", { class: "waiting" }, C.poll.state === "awaiting_owner" ? "A tie. The presenter decides." : "Closing Jen's poll…");
  const words = { approve: "Jen approved. Ruth hears a short read-back; the heater ships to Tampa.",
    suggest_smaller: "Jen asked for a smaller one. The agent will ask Ruth; nothing is charged yet.",
    call: "Jen will call Mom first. The order is held; nothing is charged." }[d.cart_id] || "";
  return h("div", { class: "decision" }, h("p", { class: "decision-status" }, `Jen's answer: ${C.poll.decision_label || "none"}`), h("p", { class: "lede" }, words), tallyBars(C.poll.tally, { winner: d.cart_id }));
}

function notice(n) {
  if (!n) return null;
  return h("p", { class: `notice notice-${n.kind}` }, n.code ? h("span", { class: "chip chip-refusal" }, n.code) : null, " ", n.text);
}

function resultChip(r) {
  if (r.refusal) return h("p", { class: "result muted" }, "Result@0 refusal ", h("span", { class: "chip chip-refusal" }, r.refusal.code), ` · ${r.refusal.reason}`);
  if (r.ok) return h("p", { class: "result muted" }, `Result@0 ok · ${r.ok.adapter_id}${r.ok.fallback_used ? " · fallback used" : ""}`);
  return null;
}

// voice capture (D03): the browser records, the host transcribes locally, typed fallback otherwise
let recording = null;
async function toggleMic() {
  if (recording) { recording.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      recording = null; render();
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      const r = await fetch("/api/care/voice", { method: "POST", headers: { "Content-Type": blob.type }, body: blob }).then((x) => x.json());
      if (r.ok) sendRequest(r.text, "stt");
      else { const t = document.getElementById("typed"); if (t) { t.placeholder = "Didn't catch that: type it"; t.focus(); } }
    };
    rec.start(); recording = rec; render();
  } catch (e) { const t = document.getElementById("typed"); if (t) t.focus(); }
}

function playClip() {
  const clip = S.care.clip;
  if (!clip) return;
  new Audio(`/recordings/${clip.file}`).play().catch(() => {});
  sendRequest(clip.transcript, "clip");
}

function sendRequest(text, mode) {
  post("/api/care/request", { text, input_mode: mode }).catch(showError);
}

// ------------------------------------------------------------------ proof overlay (D05)
function proofOverlay() {
  const P = S.proof;
  const W = 520, H = 260, box = { left: 40, top: 28, width: 440, height: 188 };
  const pts = P.pass_k.points;
  const line = h("div", { class: "chart" });
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const coords = series(pts, box);
  s.innerHTML = `<rect x="${box.left}" y="${box.top}" width="${box.width}" height="${box.height}" class="frame"/>` +
    `<polyline class="ln" points="${coords.map((c) => c.join(",")).join(" ")}"/>` +
    coords.map((c, i) => `<circle cx="${c[0]}" cy="${c[1]}" r="6"/><text x="${c[0]}" y="${c[1] - 12}" text-anchor="middle">${pts[i].claim.display}</text><text x="${c[0]}" y="${H - 18}" text-anchor="middle" class="ax">k=${pts[i].k}</text>`).join("");
  line.append(s);
  const parity = h("div", { class: "parity" }, P.parity.rows.map((r) => h("div", { class: "bar-row" }, h("span", { class: "bar-label" }, r.segment),
    h("span", { class: "bar" }, h("span", { class: "fill", style: `width:${pct(r.pos)}` }), h("span", { class: "floor", style: `left:${pct(P.parity.floor_pos)}` })),
    h("span", { class: "bar-n" }, r.claim.display, labelChip(r.claim)))));
  const blind = P.blind || {};
  return h("div", { class: "proof" }, h("button", { class: "close", onclick: () => post("/api/proof", { open: false }) }, "×"),
    P.source === "fixture" ? h("div", { class: "guard" }, "Placeholder eval report: replace with the Nov 30 release bundle's K27 report.") : null,
    h("h2", {}, "How we know it works"),
    h("div", { class: "proof-grid" },
      h("section", {}, h("h3", {}, P.pass_k.metric), line, h("p", { class: "muted" }, "Households feel reliability, not averages.")),
      h("section", {}, h("h3", {}, P.parity.metric), parity, h("p", { class: "muted" }, `Floor ${P.parity.floor_claim.display}: no segment below it.`))),
    h("p", { class: "blind" }, "Blind transfer, spaghetti night: ", blind.status === "pass" ? `passed (${blind.release}, ${blind.date})` : "not shown until the latest release passes"),
    h("p", { class: "muted" }, `Trace: ${P.trace.label} · thread ${P.trace.thread_id} · report ${P.report_hash || "hash pending"}`));
}

// ------------------------------------------------------------------ HUD + frame
function hudPanel() {
  const b = S.beat;
  const info = b ? stepInfo(b) : null;
  return h("footer", { class: "hud" },
    h("div", { class: "hud-steps" }, info ? info.steps.map((s, i) => h("span", { class: `hs ${i === info.i ? "is-on" : ""} ${s.optional ? "is-opt" : ""}` }, s.title)) : "Press 1, 2 or 3"),
    b === 1 ? h("p", { class: "meta" }, `hello-world hook: ${S.hello.tiers.result.status} · ${S.hello.tiers.result.oracle_version}`) : null,
    info ? h("p", { class: "say" }, info.cur.say) : null,
    h("p", { class: "keys" }, "1 2 3 beats · Space/→ next · ← back · R recording · L live · P proof · H hud · Shift+R reset",
      b === 1 ? " · A policy · 7 8 9 owner pick" : b === 2 ? " · M marketing · S supply · B balanced · N lens · D drill · Esc" : b === 3 ? " · V listen · C clip · T type" : ""),
    h("p", { class: "meta" }, `${conn} · v${S.version} · sources ${Object.entries(S.sources).map(([k, v]) => `${k}:${v}`).join(" ")} · ${S.members.total} phones`,
      lastFlipMs !== null ? ` · last flip ${lastFlipMs} ms` : "", lastSwitchMs !== null ? ` · last switch ${lastSwitchMs} ms` : ""));
}

function render() {
  if (!S) return;
  const b = S.beat;
  const view = b === 1 ? viewHello() : b === 2 ? viewEngine() : b === 3 ? viewCare() : h("div", { class: "beat beat-blank" },
    h("h1", { class: "display xl" }, "Dinner, handled. Under the family's rules."),
    h("p", { class: "lede", style: "font-size:1.5rem;margin-top:1.4rem" }, "An agent that shops for a household, under the household's rules, through Walmart's own backend."));
  const frag = [topBar(b), guardBanner(b), view, S.proof_open ? proofOverlay() : null, hud ? hudPanel() : null].filter(Boolean);
  const focused = document.activeElement && document.activeElement.id;
  const typed = document.getElementById("typed");
  const draft = typed ? typed.value : "";
  app.replaceChildren(...frag);
  const t2 = document.getElementById("typed");
  if (t2 && draft) t2.value = draft;
  if (focused) { const el = document.getElementById(focused); if (el) el.focus(); }
  syncRecordings();
}

function showError(e) {
  const t = h("div", { class: "toast" }, e.message || String(e));
  document.body.append(t);
  setTimeout(() => t.remove(), 3500);
}

// ------------------------------------------------------------------ keys (beat controller)
const BEAT_KEYS = { 0: 0, 1: 1, 2: 2, 3: 3 };
const SWITCH_KEYS = { m: "marketing_crm", s: "supply_chain", b: "default" };
const PICK_KEYS = { 7: "c_a", 8: "c_b", 9: "c_c" };
document.addEventListener("keydown", (ev) => {
  if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA")) {
    if (ev.key === "Escape") ev.target.blur();
    return;
  }
  if (!S) return;
  const k = ev.key;
  const b = S.beat;
  const act = (p) => p.catch(showError);
  if (k in BEAT_KEYS) return act(post("/api/beat", { beat: BEAT_KEYS[k] }));
  if (k === " " || k === "ArrowRight" || k === "PageDown") { ev.preventDefault(); return act(post("/api/step", { delta: 1 })); }
  if (k === "ArrowLeft" || k === "PageUp") return act(post("/api/step", { delta: -1 }));
  if (k === "R" && ev.shiftKey && b) return act(post("/api/reset", { beat: b }));
  if ((k === "r" || k === "R") && b) { const t0 = stamp(); return act(post("/api/view", { beat: b, view: "recording" }).then(() => { lastSwitchMs = since(t0); })); }
  if ((k === "l" || k === "L") && b) return act(post("/api/view", { beat: b, view: "live" }));
  if (k === "p" || k === "P") return act(post("/api/proof", {}));
  if (k === "h" || k === "H") { hud = !hud; return render(); }
  if (k === "f" || k === "F") return document.documentElement.requestFullscreen?.();
  if (b === 1) {
    if (k === "a" || k === "A") return act(post("/api/hello/policy", { policy: S.hello.policy === "owner_decides" ? "auto_plurality" : "owner_decides" }));
    if (k in PICK_KEYS) return act(post("/api/hello/owner_pick", { cart_id: PICK_KEYS[k] }));
  }
  if (b === 2) {
    const to = SWITCH_KEYS[k.toLowerCase()];
    if (to) return flip({ op: "switch", path: [], value: to });
    if (k === "n" || k === "N") return flip({ op: "lens", path: [], value: S.engine.readout.profile.lens === "partner" ? "in_house" : "partner" });
    if (k === "d" || k === "D") return act(post("/api/engine/drill", { family_id: "PF-28" }));
    if (k === "Escape") return act(post("/api/engine/drill", { family_id: null }));
  }
  if (b === 3) {
    if (k === "v" || k === "V") return toggleMic();
    if (k === "c" || k === "C") return playClip();
    if (k === "t" || k === "T") { ev.preventDefault(); const t = document.getElementById("typed"); if (t) t.focus(); }
  }
});

ticker(tickCountdowns);

subscribe("/events/stage", (snap) => {
  const prev = S && S.engine.readout.view_id;
  S = snap;
  setupRecordings(S.recordings);
  render();
  if (flipT0 !== null && S.engine.readout.view_id !== prev) { lastFlipMs = since(flipT0); flipT0 = null; window.__lastFlipMs = lastFlipMs; render(); }
  window.__S = S;
}, (s) => { conn = s; });
