// D02 phone: join by QR, get a role, see that role's K11 card only, send a poll.response.
// In beat 3 every phone becomes Jen and gets the over-cap card ("room is Jen", B ask 7).
import { h, post, store, subscribe } from "./dom.js";
import { renderCard } from "./render-card.js";
import { closesAtWall, mmss, secondsLeftWall, spanWall, tickCountdowns, ticker } from "./clock.js";
import { tileArt } from "./art.js";

const app = document.getElementById("app");
let me = null, V = null, localPick = null, sending = false, endMs = null, spanMs = null;

async function join() {
  const fromLink = new URLSearchParams(location.search).get("b");
  me = await post("/api/join", { member_hash: store("fh.member"), ballot_token: fromLink || store("fh.token") });
  store("fh.member", me.member_hash);
  store("fh.token", me.ballot_token);
  if (fromLink) history.replaceState(null, "", "/p");  // the ballot link is single use; keep it out of the address bar
  let last = "";
  subscribe(`/events/phone?m=${encodeURIComponent(me.member_hash)}`, (v) => {
    // Redraw only when this phone's own view changed: other people's votes must not wipe a half-typed request.
    // The sim clock changes on every message, so it is left out of the comparison.
    const key = JSON.stringify({ ...v, clock: null });
    if (v.closes_at && v.clock) { endMs = closesAtWall(v.closes_at, v.clock); spanMs = spanWall(v.opened_at, v.closes_at, v.clock); }
    if (key === last) return;
    last = key; V = v; render();
  }, (s) => {
    document.body.dataset.conn = s;
  });
}

async function act(action, text) {
  if (sending) return;
  sending = true;
  try {
    if (action.kind === "pick_add") localPick = action.action_id;
    if (navigator.vibrate) navigator.vibrate(18);
    await post("/api/act", { member_hash: me.member_hash, ballot_token: me.ballot_token, action_id: action.action_id, text });
  } catch (e) {
    flash(e.message);
  } finally {
    sending = false;
    render();
  }
}

function flash(msg) {
  const t = h("div", { class: "toast" }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 3000);
}

const MARK = `<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M2 17 A10 10 0 0 1 22 17 Z" fill="#ffc940"/><circle cx="8" cy="11" r="2.2" fill="#ff5b3a"/><circle cx="14" cy="10" r="2.2" fill="#93d36b"/></svg>`;

function render() {
  if (!V) return;
  const head = h("header", { class: "who" }, h("span", { class: "mark", html: MARK }), h("span", { class: "role-badge" }, V.as || "Joining…"));
  let body;
  if (V.screen === "join") body = h("div", { class: "wait" }, h("p", { class: "big" }, "Joining…"));
  else if (V.screen === "wait") body = h("div", { class: "wait" }, tileArt(1), h("p", { class: "big" }, "You're in."), h("p", { class: "fine" }, "Your ballot shows up here when the vote opens."));
  else if (V.screen === "result") body = h("div", { class: "wait" }, tileArt(0), h("p", { class: "big" }, V.text), h("p", { class: "fine" }, "Thanks for voting. Watch the big screen."));
  else {
    const kid = V.role === "kid";
    body = h("div", { class: `ballot ${kid ? "is-kid" : ""}` },
      h("div", { class: "timer-wrap" }, h("span", { class: "timer-label" }, V.voted ? "Vote in. Change it until time's up." : "Time left to vote"),
        h("span", { class: "timer", "data-closes-wall": endMs ?? "", "data-span-ms": spanMs ?? "" }, mmss(secondsLeftWall(endMs))), h("i", { class: "timer-bar" })),
      V.card.headline ? h("h1", { class: "q" }, V.card.headline) : null,
      renderCard({ ...V.card, headline: null }, { onAction: act, selected: V.your_vote || localPick, disabled: sending, className: "on-phone" }),
      localPick && V.card.kind === "ballot" ? h("p", { class: "fine" }, "Your add-on request went to the owner.") : null);
  }
  const typing = [...app.querySelectorAll("input")].map((i) => [i.getAttribute("aria-label"), i.value]);
  app.replaceChildren(head, body);
  for (const [label, value] of typing) { const i = app.querySelector(`input[aria-label="${label}"]`); if (i && value) i.value = value; }
  tickCountdowns();
}

ticker(tickCountdowns);

join().catch((e) => { app.replaceChildren(h("p", { class: "big" }, "Couldn't join: ", e.message)); });
