// Product-tile illustrations for cart options. Decoration only: no words, no numbers, nothing a contract carries.
// One taco, three moods, picked by the tile's position (the hello-world menu is always repeat, fresh, savings).
const TACO = (tone) => `
  <path d="M14 92 A56 56 0 0 1 126 92 Z" fill="#f2c46b"/>
  <path d="M14 92 A56 56 0 0 1 126 92" fill="none" stroke="#c98f2e" stroke-width="5" stroke-linecap="round"/>
  <path d="M26 66 q8 -12 16 -2 q8 -12 16 -2 q8 -12 16 -2 q8 -12 16 -2 q8 -12 16 -2 q6 -8 12 2" fill="none" stroke="#93d36b" stroke-width="9" stroke-linecap="round"/>
  <circle cx="44" cy="58" r="7" fill="#ff5b3a"/><circle cx="72" cy="52" r="7" fill="#ff5b3a"/><circle cx="98" cy="58" r="7" fill="#ff5b3a"/>
  <path d="M56 46 l10 -10 M84 46 l8 -12" stroke="#f4ecdc" stroke-width="5" stroke-linecap="round"/>
  <circle cx="122" cy="30" r="20" fill="${tone}"/>`;

const BADGE = [
  // repeat
  `<path d="M113 27 a9 9 0 1 1 3 9" fill="none" stroke="#14110d" stroke-width="4" stroke-linecap="round"/><path d="M108 22 l5 6 l6 -4" fill="none" stroke="#14110d" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`,
  // leaf
  `<path d="M112 40 C110 26 120 18 133 20 C134 33 126 41 112 40 Z" fill="#14110d"/><path d="M112 40 L126 26" stroke="${"#93d36b"}" stroke-width="2.5"/>`,
  // price tag
  `<path d="M110 30 L120 20 H133 V33 L123 43 Z" fill="#14110d"/><circle cx="128" cy="25" r="2.6" fill="#ffc940"/>`,
];
const TONES = ["#ff5b3a", "#93d36b", "#ffc940"];

export function tileArt(i) {
  const k = i % 3;
  const box = document.createElement("div");
  box.className = "tile-art";
  box.setAttribute("aria-hidden", "true");
  box.innerHTML = `<svg viewBox="0 0 150 100" xmlns="http://www.w3.org/2000/svg">${TACO(TONES[k])}${BADGE[k]}</svg>`;
  return box;
}
