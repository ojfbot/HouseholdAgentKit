// Presentation geometry only. Allowlisted by the no-business-math lint: inputs are positions and shares that
// K10 and E12 already computed (0..1); this file maps them to pixels and percentages, nothing else.
export function pct(share) {
  return `${Math.max(0, Math.min(1, share)) * 100}%`;
}

export function series(points, box) {
  // Evenly spaced x, y from each point's precomputed `pos` (0..1).
  const n = points.length > 1 ? points.length - 1 : 1;
  return points.map((p, i) => [box.left + (box.width * i) / n, box.top + box.height * (1 - p.pos)]);
}

export function place(pos, box) {
  return { x: box.left + pos.x * box.width, y: box.top + (1 - pos.y) * box.height };
}
