// Frame-pure, zero-lookback-at-render-time tracking interpolation.
// Fits a small symmetric neighbourhood once, then samples a C1 monotone cubic.
// Source keyframes are retained; corrections are bounded in output pixels.
export type TrackingKey = number[];
type Track = { keys: number[][]; slopes: number[][] };
const prepared = new WeakMap<number[][], Map<string, Track>>();
const clamp = (x: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, x));

const fitCenter = (keys: number[][], i: number, column: number) => {
  const lo = Math.max(0, i - 2), hi = Math.min(keys.length - 1, i + 2);
  if (hi - lo < 3) return keys[i][column];
  const scale = Math.max(0.01, keys[hi][0] - keys[lo][0]);
  const mat = Array.from({ length: 3 }, () => [0, 0, 0, 0]);
  for (let j = lo; j <= hi; j++) {
    const u = (keys[j][0] - keys[i][0]) / scale;
    const weight = Math.exp(-4 * u * u), basis = [1, u, u * u];
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) mat[r][c] += weight * basis[r] * basis[c];
      mat[r][3] += weight * basis[r] * keys[j][column];
    }
  }
  for (let c = 0; c < 3; c++) {
    let pivot = c;
    for (let r = c + 1; r < 3; r++) if (Math.abs(mat[r][c]) > Math.abs(mat[pivot][c])) pivot = r;
    [mat[c], mat[pivot]] = [mat[pivot], mat[c]];
    if (Math.abs(mat[c][c]) < 1e-12) return keys[i][column];
    const den = mat[c][c];
    for (let k = c; k < 4; k++) mat[c][k] /= den;
    for (let r = 0; r < 3; r++) if (r !== c) {
      const v = mat[r][c];
      for (let k = c; k < 4; k++) mat[r][k] -= v * mat[c][k];
    }
  }
  return mat[0][3];
};

export const prepareTracking = (source: number[][], width = 1440, height = 1080): Track => {
  const cacheKey = width + ":" + height;
  let cache = prepared.get(source);
  if (!cache) { cache = new Map(); prepared.set(source, cache); }
  const hit = cache.get(cacheKey);
  if (hit) return hit;
  const raw = source.filter((k) => k.length >= 5 && k.slice(0, 5).every(Number.isFinite))
    .map((k) => k.slice(0, 5)).sort((a, b) => a[0] - b[0])
    .filter((k, i, a) => i === 0 || k[0] > a[i - 1][0]);
  const keys = raw.map((k) => [...k]);
  if (keys.length >= 5) for (let i = 1; i < keys.length - 1; i++) {
    for (let c = 1; c <= 4; c++) {
      const pixels = c % 2 === 1 ? width : height;
      const correction = clamp(fitCenter(raw, i, c) - raw[i][c], -1.25 / pixels, 1.25 / pixels);
      keys[i][c] = raw[i][c] + correction;
    }
  }
  const slopes = keys.map(() => [0, 0, 0, 0]);
  for (let c = 1; c <= 4; c++) {
    const secants = keys.slice(1).map((k, i) => (k[c] - keys[i][c]) / (k[0] - keys[i][0]));
    if (keys.length > 1) { slopes[0][c - 1] = secants[0]; slopes[keys.length - 1][c - 1] = secants[secants.length - 1]; }
    for (let i = 1; i < keys.length - 1; i++) {
      const a = secants[i - 1], b = secants[i];
      if (a * b <= 0) slopes[i][c - 1] = 0;
      else {
        const h0 = keys[i][0] - keys[i - 1][0], h1 = keys[i + 1][0] - keys[i][0];
        const w0 = 2 * h1 + h0, w1 = h1 + 2 * h0;
        slopes[i][c - 1] = (w0 + w1) / (w0 / a + w1 / b);
      }
    }
  }
  const result = { keys, slopes };
  cache.set(cacheKey, result);
  return result;
};

export const sampleTracking = (source: number[][], t: number, width = 1440, height = 1080): number[] | null => {
  const { keys, slopes } = prepareTracking(source, width, height);
  if (!keys.length) return null;
  if (t <= keys[0][0]) return keys[0].slice(1);
  if (t >= keys[keys.length - 1][0]) return keys[keys.length - 1].slice(1);
  let lo = 0, hi = keys.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (keys[mid][0] > t) hi = mid; else lo = mid; }
  const a = keys[lo], b = keys[hi], dt = b[0] - a[0], u = (t - a[0]) / dt;
  const u2 = u * u, u3 = u2 * u;
  return a.slice(1).map((v, i) => {
    const value = (2 * u3 - 3 * u2 + 1) * v + (u3 - 2 * u2 + u) * dt * slopes[lo][i]
      + (-2 * u3 + 3 * u2) * b[i + 1] + (u3 - u2) * dt * slopes[hi][i];
    return i >= 2 ? Math.max(1e-6, value) : value;
  });
};

