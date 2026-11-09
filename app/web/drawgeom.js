/* Classic script (no ES modules: app.js is a classic script too).
 * Publishes one namespace, `DrawGeom`, so the geometry can be used and tested
 * without the DOM. Everything below is pure. */
(function (root) {
'use strict';
/**
 * Geometry of drawn annotations, free of DOM so it can be tested directly.
 *
 * A stroke keeps its ORIGINAL world points plus an affine transform `m`
 * (six numbers [a, b, c, d, e, f], mapping p -> (a*x + c*y + e, b*x + d*y + f)).
 * Moving, scaling and rotating only update `m`; the original geometry is never
 * rewritten, so a stroke can always be restored exactly.
 *
 * Composition order matters, and the functions below apply it explicitly:
 *   translate by (dx, dy):        M' = T(dx, dy) · M
 *   scale by f about anchor a:    M' = T(a) · S(f) · T(-a) · M
 *   rotate by θ about pivot c:    M' = T(c) · R(θ) · T(-c) · M
 * The anchor/pivot is the fixed point of its own step, which is exactly the
 * behaviour a user expects from a handle.
 */

let nextStrokeId = 1;
function newStrokeId() {
  return nextStrokeId++;
}

const IDENTITY = [1, 0, 0, 1, 0, 0];

/** Product of two affine matrices, A · B (apply B first, then A). */
function mul(A, B) {
  const [a1, b1, c1, d1, e1, f1] = A;
  const [a2, b2, c2, d2, e2, f2] = B;
  return [
    a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
    a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
    a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1,
  ];
}

function applyMatrix(M, p) {
  return { x: M[0] * p.x + M[2] * p.y + M[4], y: M[1] * p.x + M[3] * p.y + M[5] };
}

function matrixOf(stroke) {
  return stroke.m && stroke.m.length === 6 ? stroke.m : IDENTITY;
}

/** The stroke's points after its transform, in world coordinates. */
function transformedPoints(stroke) {
  const M = matrixOf(stroke);
  const pts = stroke.points || [];
  if (M === IDENTITY) return pts;
  return pts.map((p) => applyMatrix(M, p));
}

/** Translate by (dx, dy) world units. Returns a new stroke. */
function translated(stroke, dx, dy) {
  return { ...stroke, m: mul([1, 0, 0, 1, dx, dy], matrixOf(stroke)) };
}

/** Scale by `factor` about the world anchor (ax, ay); the anchor stays put. */
function scaled(stroke, factor, ax, ay) {
  const S = [factor, 0, 0, factor, 0, 0];
  const step = mul(translation(ax, ay), mul(S, translation(-ax, -ay)));
  return { ...stroke, m: mul(step, matrixOf(stroke)) };
}

/** Rotate by `angle` radians about the world pivot (cx, cy). */
function rotated(stroke, angle, cx, cy) {
  const c = Math.cos(angle), s = Math.sin(angle);
  const R = [c, s, -s, c, 0, 0];
  const step = mul(translation(cx, cy), mul(R, translation(-cx, -cy)));
  return { ...stroke, m: mul(step, matrixOf(stroke)) };
}

function translation(x, y) {
  return [1, 0, 0, 1, x, y];
}

/** Scale factor of the transform (geometric mean of the axis scales). */
function scaleOf(stroke) {
  const [a, b, c, d] = matrixOf(stroke);
  return Math.sqrt(Math.abs(a * d - b * c));
}

/**
 * Bake the transform into the points and reset it. Used before erasing, which
 * cuts the points themselves and must work in the final geometry.
 */
function baked(stroke) {
  if (matrixOf(stroke) === IDENTITY) return stroke;
  return { ...stroke, points: transformedPoints(stroke), m: undefined };
}

function centroid(stroke) {
  const pts = transformedPoints(stroke);
  if (!pts.length) return { x: 0, y: 0 };
  let sx = 0, sy = 0;
  for (const p of pts) { sx += p.x; sy += p.y; }
  return { x: sx / pts.length, y: sy / pts.length };
}

/** Axis-aligned bounding box of the transformed points, padded in world units. */
function bounds(stroke, padWorld = 0) {
  const pts = transformedPoints(stroke);
  if (!pts.length) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of pts) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX: minX - padWorld, minY: minY - padWorld,
           maxX: maxX + padWorld, maxY: maxY + padWorld };
}

/** Distance in world units from p to segment ab. */
function distanceToSegment(p, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0;
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

/**
 * Distance from p to the drawn geometry, in world units. `textBox` is the
 * label's size in world units; the caller measures the font, since it owns the
 * canvas.
 */
function strokeDistance(stroke, p, textBox) {
  const pts = transformedPoints(stroke);
  if (!pts.length) return Infinity;

  if (stroke.tool === 'marker') {
    return Math.hypot(p.x - pts[0].x, p.y - pts[0].y);
  }

  if (stroke.tool === 'text') {
    const box = textBox || { w: 0, h: 0 };
    const x0 = pts[0].x, y0 = pts[0].y;
    const x1 = x0 + box.w, y1 = y0 + box.h;
    if (p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1) return 0;
    const nx = Math.min(Math.max(p.x, x0), x1);
    const ny = Math.min(Math.max(p.y, y0), y1);
    return Math.hypot(p.x - nx, p.y - ny);
  }

  if (pts.length === 1) return Math.hypot(p.x - pts[0].x, p.y - pts[0].y);

  if (stroke.tool === 'line' || stroke.tool === 'arrow') {
    return distanceToSegment(p, pts[0], pts[pts.length - 1]);
  }

  if (stroke.tool === 'rect') {
    const a = pts[0], b = pts[pts.length - 1];
    const corners = [a, { x: b.x, y: a.y }, b, { x: a.x, y: b.y }, a];
    let best = Infinity;
    for (let i = 1; i < corners.length; i++) {
      best = Math.min(best, distanceToSegment(p, corners[i - 1], corners[i]));
    }
    return best;
  }

  if (stroke.tool === 'circle') {
    const a = pts[0], b = pts[pts.length - 1];
    const radius = Math.hypot(b.x - a.x, b.y - a.y);
    return Math.abs(Math.hypot(p.x - a.x, p.y - a.y) - radius);
  }

  // pen, dashed pen: closest segment of the polyline
  let best = Infinity;
  for (let i = 1; i < pts.length; i++) {
    best = Math.min(best, distanceToSegment(p, pts[i - 1], pts[i]));
  }
  return best;
}

/** Dash pattern in screen pixels for a given stroke width. */
function dashPattern(width) {
  return [Math.max(6, width * 3), Math.max(4, width * 2)];
}

/** Two barbs of an arrow head at tip b, for the direction a → b. */
function arrowHead(a, b, length, spread = Math.PI / 7) {
  const angle = Math.atan2(b.y - a.y, b.x - a.x);
  return [
    { x: b.x - length * Math.cos(angle - spread), y: b.y - length * Math.sin(angle - spread) },
    { x: b.x - length * Math.cos(angle + spread), y: b.y - length * Math.sin(angle + spread) },
  ];
}

/**
 * Split a polyline around a disc: keep the runs outside the eraser. Each run
 * keeps at least two points.
 */
function cutPolyline(points, center, radius) {
  const runs = [];
  let run = [];
  for (const p of points) {
    if (Math.hypot(p.x - center.x, p.y - center.y) <= radius) {
      if (run.length > 1) runs.push(run);
      run = [];
    } else {
      run.push(p);
    }
  }
  if (run.length > 1) runs.push(run);
  return runs;
}

const api = {
  newStrokeId, mul, applyMatrix, transformedPoints, translated, scaled, rotated,
  scaleOf, baked, centroid, bounds, distanceToSegment, strokeDistance,
  dashPattern, arrowHead, cutPolyline,
};
root.DrawGeom = api;
if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
