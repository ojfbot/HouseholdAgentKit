// Time arithmetic for countdowns. Allowlisted by the no-business-math lint: it only ever touches time.
// Poll@1 rule: countdowns run off the message's sim clock (stage rate 20), never the wall clock alone.
// The wall moment the poll closes = now (when the message arrives) + (closes_at - clock.sim_now) / clock.rate.
// Anchored on this device's receipt time, not on clock.wall_now, so a phone whose clock is off still counts right.
export function closesAtWall(closesAtSim, clock) {
  if (!closesAtSim || !clock) return null;
  return Date.now() + (Date.parse(closesAtSim) - Date.parse(clock.sim_now)) / clock.rate;
}

export function secondsLeftWall(endMs) {
  if (endMs === null || endMs === undefined || endMs === "") return null;
  const left = Math.ceil((endMs - Date.now()) / 1000);
  return left > 0 ? left : 0;
}

export function mmss(s) {
  if (s === null) return "";
  const m = Math.floor(s / 60);
  const r = String(s % 60).padStart(2, "0");
  return `${m}:${r}`;
}

export function stamp() {
  return performance.now();
}

export function since(t0) {
  return Math.round(performance.now() - t0);
}

export function ticker(fn, ms = 250) {
  const id = setInterval(fn, ms);
  return () => clearInterval(id);
}

// How long the poll runs on this screen, in wall ms: (closes_at - opened_at) / rate. Feeds the countdown ring.
export function spanWall(openedAtSim, closesAtSim, clock) {
  if (!openedAtSim || !closesAtSim || !clock) return null;
  return (Date.parse(closesAtSim) - Date.parse(openedAtSim)) / clock.rate;
}

export function tickCountdowns() {
  for (const el of document.querySelectorAll("[data-closes-wall]")) {
    const v = el.dataset.closesWall;
    const end = v ? +v : null;
    el.textContent = mmss(secondsLeftWall(end));
    const span = el.dataset.spanMs ? +el.dataset.spanMs : 0;
    const ring = el.closest(".ring, .timer-wrap");
    if (ring && span && end) ring.style.setProperty("--left", String(Math.max(0, Math.min(1, (end - Date.now()) / span))));
    if (ring && end !== null) ring.classList.toggle("is-ending", secondsLeftWall(end) <= 10);
  }
}
