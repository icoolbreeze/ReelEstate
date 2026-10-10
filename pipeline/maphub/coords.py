"""Coordinate helpers for the map-hub series (portable, no third-party deps).

- GCJ-02 <-> WGS-84 (iterative inverse, < 1 m error) for using Google/WGS imagery with Amap data.
- Episode "plane" projection: pure Web-Mercator at zoom Z, scaled by K, centred on CENTER,
  mapped onto a W x H comp plane. This is the frame every map layer (base PNG, route, pins) shares.
  EP.07 default: z15, K=2.8125, centre 120.1665,30.2745, 1440x1080  (same as multiplane-opener mapdata.json).
"""
import math

A = 6378245.0
EE = 0.00669342162296594323


def _out_of_china(lng, lat):
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def _tlat(x, y):
    r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return r


def _tlng(x, y):
    r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return r


def wgs_to_gcj(lng, lat):
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _tlat(lng - 105.0, lat - 35.0)
    dlng = _tlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = 1 - EE * math.sin(radlat) ** 2
    sq = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sq) * math.pi)
    dlng = (dlng * 180.0) / (A / sq * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat


def gcj_to_wgs(lng, lat, iters=8):
    """Iterative inverse; residual well under 1 m after a few iterations."""
    w = [lng, lat]
    for _ in range(iters):
        g = wgs_to_gcj(*w)
        w = [w[0] - (g[0] - lng), w[1] - (g[1] - lat)]
    return tuple(w)


def haversine_m(a, b):
    R = 6371008.8
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = p2 - p1, math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def merc_px(lng, lat, z):
    n = 256 * 2 ** z
    x = (lng + 180) / 360 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


class Plane:
    def __init__(self, center=(120.1665, 30.2745), zoom=15, k=2.8125, w=1440, h=1080):
        self.center, self.zoom, self.k, self.w, self.h = tuple(center), zoom, k, w, h
        self.cx, self.cy = merc_px(*self.center, zoom)

    @classmethod
    def from_cfg(cls, cfg):
        return cls(cfg.get("center", (120.1665, 30.2745)), cfg.get("zoom", 15), cfg.get("k", 2.8125), cfg.get("w", 1440), cfg.get("h", 1080))

    def xy(self, lng, lat):
        x, y = merc_px(lng, lat, self.zoom)
        return round(self.w / 2 + (x - self.cx) * self.k, 2), round(self.h / 2 + (y - self.cy) * self.k, 2)

    def metres_per_px(self, lat=None):
        lat = self.center[1] if lat is None else lat
        return 156543.03392 * math.cos(math.radians(lat)) / 2 ** self.zoom / self.k


if __name__ == "__main__":
    import sys
    p = Plane()
    print("listing xy", p.xy(120.167637, 30.276067), "(expect ~794.51, 421.88)")
    g = (120.167637, 30.276067); w = gcj_to_wgs(*g); back = wgs_to_gcj(*w)
    print("gcj->wgs", w, "roundtrip err m", round(haversine_m(g, back), 4))
    print("m/px", round(p.metres_per_px(), 3))
