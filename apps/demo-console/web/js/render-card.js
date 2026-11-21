// One renderer for every Card@0 (ballot, approval, over_cap, digest, readback) on stage and on phones.
// It prints line text exactly as K11 wrote it. Numbers are never parsed, formatted or combined here:
// a line with a number carries claim_ref, and the claim's label and verifier ride beside it as a chip.
import { h } from "./dom.js";
import { tileArt } from "./art.js";

const MARK_ICON = { lock: "\u{1F512}", sponsored: "Sponsored", quote: "", info: "i", warn: "!", ok: "✓" };

export function labelChip(claim) {
  if (!claim) return null;
  const kind = claim.label.startsWith("public:") ? "public" : claim.label.startsWith("observed:") ? "observed" : "synthetic";
  return h("span", { class: `chip chip-${kind}`, title: `verified by ${claim.verified_by}` }, claim.label);
}

export function renderCard(card, opts = {}) {
  const claims = Object.fromEntries((card.claims || []).map((c) => [c.id, c]));
  const root = h("article", { class: `card card-${card.kind} role-${card.audience.role} ${opts.className || ""}`, "data-card": card.card_id,
    "aria-label": card.headline || card.kind });
  if (card.headline && !opts.noHeadline) root.append(h("h2", { class: "card-headline" }, card.headline));
  const list = h("div", { class: "card-sections" });
  let tileIndex = 0;
  for (const s of card.sections) {
    const picked = opts.selected && s.option && opts.selected === s.option;
    // A section that carries an option (a cart) is a product tile: art, name, shelf price, details.
    const tile = Boolean(s.option) && !opts.plain;
    const sec = h("section", { class: `card-section ${tile ? "tile" : ""} ${picked ? "is-picked" : ""}`, "data-option": s.option || null });
    const body = tile ? h("div", { class: "tile-body" }) : sec;
    if (tile) sec.append(tileArt(tileIndex++), body);
    body.append(h("h3", {}, s.title));
    const ul = h("ul", {});
    let lead = tile;
    for (const line of s.lines) {
      // The shelf price: the tile's first money claim (a claim whose value is {amount, currency}); read, never computed.
      const v = line.claim_ref && claims[line.claim_ref] ? claims[line.claim_ref].value : null;
      const isLead = lead && !line.mark && v !== null && typeof v === "object" && "amount" in v;
      if (isLead) lead = false;
      const li = h("li", { class: `line ${line.mark ? "mark-" + line.mark : ""} ${isLead ? "is-lead" : ""}` });
      if (line.mark && MARK_ICON[line.mark]) li.append(h("span", { class: "mark", "aria-hidden": "true" }, MARK_ICON[line.mark]));
      li.append(h("span", { class: "text" }, line.text));
      if (line.claim_ref) li.append(labelChip(claims[line.claim_ref]));
      ul.append(li);
    }
    body.append(ul);
    if (opts.onAction && s.option) {
      const vote = (card.actions || []).find((a) => a.option === s.option && a.kind === "vote");
      if (vote) body.append(h("button", { class: `btn btn-vote ${picked ? "is-on" : ""}`, disabled: opts.disabled, onclick: () => opts.onAction(vote) },
        picked ? "Your pick ✓" : vote.label));
    }
    list.append(sec);
  }
  root.append(list);
  if (opts.onAction) {
    const extra = (card.actions || []).filter((a) => !(a.kind === "vote" && a.option && card.sections.some((s) => s.option === a.option)));
    if (extra.length) root.append(renderActions(extra, opts));
  } else if (opts.showActions && card.actions && card.actions.length) {
    root.append(h("div", { class: "card-actions is-static" }, card.actions.map((a) => h("span", { class: `btn btn-${a.kind}` }, a.label))));
  }
  return root;
}

function renderActions(actions, opts) {
  const box = h("div", { class: "card-actions" });
  const picks = actions.filter((a) => a.kind === "pick_add");
  if (picks.length) {
    box.append(h("p", { class: "hint" }, "Ask for one thing to add:"),
      h("div", { class: "pick-row" }, picks.map((a) => h("button", { class: `btn btn-pick ${opts.selected === a.action_id ? "is-on" : ""}`,
        disabled: opts.disabled, onclick: () => opts.onAction(a) }, a.label))));
  }
  for (const a of actions.filter((x) => x.kind === "request" || x.kind === "free_text")) {
    const input = h("input", { type: "text", maxlength: a.max_len, placeholder: a.kind === "request" ? "Add queso?" : "Note for the owner",
      "aria-label": a.label });
    box.append(h("form", { class: "text-row", onsubmit: (ev) => { ev.preventDefault(); if (input.value.trim()) { opts.onAction(a, input.value.trim()); input.value = ""; } } },
      h("label", {}, a.label, input), h("button", { class: "btn btn-send", type: "submit", disabled: opts.disabled }, "Send")));
  }
  const decisions = actions.filter((a) => ["approve", "counter", "defer", "decline", "vote"].includes(a.kind));
  if (decisions.length) {
    box.append(h("div", { class: "decision-row" }, decisions.map((a) => h("button", {
      class: `btn btn-${a.kind} ${opts.selected === a.action_id ? "is-on" : ""}`, disabled: opts.disabled, onclick: () => opts.onAction(a) },
      opts.selected === a.action_id ? `${a.label} ✓` : a.label))));
  }
  return box;
}
