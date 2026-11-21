// Tiny DOM helpers shared by stage and phone. No framework, no build step: the console runs offline on the stage host.
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

export function svg(tag, attrs = {}, ...kids) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
}

export async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

export function subscribe(url, onData, onStatus) {
  let es;
  const open = () => {
    es = new EventSource(url);
    es.onopen = () => onStatus && onStatus("connected");
    es.onmessage = (ev) => onData(JSON.parse(ev.data));
    es.onerror = () => { onStatus && onStatus("reconnecting"); es.close(); setTimeout(open, 800); };
  };
  open();
  return () => es && es.close();
}

export function store(key, value) {
  // Per-viewer convenience only (phone keeps its member hash across reloads). Storage can throw; never rely on it.
  try {
    if (value === undefined) return window.localStorage.getItem(key);
    window.localStorage.setItem(key, value);
  } catch (e) { return null; }
  return value;
}
