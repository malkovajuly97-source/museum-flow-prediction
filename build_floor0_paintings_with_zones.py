"""
Создаёт таблицу картин этажа 0 с колонкой «зона» (0-15).
1. Читает floor0_attractions.json.
2. Из floor0_paintings_areas.dxf извлекает замкнутые контуры и подписи зон (MTEXT 0-15).
   Принадлежность точке контуру — через Shapely (надёжный point-in-polygon, точки на границе = внутри).
   Если точка не попала ни в один контур, назначается зона ближайшего контура (в пределах порога).
3. Сохраняет floor0_paintings_with_zones.csv, .json и отчёт floor0_zones_report.txt.
"""
import json
from pathlib import Path

ATTRACTIONS_JSON = Path("floor0_attractions.json")
DXF_FILE = Path("floor0_paintings_areas.dxf")
OUTPUT_CSV = Path("floor0_paintings_with_zones.csv")
OUTPUT_JSON = Path("floor0_paintings_with_zones.json")
OUTPUT_REPORT = Path("floor0_zones_report.txt")

# Если точка не внутри ни одного контура, но ближе этого расстояния до какого-то контура — назначаем ту зону (погрешность границ DXF)
NEAREST_POLYGON_MAX_DIST = 150.0

# Ручные правки: id картины -> правильная зона
# Зоны 11 и 15 — фиксированные списки; в зону 7 перенесены точки, бывшие в 11/15 и не вошедшие в новые списки
ZONE_OVERRIDES = {
    "0_0570": 3,
    "0_0571": 3,
    "0_0574": 3,
    "0_0670": 7,
    "0_0668": 7,
    # Зона 11 (по плану)
    "0_0759": 11,
    "0_0761": 11,
    "0_0763": 11,
    "0_0765": 11,
    "0_0767": 11,
    "0_0749": 11,
    "0_0753": 11,
    "0_0755": 11,
    "0_0751": 11,
    "0_0775": 11,
    "0_0757": 11,
    # Зона 15 (по плану)
    "0_0439": 15,
    "0_0875": 15,
    "0_0879": 15,
    "0_0890": 15,
    "0_0877": 15,
    "0_0881": 15,
    "0_0887": 15,
    "0_0883": 15,
    "0_0885": 15,
    # Были в зонах 11/15, не вошли в новые списки 11 и 15 → зона 7
    "0_0731": 7,
    "0_0733": 7,
    "0_0735": 7,
    "0_0737": 7,
    "0_0739": 7,
    "0_0741": 7,
    "0_0742": 7,
}

_has_shapely = None


def _use_shapely():
    global _has_shapely
    if _has_shapely is None:
        try:
            import shapely.geometry  # noqa: F401
            _has_shapely = True
        except ImportError:
            _has_shapely = False
    return _has_shapely


def load_attractions():
    with open(ATTRACTIONS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("points", [])


def _make_polygon(points: list):
    """Создаёт Shapely Polygon из списка (x,y). Невалидные контуры пробуем исправить buffer(0)."""
    if not _use_shapely():
        return None
    from shapely.geometry import Polygon
    if len(points) < 3:
        return None
    # убираем дубликат последней точки, если контур уже замкнут
    coords = list(points)
    if len(coords) > 3 and abs(coords[0][0] - coords[-1][0]) < 1e-9 and abs(coords[0][1] - coords[-1][1]) < 1e-9:
        coords = coords[:-1]
    try:
        poly = Polygon(coords)
        if poly.is_empty or not poly.is_valid:
            poly = poly.buffer(0)
        return poly if poly.is_valid and not poly.is_empty else None
    except Exception:
        try:
            return Polygon(coords).buffer(0)
        except Exception:
            return None


def _point_inside(px: float, py: float, poly) -> bool:
    """Точка внутри полигона (Shapely) или внутри списка вершин (fallback ray-casting)."""
    if _use_shapely() and poly is not None and hasattr(poly, "contains"):
        from shapely.geometry import Point
        return poly.contains(Point(px, py))
    # fallback: ray casting по списку точек
    polygon = poly if isinstance(poly, list) else (list(poly.exterior.coords) if hasattr(poly, "exterior") else [])
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _polygon_area(poly) -> float:
    """Площадь полигона (Shapely или формула шнурования)."""
    if _use_shapely() and poly is not None and hasattr(poly, "area"):
        return abs(float(poly.area))
    if isinstance(poly, list):
        n = len(poly)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
        return abs(area) * 0.5
    return 0.0


def _distance_to_polygon(px: float, py: float, poly) -> float:
    """Расстояние от точки до полигона (0 если внутри). Только для Shapely."""
    if not _use_shapely() or poly is None or not hasattr(poly, "distance"):
        return float("inf")
    from shapely.geometry import Point
    return float(poly.distance(Point(px, py)))


def parse_dxf_zones_and_contours():
    """
    Читает DXF: замкнутые 2D POLYLINE -> список полигонов [[(x,y),...], ...];
    MTEXT с текстом 0-15 -> список (x, y, zone).
    Возвращает (polygons_with_zone, zone_labels).
    polygons_with_zone: список (polygon, zone), где polygon = [(x,y),...], zone = 0..15 или None.
    zone_labels: [(x, y, zone), ...].
    """
    path = DXF_FILE.resolve()
    if not path.exists():
        print(f"Файл не найден: {path}")
        return [], []

    try:
        import ezdxf
    except ImportError:
        print("Установите ezdxf: pip install ezdxf")
        return [], []

    try:
        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
    except Exception as err:
        print(f"Не удалось прочитать DXF: {err}")
        return [], []

    # Подписи зон (MTEXT и TEXT)
    zone_labels = []
    for e in list(msp.query("TEXT")) + list(msp.query("MTEXT")):
        raw = getattr(e.dxf, "text", None) or ""
        if hasattr(e, "plain_text"):
            text = e.plain_text().strip()
        else:
            text = raw.strip()
        if text.isdigit() and 0 <= int(text) <= 15:
            insert = e.dxf.insert
            zone_labels.append((float(insert.x), float(insert.y), int(text)))

    # Замкнутые 2D полилинии (POLYLINE и LWPOLYLINE) -> полигоны
    polygons = []

    # POLYLINE (старый формат: POLYLINE + VERTEX + SEQEND)
    for e in msp.query("POLYLINE"):
        if not hasattr(e, "get_mode"):
            continue
        try:
            mode = e.get_mode()
        except Exception:
            continue
        if mode != "AcDb2dPolyline":
            continue
        try:
            closed = getattr(e, "is_closed", None)
            closed = closed() if callable(closed) else closed
        except Exception:
            closed = False
        points = []
        try:
            for v in e.vertices:
                loc = v.dxf.location
                points.append((float(loc.x), float(loc.y)))
        except Exception:
            continue
        if len(points) < 3 and not closed:
            continue
        if len(points) == 2 and closed:
            continue  # отрезок, не полигон
        if len(points) >= 3:
            if not closed:
                x0, y0 = points[0]
                x1, y1 = points[-1]
                if (x0 - x1) ** 2 + (y0 - y1) ** 2 > 1e-6:
                    points.append(points[0])
            polygons.append(points)

    # LWPOLYLINE (лёгкие полилинии — часто экспорт из Rhino даёт именно их)
    for e in msp.query("LWPOLYLINE"):
        try:
            closed = getattr(e, "closed", False) or getattr(e, "is_closed", False)
            if callable(closed):
                closed = closed()
        except Exception:
            closed = False
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            try:
                pts = [(float(p[0]), float(p[1])) for p in e]
            except Exception:
                continue
        if len(pts) < 3:
            continue
        if not closed and len(pts) >= 3:
            x0, y0 = pts[0]
            x1, y1 = pts[-1]
            if (x0 - x1) ** 2 + (y0 - y1) ** 2 > 1e-6:
                pts = list(pts) + [pts[0]]
        polygons.append(pts)

    # Превращаем списки точек в геометрию (Shapely Polygon или список для fallback)
    geom_list = []
    for poly in polygons:
        shp = _make_polygon(poly)
        geom_list.append(shp if shp is not None else poly)

    # Каждому полигону назначаем зону: какая подпись (x,y,zone) лежит внутри
    polygons_with_zone = []
    for geom in geom_list:
        zone = None
        for (lx, ly, z) in zone_labels:
            if _point_inside(lx, ly, geom):
                zone = z
                break
        polygons_with_zone.append((geom, zone))

    # Сортируем по площади (сначала самые маленькие): при пересечении контуров
    # точка получит зону наименьшего содержащего её контура
    polygons_with_zone.sort(key=lambda pwz: _polygon_area(pwz[0]))

    return polygons_with_zone, zone_labels


def assign_zone_by_nearest(paintings, zone_labels):
    """Для точек с zone=-1 назначает зону по ближайшей подписи (запасной вариант)."""
    if not zone_labels:
        return
    for p in paintings:
        if p.get("zone", -1) >= 0:
            continue
        px, py = float(p["x"]), float(p["y"])
        best_z, best_d2 = None, float("inf")
        for zx, zy, z in zone_labels:
            d2 = (px - zx) ** 2 + (py - zy) ** 2
            if d2 < best_d2:
                best_d2, best_z = d2, z
        if best_z is not None:
            p["zone"] = best_z


def assign_zones_by_contour(paintings, polygons_with_zone, zone_labels):
    """Сначала point-in-polygon (Shapely); если точка ни в один контур не попала — зона ближайшего контура в пределах порога."""
    for p in paintings:
        px, py = float(p["x"]), float(p["y"])
        found = False
        for geom, zone in polygons_with_zone:
            if zone is not None and _point_inside(px, py, geom):
                p["zone"] = zone
                found = True
                break
        if not found:
            # Точка не внутри ни одного контура: назначаем зону ближайшего контура, если он ближе порога
            best_zone = None
            best_dist = NEAREST_POLYGON_MAX_DIST
            for geom, zone in polygons_with_zone:
                if zone is None:
                    continue
                d = _distance_to_polygon(px, py, geom)
                if d < best_dist:
                    best_dist = d
                    best_zone = zone
            if best_zone is not None:
                p["zone"] = best_zone
            else:
                p.setdefault("zone", -1)
    assign_zone_by_nearest(paintings, zone_labels)

    for p in paintings:
        pid = p.get("id")
        if pid and pid in ZONE_OVERRIDES:
            p["zone"] = ZONE_OVERRIDES[pid]


def apply_overrides(points):
    """Применяет ZONE_OVERRIDES к таблице."""
    for p in points:
        pid = p.get("id")
        if pid and pid in ZONE_OVERRIDES:
            p["zone"] = ZONE_OVERRIDES[pid]


def write_zones_report(points, report_path):
    """Пишет отчёт: по каждой зоне количество точек и список id картин."""
    by_zone = {}
    for p in points:
        z = p.get("zone", -1)
        by_zone.setdefault(z, []).append(p.get("id", ""))
    for z in sorted(by_zone.keys(), key=lambda x: (x < 0, x)):
        ids = sorted(by_zone[z])
        by_zone[z] = ids
    lines = [
        "Количество точек в каждой секции (зоне):",
        "",
    ]
    # Краткая сводка: в 0 — N, в 1 — N, ...
    summary = []
    for z in sorted(by_zone.keys(), key=lambda x: (x < 0, x)):
        n = len(by_zone[z])
        if z >= 0:
            summary.append(f"в {z} — {n}")
        else:
            summary.append(f"не назначена — {n}")
    lines.append(", ".join(summary))
    lines.append("")
    lines.append("Зона -> список id картин (для сверки с планом). Ручные правки: ZONE_OVERRIDES в скрипте.")
    lines.append("")
    for z in sorted(by_zone.keys(), key=lambda x: (x < 0, x)):
        ids = by_zone[z]
        n = len(ids)
        label = f"zone {z}" if z >= 0 else "zone (не назначена)"
        lines.append(f"{label} ({n}): {', '.join(ids)}")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    points = load_attractions()
    if not points:
        print("Нет точек в", ATTRACTIONS_JSON)
        return

    for p in points:
        p.setdefault("zone", -1)

    if _use_shapely():
        print("Используется Shapely для принадлежности точки контуру.")
    polygons_with_zone, zone_labels = parse_dxf_zones_and_contours()
    if not polygons_with_zone and zone_labels:
        print("В DXF нет контуров с 3+ вершинами; зоны заполнены по ближайшей подписи.")
        assign_zone_by_nearest(points, zone_labels)
    elif polygons_with_zone:
        assign_zones_by_contour(points, polygons_with_zone, zone_labels)
        labeled = sum(1 for _, z in polygons_with_zone if z is not None)
        print(f"Контуров: {len(polygons_with_zone)}, с подписью зоны: {labeled}, подписей в DXF: {len(zone_labels)}")
    elif zone_labels:
        assign_zone_by_nearest(points, zone_labels)
        print(f"Зоны заполнены по ближайшей подписи ({len(zone_labels)} подписей).")
    else:
        print("В DXF не найдено контуров и подписей зон. Столбец zone = -1.")

    if polygons_with_zone or zone_labels:
        apply_overrides(points)

    write_zones_report(points, OUTPUT_REPORT)
    print("Отчёт для проверки:", OUTPUT_REPORT)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"points": points}, f, indent=2, ensure_ascii=False)
    print("Сохранено:", OUTPUT_JSON)

    with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
        f.write("id,x,y,zone\n")
        for p in points:
            f.write(f"{p['id']},{p['x']},{p['y']},{p.get('zone', -1)}\n")
    print("Сохранено:", OUTPUT_CSV)
    print("Картин:", len(points))


if __name__ == "__main__":
    main()
