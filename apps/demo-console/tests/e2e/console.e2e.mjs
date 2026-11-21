// Browser check for the definition of done: every beat by one key, a flip re-renders < 1 s,
// a switch to the recording < 10 s, phones vote through real taps. Screenshots land in $OUT.
// Run: CHROME=/usr/bin/google-chrome BASE=http://127.0.0.1:8765 OUT=/tmp/shots node tests/e2e/console.e2e.mjs
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const BASE = process.env.BASE || "http://127.0.0.1:8765";
const OUT = process.env.OUT || "/tmp/shots";
fs.mkdirSync(OUT, { recursive: true });
const results = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const post = (p, b) => fetch(BASE + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }).then((r) => r.json());

const browser = await puppeteer.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
try {
  for (const b of [1, 2, 3]) await post("/api/reset", { beat: b });
  const stage = await browser.newPage();
  await stage.setViewport({ width: 1920, height: 1080 });
  const errors = [];
  stage.on("pageerror", (e) => errors.push(String(e)));
  stage.on("response", (r) => {
    const u = new URL(r.url());
    // Recordings are captured on Nov 30; until then their 404s are expected and the slate shows instead.
    if (r.status() >= 400 && !u.pathname.startsWith("/recordings/") && u.pathname !== "/favicon.ico") errors.push(`${r.status()} ${u.pathname}`);
  });
  await stage.goto(BASE + (process.env.HUD === "0" ? "/" : "/?hud=1"), { waitUntil: "networkidle2" });
  await stage.waitForFunction(() => window.__S);
  const shot = (name, page = stage) => page.screenshot({ path: `${OUT}/${name}.png` });
  const key = async (k) => { await stage.keyboard.press(k); await sleep(250); };

  // beat 1 by one key
  let t0 = Date.now(); await key("1");
  await stage.waitForFunction(() => window.__S.beat === 1);
  results.beat1_key_ms = Date.now() - t0;
  await shot("b1-0-request");
  await key("Space"); await shot("b1-1-sparky");
  await key("Space"); await shot("b1-2-brief");
  await key("Space"); await shot("b1-3-menu");
  await key("Space"); await shot("b1-4-join");

  // three phones join by the QR url and vote with real taps
  const phones = [];
  for (let i = 0; i < 3; i++) {
    const ctx = await browser.createBrowserContext();
    const p = await ctx.newPage();
    await p.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await p.goto(BASE + "/p", { waitUntil: "networkidle2" });
    phones.push(p);
  }
  await key("Space"); // vote: opens the poll
  for (const p of phones) await p.waitForSelector(".btn-vote", { timeout: 4000 });
  await shot("phone-ballot-0", phones[0]); await shot("phone-ballot-1", phones[1]); await shot("phone-ballot-2", phones[2]);
  for (const [i, p] of phones.entries()) { const btns = await p.$$(".btn-vote"); await btns[i % btns.length].tap(); }
  await sleep(500);
  await post("/api/sim/voters", { n: 17 });
  await sleep(400);
  await shot("b1-5-vote");
  await shot("phone-voted-0", phones[0]);
  await key("Space"); await sleep(300); await shot("b1-6-tally-owner");
  await key("a"); await sleep(300); await shot("b1-6b-tally-auto");
  await key("Space"); await shot("b1-7-tortilla");
  await key("Space"); await shot("b1-8-approve");
  await key("Space"); await shot("b1-9-order");
  await key("p"); await sleep(200); await shot("b1-proof"); await key("p");

  // beat 2 by one key; flip timing
  t0 = Date.now(); await key("2");
  await stage.waitForFunction(() => window.__S.beat === 2);
  results.beat2_key_ms = Date.now() - t0;
  await shot("b2-0-map");
  await stage.evaluate(() => { window.__lastFlipMs = null; });
  await stage.keyboard.press("m");
  await stage.waitForFunction(() => window.__lastFlipMs !== null, { timeout: 2000 });
  results.flip_rerender_ms = await stage.evaluate(() => window.__lastFlipMs);
  await sleep(200); await shot("b2-1-marketing");
  await stage.evaluate(() => { window.__lastFlipMs = null; });
  await stage.keyboard.press("s");
  await stage.waitForFunction(() => window.__lastFlipMs !== null, { timeout: 2000 });
  results.flip2_rerender_ms = await stage.evaluate(() => window.__lastFlipMs);
  await sleep(200); await shot("b2-2-supply");
  await key("n"); await shot("b2-3-partner-pending"); await key("n");
  await key("d"); await sleep(200); await shot("b2-4-drill");

  // recording switch timing (beat 2)
  t0 = Date.now();
  await stage.keyboard.press("r");
  await stage.waitForFunction(() => document.querySelector('.rec-wrap[data-beat="2"]')?.classList.contains("is-on"), { timeout: 10000 });
  results.recording_switch_ms = Date.now() - t0;
  await sleep(300); await shot("b2-rec");
  await key("l");

  // beat 3 by one key; typed fallback timing; the room is Jen
  t0 = Date.now(); await key("3");
  await stage.waitForFunction(() => window.__S.beat === 3);
  results.beat3_key_ms = Date.now() - t0;
  t0 = Date.now();
  await key("t");
  await stage.keyboard.type("I'm out of my coffee and the soft bread, and get some sour cream.");
  await stage.keyboard.press("Enter");
  await stage.waitForFunction(() => window.__S.care.request !== null, { timeout: 5000 });
  results.typed_fallback_ms = Date.now() - t0;
  await sleep(250); await shot("b3-0-today");
  await stage.evaluate(() => document.activeElement && document.activeElement.blur());
  await key("Space"); await shot("b3-1-profile");
  await key("Space"); await sleep(200); await shot("b3-2-care");
  await key("Space");
  await key("t");
  await stage.keyboard.type("And a little space heater, the bedroom gets cold at night.");
  await stage.keyboard.press("Enter");
  await sleep(300);
  await stage.evaluate(() => document.activeElement && document.activeElement.blur());
  for (const p of phones) await p.waitForSelector(".btn-approve", { timeout: 4000 });
  await shot("phone-jen", phones[0]);
  await (await phones[0].$(".btn-approve")).tap();
  await (await phones[1].$(".btn-counter")).tap();
  await (await phones[2].$(".btn-approve")).tap();
  await sleep(400); await shot("b3-3-heater");
  await key("Space"); await sleep(300); await shot("b3-4-decision");
  await key("Space"); await shot("b3-5-lock");
  await key("Space"); await shot("b3-6-scam");
  await key("Space"); await shot("b3-7-month");
  results.page_errors = errors;
  results.pass = results.flip_rerender_ms < 1000 && results.flip2_rerender_ms < 1000 && results.recording_switch_ms < 10000 &&
    results.typed_fallback_ms < 5000 && errors.length === 0;
} finally {
  await browser.close();
}
console.log(JSON.stringify(results, null, 1));
process.exit(results.pass ? 0 : 1);
