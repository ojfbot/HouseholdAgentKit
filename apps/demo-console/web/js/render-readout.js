// E19 engine map + E16 readout page, rendered from readout-view@0: the host's E16 adapter builds it from Fork G's
// Readout@0 (e16_view.py). Ranks, tiers, cells, positions and display strings all arrive ready; this file lays them out.
import { h, svg } from "./dom.js";
import { labelChip } from "./render-card.js";
import { place } from "./layout.js";

export function renderEngine(eng, { onDrill, onFlip } = {}) {
  const ro = eng.readout;
  const claims = Object.fromEntries((ro.claims || []).map((c) => [c.id, c]));
  const root = h("div", { class: `engine ${ro.kind === "pending" ? "is-pending" : ""}` });

  const lens = ro.profile.lens === "partner" ? "Partner lens" : "In-house lens";
  root.append(h("header", { class: "engine-head" },
    h("div", { class: "engine-profile" }, h("span", { class: "label" }, lens), h("strong", {}, ro.profile.function)),
    h("p", { class: "answer-first" }, ro.answer_first),
    renderFlips(eng, onFlip)));

  if (ro.kind === "pending") {
    root.append(h("div", { class: "pending-panel" },
      h("p", {}, "Waiting on: ", (ro.pending?.needs || []).join(", ")),
      h("p", { class: "muted" }, `Expected ${ro.pending?.eta || "with run 1"}. Until then the beat's recording covers the lens flip.`)));
    root.append(renderDelta(eng.last_delta));
    return root;
  }

  const grid = h("div", { class: "engine-grid" });
  grid.append(renderLadder(ro, onDrill), renderQuad(ro, claims, onDrill), renderPortfolio(ro, claims, onDrill));
  root.append(grid);
  if (ro.clamps && ro.clamps.length) {
    root.append(h("p", { class: "clamps" }, h("span", { class: "mark" }, "⚖"),
      " Fairness-floor clamps under this profile: ", h("strong", {}, claims["clamps.count"].display), ". Protected families were not down-weighted. ",
      labelChip(claims["clamps.count"])));
  }
  root.append(renderDelta(eng.last_delta));
  if (eng.drill && eng.drill_view) root.append(renderDrill(eng.drill, eng.drill_view, onDrill));
  return root;
}

function renderFlips(eng, onFlip) {
  const cur = eng.readout.profile;
  return h("nav", { class: "flips", "aria-label": "Control flips" }, (eng.flips || []).map((f) => {
    const r = f.request;
    const on = (r.op === "switch" && cur.lens !== "partner" && cur.profile_id === r.value) || (r.op === "lens" && cur.lens === r.value);
    return h("button", { class: `flip ${on ? "is-on" : ""}`, onclick: onFlip ? () => onFlip(r) : null }, f.label);
  }));
}

function renderLadder(ro, onDrill) {
  return h("section", { class: "panel ladder" }, h("h3", {}, "Value ladder"),
    ro.ladder.slice().reverse().map((t) => h("div", { class: `rung tier-${t.tier}` }, h("h4", {}, t.label),
      h("div", { class: "pills" }, t.families.map((f) => h("button", {
        class: `pill ${f.in_portfolio ? "is-in" : ""} ${f.anchor ? "is-anchor" : ""}`, title: f.title, onclick: onDrill ? () => onDrill(f.family_id) : null },
        f.family_id))))));
}

function renderQuad(ro, claims, onDrill) {
  const W = 620, H = 440, box = { left: 46, top: 18, width: W - 70, height: H - 66 };
  const q = ro.quad;
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "quad", role: "img", "aria-label": "Two by two of problem families" });
  const mid = place({ x: 0.5, y: 0.5 }, box);
  s.append(svg("rect", { x: box.left, y: box.top, width: box.width, height: box.height, class: "quad-frame" }),
    svg("line", { x1: mid.x, y1: box.top, x2: mid.x, y2: box.top + box.height, class: "quad-mid" }),
    svg("line", { x1: box.left, y1: mid.y, x2: box.left + box.width, y2: mid.y, class: "quad-mid" }));
  const corner = (pos, key, anchor) => { const p = place(pos, box); s.append(svg("text", { x: p.x, y: p.y, class: "quad-name", "text-anchor": anchor }, q.quadrants[key])); };
  corner({ x: 0.98, y: 0.97 }, "build", "end"); corner({ x: 0.98, y: 0.06 }, "prove", "end");
  corner({ x: 0.02, y: 0.97 }, "quick_proof", "start"); corner({ x: 0.02, y: 0.06 }, "park", "start");
  const xLab = place({ x: 0.5, y: 0 }, box), yLab = place({ x: 0, y: 0.5 }, box);
  s.append(svg("text", { x: xLab.x, y: H - 14, class: "quad-axis", "text-anchor": "middle" }, `${q.x.label} →`),
    svg("text", { x: 16, y: yLab.y, class: "quad-axis", "text-anchor": "middle", transform: `rotate(-90 16 ${yLab.y})` }, `${q.y.label} →`));
  // Families on the same rubric scores share a position: draw one dot per position, one label listing them.
  const rank = Object.fromEntries(ro.portfolio.map((p) => [p.family_id, p.rank]));
  const groups = new Map();
  for (const pt of q.points) {
    const k = `${pt.pos.x}|${pt.pos.y}`;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(pt);
  }
  const ordered = [...groups.values()].sort((a, b) => (a.some((p) => p.in_portfolio || p.anchor) ? 1 : 0) - (b.some((p) => p.in_portfolio || p.anchor) ? 1 : 0));
  for (const pts of ordered) {
    const anchor = pts.some((p) => p.anchor), inP = pts.some((p) => p.in_portfolio);
    // Label only the top three and the anchors; the list on the right names the rest, and every dot has a tooltip.
    const named = pts.filter((p) => p.anchor || (rank[p.family_id] || 99) <= 3).map((p) => p.family_id);
    const p = place(pts[0].pos, box);
    const right = pts[0].pos.x < 0.72;
    const g = svg("g", { class: `pt ${inP ? "is-in" : ""} ${anchor ? "is-anchor" : ""}`, transform: `translate(${p.x} ${p.y})`, tabindex: "0" },
      svg("circle", { r: anchor ? 9 : inP ? 7 : 4 }),
      named.length ? svg("text", { x: right ? 12 : -12, y: 4, class: "pt-label", "text-anchor": right ? "start" : "end" }, named.join(" · ")) : null,
      svg("title", {}, pts.map((pt) => `${pt.family_id} · ${pt.short}${pt.vas_claim && claims[pt.vas_claim] ? ` · ${claims[pt.vas_claim].display} (${claims[pt.vas_claim].label})` : ""}`).join("\n")));
    if (onDrill) g.addEventListener("click", () => onDrill((pts.find((x) => x.anchor) || pts.find((x) => x.in_portfolio) || pts[0]).family_id));
    s.append(g);
  }
  return h("section", { class: "panel quad-panel" }, h("h3", {}, "Portfolio 2×2", q.axes_provisional ? h("span", { class: "chip chip-draft" }, "axes: draft until E12") : null), s);
}

function renderPortfolio(ro, claims, onDrill) {
  return h("section", { class: "panel portfolio" }, h("h3", {}, "Top cells under this profile"),
    h("ol", {}, ro.portfolio.map((p) => h("li", { class: `row ${p.owned ? "is-owned" : ""}`, onclick: onDrill ? () => onDrill(p.family_id) : null },
      h("span", { class: "rank" }, p.rank),
      h("span", { class: "title" }, p.title, p.protected.length ? h("span", { class: "tag" }, "protected: " + p.protected.join(", ")) : null),
      h("span", { class: "vas" }, claims[p.vas_claim].display, labelChip(claims[p.vas_claim]))))));
}

function renderDrill(fid, d, onDrill) {
  const vas = d.vas;
  return h("aside", { class: "drill", role: "dialog", "aria-label": `Drill into ${fid}` },
    h("button", { class: "close", onclick: onDrill ? () => onDrill(null) : null, "aria-label": "Close" }, "×"),
    h("p", { class: "label" }, `${fid} · tier ${d.tier} · evidence ${d.evidence}`),
    h("h3", {}, d.title),
    vas ? h("p", { class: "vas" }, vas.display, " at stake ", labelChip(vas), vas.note ? h("span", { class: "muted" }, ` · ${vas.note}`) : null) : null,
    h("p", { class: "muted" }, d.owners && d.owners.length ? `Owners: ${d.owners.join(", ")}` : "", d.protected && d.protected.length ? ` · protected: ${d.protected.join(", ")}` : ""),
    h("h4", {}, "Components it needs (decomposition@2)"),
    d.components && d.components.length ? h("div", { class: "comps" }, d.components.map((c) => h("span", { class: "comp" }, h("b", {}, c.id), " ", c.name)),
      d.enhance.map((k) => h("span", { class: "comp is-enhance" }, h("b", {}, k), " enhances"))) : h("p", { class: "muted" }, "Components arrive with Fork G's readout."),
    d.adapters && d.adapters.length ? h("p", { class: "muted" }, "Through adapters until Walmart confirms: ", d.adapters.join(", ")) : null,
    d.demo_beat ? h("p", { class: "go-beat" }, `This cell is beat ${d.demo_beat}. Press ${d.demo_beat}.`) : null);
}

function renderDelta(d) {
  if (!d) return h("p", { class: "delta muted" }, "No control flipped yet. Every flip is a ControlDelta, logged and traced.");
  const codes = d.codes && d.codes.length ? ` · ${d.codes.join(", ")}` : "";
  return h("p", { class: `delta st-${d.status}` }, h("span", { class: "chip chip-draft" }, "ControlDelta@0"),
    ` ${d.delta_id} · ${d.status} · ${d.change.kind} ${d.change.from} → ${d.change.to}${codes} · engine ${d.recompute_ms ?? "?"} ms · round trip ${d.roundtrip_ms ?? "?"} ms · ${d.adapter_id}`);
}
