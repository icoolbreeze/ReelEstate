// Shared screen-space callout routing. No previous-frame state is read.
export type Point = { x: number; y: number };
export type Obstacle = ({ kind: "rect"; x: number; y: number; w: number; h: number }
  | { kind: "circle"; x: number; y: number; r: number }) & { id: string };
export type LeaderPlan = { points: Point[]; nodes: string[]; port: number; clear: boolean };
const EPS = 0.05;
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
export const overlapsRect = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }, gap = 0) =>
  a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;

export const segmentHits = (a: Point, b: Point, o: Obstacle) => {
  if (o.kind === "circle") {
    const dx = b.x - a.x, dy = b.y - a.y, den = dx * dx + dy * dy;
    const t = den ? Math.max(0, Math.min(1, ((o.x - a.x) * dx + (o.y - a.y) * dy) / den)) : 0;
    return Math.hypot(a.x + t * dx - o.x, a.y + t * dy - o.y) < o.r - EPS;
  }
  const x0 = o.x + EPS, x1 = o.x + o.w - EPS, y0 = o.y + EPS, y1 = o.y + o.h - EPS;
  let lo = 0, hi = 1;
  for (const [v, d, min, max] of [[a.x, b.x - a.x, x0, x1], [a.y, b.y - a.y, y0, y1]]) {
    if (Math.abs(d) < 1e-9) { if (v < min || v > max) return false; }
    else {
      let t0 = (min - v) / d, t1 = (max - v) / d;
      if (t0 > t1) [t0, t1] = [t1, t0];
      lo = Math.max(lo, t0); hi = Math.min(hi, t1);
      if (lo > hi) return false;
    }
  }
  return hi >= 0 && lo <= 1;
};
const contains = (p: Point, o: Obstacle) => o.kind === "circle"
  ? distance(p, o) < o.r - EPS
  : p.x > o.x + EPS && p.x < o.x + o.w - EPS && p.y > o.y + EPS && p.y < o.y + o.h - EPS;


export const planLeader = (anchor: Point, ports: Point[], obstacles: Obstacle[], preferred?: LeaderPlan, width = 1440, height = 1080): LeaderPlan => {
  const start = { ...anchor };
  // A geographic anchor can sit under a foreground card. Keep it fixed and
  // allow only its first segment to leave that convex occluder underneath it.
  // Moving the start to the nearest edge makes it jump when the nearest side changes.
  const clear = (a: Point, b: Point) => !obstacles.some((o) =>
    !(distance(a, start) < 1e-7 && contains(start, o)) && segmentHits(a, b, o));
  const nodes: { id: string; p: Point }[] = [{ id: "start", p: start }];
  ports.forEach((p, i) => nodes.push({ id: "port:" + i, p }));
  const near = { x: Math.min(start.x, ...ports.map((p) => p.x)) - 160, y: Math.min(start.y, ...ports.map((p) => p.y)) - 160,
    w: Math.max(start.x, ...ports.map((p) => p.x)) - Math.min(start.x, ...ports.map((p) => p.x)) + 320,
    h: Math.max(start.y, ...ports.map((p) => p.y)) - Math.min(start.y, ...ports.map((p) => p.y)) + 320 };
  for (const o of obstacles) {
    const box = o.kind === "rect" ? o : { x: o.x - o.r, y: o.y - o.r, w: o.r * 2, h: o.r * 2 };
    if (!overlapsRect(near, box) && !preferred?.nodes.some((n) => n.startsWith(o.id + ":"))) continue;
    const corners = o.kind === "rect"
      ? [{ x: o.x - 1, y: o.y - 1 }, { x: o.x + o.w + 1, y: o.y - 1 }, { x: o.x + o.w + 1, y: o.y + o.h + 1 }, { x: o.x - 1, y: o.y + o.h + 1 }]
      : Array.from({ length: 8 }, (_, i) => { const t = i * Math.PI / 4; return { x: o.x + Math.cos(t) * (o.r + 1) / Math.cos(Math.PI / 8), y: o.y + Math.sin(t) * (o.r + 1) / Math.cos(Math.PI / 8) }; });
    corners.forEach((p, i) => { if (p.x >= 8 && p.x <= width - 8 && p.y >= 8 && p.y <= height - 8) nodes.push({ id: o.id + ":" + i, p }); });
  }
  const byId = new Map(nodes.map((n) => [n.id, n.p]));
  if (preferred && preferred.port < ports.length) {
    const ids = ["start", ...preferred.nodes.filter((n) => n !== "start" && !n.startsWith("port:")), "port:" + preferred.port];
    const ps = ids.map((id) => byId.get(id));
    if (ps.every((p) => !!p)) {
      if (ps.slice(1).every((p, i) => clear(ps[i]!, p!)))
        return { points: ps as Point[], nodes: ids, port: preferred.port, clear: true };
      // Retain the same side and port. A moving start may need an extra tangent
      // before the reference waypoints; do not jump to the opposite side.
      if (ps.slice(1, -1).every((p) => !obstacles.some((o) => contains(p!, o)))) {
        const joined: Point[] = [ps[0]!], joinedIds = [ids[0]];
        let valid = true;
        for (let i = 1; i < ps.length; i++) {
          if (clear(ps[i - 1]!, ps[i]!)) { joined.push(ps[i]!); joinedIds.push(ids[i]); }
          else {
            const part = planLeader(ps[i - 1]!, [ps[i]!], obstacles, undefined, width, height);
            if (!part.clear) { valid = false; break; }
            joined.push(...part.points.slice(1));
            joinedIds.push(...part.nodes.slice(1).map((id) => id.startsWith("port:") ? ids[i] : id));
          }
        }
        if (valid) return { points: joined, nodes: joinedIds, port: preferred.port, clear: true };
      }
    }
  }
  const dist = nodes.map(() => Infinity), prev = nodes.map(() => -1), visited = nodes.map(() => false);
  dist[0] = 0;
  let end = -1;
  for (let count = 0; count < nodes.length; count++) {
    let u = -1;
    for (let i = 0; i < nodes.length; i++) if (!visited[i] && (u < 0 || dist[i] < dist[u] - 1e-7)) u = i;
    if (u < 0 || !Number.isFinite(dist[u])) break;
    if (u > 0 && u <= ports.length) { end = u; break; }
    visited[u] = true;
    for (let v = 1; v < nodes.length; v++) if (!visited[v] && clear(nodes[u].p, nodes[v].p)) {
      const bias = preferred && !preferred.nodes.includes(nodes[v].id) && !nodes[v].id.startsWith("port:") ? 24 : 0;
      const portBias = preferred && nodes[v].id.startsWith("port:") && nodes[v].id !== "port:" + preferred.port ? 5000 : 0;
      const cost = dist[u] + distance(nodes[u].p, nodes[v].p) + (u === 0 ? 0 : 8) + bias + portBias;
      if (cost < dist[v] - 1e-7) { dist[v] = cost; prev[v] = u; }
    }
  }
  if (end < 0) return { points: [], nodes: [], port: 0, clear: false };
  const chain: number[] = [];
  for (let i = end; i >= 0; i = prev[i]) { chain.push(i); if (i === 0) break; }
  chain.reverse();
  return { points: chain.map((i) => nodes[i].p), nodes: chain.map((i) => nodes[i].id), port: end - 1, clear: true };
};

export const rectanglePorts = (b: { x: number; y: number; w: number; h: number }, pad = 8): Point[] => [
  { x: b.x - pad - 1, y: b.y + b.h / 2 }, { x: b.x + b.w + pad + 1, y: b.y + b.h / 2 },
  { x: b.x + b.w / 2, y: b.y - pad - 1 }, { x: b.x + b.w / 2, y: b.y + b.h + pad + 1 },
];

// Choose one reference over a planned move, rather than the shortest path in one frame.
// A stable side with a few extra pixels is preferable to switching around a moving card.
export const pickLeaderReference = (scenes: { anchor: Point; ports: Point[]; obstacles: Obstacle[] }[]): LeaderPlan => {
  const candidates = new Map<string, LeaderPlan>();
  for (const s of scenes) for (let port = 0; port < s.ports.length; port++) {
    const route = planLeader(s.anchor,s.ports,s.obstacles,{points:[],nodes:["start","port:"+port],port,clear:true});
    if (route.clear && route.port === port && route.nodes.length <= 10) candidates.set(route.nodes.join("|"),route);
  }
  let best: LeaderPlan = {points:[],nodes:[],port:0,clear:false}, cost = Infinity;
  for (const candidate of candidates.values()) {
    const variants = new Set<string>();
    let score = 0, totalLength = 0;
    for (const s of scenes) {
      const route = planLeader(s.anchor,s.ports,s.obstacles,candidate);
      if (!route.clear || route.port !== candidate.port) score += 1e8;
      variants.add(route.nodes.join("|"));
      totalLength += route.points.slice(1).reduce((n,p,i)=>n+distance(p,route.points[i]),0);
    }
    score += variants.size * 10000 + totalLength / Math.max(1,scenes.length) + candidate.nodes.length * 2;
    if (score < cost) { cost = score; best = candidate; }
  }
  return best;
};

const pointSegmentDistance = (p: Point, a: Point, b: Point) => {
  const dx=b.x-a.x,dy=b.y-a.y,den=dx*dx+dy*dy;
  const t=den?Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/den)):0;
  return Math.hypot(p.x-a.x-t*dx,p.y-a.y-t*dy);
};
export const leaderPathJump = (a: LeaderPlan, b: LeaderPlan) => {
  if (!a.clear || !b.clear || a.points.length<2 || b.points.length<2) return false;
  if (a.port!==b.port) return true;
  const directed=(x:Point[],y:Point[])=>Math.max(...x.flatMap((p,i)=>i?[p,{x:(p.x+x[i-1].x)/2,y:(p.y+x[i-1].y)/2}]:[p])
    .map(p=>Math.min(...y.slice(1).map((q,i)=>pointSegmentDistance(p,y[i],q)))));
  const deviation=Math.max(directed(a.points,b.points),directed(b.points,a.points));
  const motion=Math.max(distance(a.points[0],b.points[0]),distance(a.points[a.points.length-1],b.points[b.points.length-1]));
  return deviation > motion*1.5+12;
};

