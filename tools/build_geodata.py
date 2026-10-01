"""產生「地圖找公文」用的離線地理資料，寫進 公文OCR建檔工具.html。

工具本身執行時完全不連網（公文內容與地址都不離開這台電腦），所以地理編碼
需要的資料都在開發時先抓好、內嵌進 HTML。這支腳本只抓公開資料：

  1. 鄉鎮市區界：taiwan-atlas（內政部資料轉成的 TopoJSON，2021 版）
     → 全台 368 個鄉鎮市區的中心點（地址只認得到區的時候用）
     → 縣市輪廓、臺東縣的鄉鎮市界（當作底圖）
  2. 臺東市的道路：OpenStreetMap（Overpass API）
     → 每個路名（含巷弄）一個代表點（地址認得到路名的時候用）
     → 主要道路的線條（當作底圖，讓人認得出位置）

OSM 資料採 ODbL 授權，HTML 裡要標示出處。

用法：python3 tools/build_geodata.py
"""
import json
import math
import pathlib
import re
import urllib.parse
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "公文OCR建檔工具.html"
BEGIN, END = "/* GEODATA:BEGIN */", "/* GEODATA:END */"

ATLAS_URL = "https://cdn.jsdelivr.net/npm/taiwan-atlas@2021.9.20/towns-10t.json"
# 公共 Overpass 伺服器常因負載回 504，依序換鏡像站重試
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
ROAD_CITY = ("臺東縣", "臺東市")
MAIN_ROADS = {"trunk", "primary", "secondary", "tertiary"}


def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "gov-doc-ocr-tool geodata builder",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def tai(s):
    """內政部資料寫「台」，公文寫「臺」——統一成「臺」。"""
    return s.replace("台", "臺")


# --- TopoJSON -----------------------------------------------------------
def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring(arcs, idxs):
    pts = []
    for i in idxs:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def polygons(arcs, geom):
    if geom["type"] == "Polygon":
        return [[ring(arcs, r) for r in geom["arcs"]]]
    return [[ring(arcs, r) for r in poly] for poly in geom["arcs"]]


def ring_area_centroid(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    a /= 2
    if abs(a) < 1e-12:
        return 0.0, pts[0]
    return abs(a), (cx / (6 * a), cy / (6 * a))


def centroid(polys):
    # 用面積最大的那一塊的形心——離島多的鄉鎮，平均起來會落在海上
    best = max((ring_area_centroid(p[0]) for p in polys), key=lambda t: t[0])
    return best[1]


# --- 線段簡化 -----------------------------------------------------------
def simplify(pts, tol):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy) or 1e-12
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[: idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def simplify_ring(pts, tol):
    # 封閉環的起點等於終點，直接丟進 simplify 會以「同一點到同一點」為基準線，
    # 所有點的距離都算成 0，整圈被壓成兩個點。先對半切開再各自簡化。
    mid = len(pts) // 2
    return simplify(pts[: mid + 1], tol)[:-1] + simplify(pts[mid:], tol)


def latlng(pts, nd):
    """[(lng, lat)] → [[lat, lng]]，四捨五入到 nd 位小數。"""
    return [[round(y, nd), round(x, nd)] for x, y in pts]


# --- build ----------------------------------------------------------------
def build_atlas():
    topo = fetch(ATLAS_URL)
    arcs = decode_arcs(topo)
    towns = []
    city_outline = None
    county_towns = []
    for g in topo["objects"]["towns"]["geometries"]:
        p = g["properties"]
        county, town = tai(p["COUNTYNAME"]), tai(p["TOWNNAME"])
        polys = polygons(arcs, g)
        lng, lat = centroid(polys)
        towns.append([county, town, round(lat, 5), round(lng, 5)])
        if county == ROAD_CITY[0]:
            rings = [latlng(simplify_ring(poly[0], 0.0003), 4) for poly in polys]
            county_towns.append({"name": town, "rings": rings})
    counties = []
    for g in topo["objects"]["counties"]["geometries"]:
        rings = [latlng(simplify_ring(poly[0], 0.003), 3) for poly in polygons(arcs, g)]
        counties.append([r for r in rings if len(r) >= 4])
    return towns, counties, county_towns


def build_roads():
    q = f"""[out:json][timeout:120];
area["name"="{ROAD_CITY[1]}"]["boundary"="administrative"]->.a;
way(area.a)["highway"]["name"];
out geom tags;"""
    body = urllib.parse.urlencode({"data": q}).encode()
    for i, url in enumerate(OVERPASS_URLS):
        try:
            data = fetch(url, body)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Overpass {url} 失敗：{e}")
            if i == len(OVERPASS_URLS) - 1:
                raise
    by_name = {}
    lines = []
    for e in data["elements"]:
        if e["tags"].get("highway") in {"proposed", "construction"}:
            continue
        name = tai(e["tags"]["name"])
        pts = [(n["lon"], n["lat"]) for n in e.get("geometry", [])]
        if not pts:
            continue
        by_name.setdefault(name, []).extend(pts)
        if e["tags"]["highway"] in MAIN_ROADS:
            lines.append(latlng(simplify(pts, 0.00005), 5))
    roads = {}
    for name, pts in by_name.items():
        # 代表點取「離所有節點平均位置最近的那個節點」，保證落在路上
        mx = sum(x for x, _ in pts) / len(pts)
        my = sum(y for _, y in pts) / len(pts)
        x, y = min(pts, key=lambda p: (p[0] - mx) ** 2 + (p[1] - my) ** 2)
        roads[name] = [round(y, 5), round(x, 5)]
    return roads, lines


def main():
    towns, counties, county_towns = build_atlas()
    roads, lines = build_roads()
    geodata = {
        "roadCity": list(ROAD_CITY),
        "towns": towns,
        "roads": roads,
        "counties": counties,
        "countyTowns": county_towns,
        "mainRoads": lines,
    }
    blob = json.dumps(geodata, ensure_ascii=False, separators=(",", ":"))
    html = HTML.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END), re.S)
    if not pattern.search(html):
        raise SystemExit(f"找不到 {BEGIN} … {END} 標記")
    html = pattern.sub(lambda _: f"{BEGIN}\nconst GEODATA = {blob};\n{END}", html)
    HTML.write_text(html, encoding="utf-8")
    print(f"鄉鎮市區 {len(towns)}、路名 {len(roads)}、主要道路線段 {len(lines)}、"
          f"寫入 {len(blob.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
