"""
Room popularity ranking из DXF: зоны 0–15, треки в слоях или CSV.
Публичный API: compute_room_popularity_ranking(), save_ranking(), load_trajectories_from_csv(), load_simulated_trajectories_from_unity_dxf().
"""
import glob
import json
from pathlib import Path

import pandas as pd

try:
    import ezdxf
except ImportError:
    ezdxf = None

try:
    from shapely.geometry import Polygon, Point
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

NEAREST_POLYGON_MAX_DIST = 150.0


def _make_polygon(points):
    if len(points) < 3:
        return None
    coords = list(points)
    if len(coords) > 3 and abs(coords[0][0] - coords[-1][0]) < 1e-9 and abs(coords[0][1] - coords[-1][1]) < 1e-9:
        coords = coords[:-1]
    if not HAS_SHAPELY:
        return coords
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


def _point_inside(px, py, poly):
    if HAS_SHAPELY and poly is not None and hasattr(poly, "contains"):
        return poly.contains(Point(px, py))
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


def _polygon_area(poly):
    if HAS_SHAPELY and poly is not None and hasattr(poly, "area"):
        return abs(float(poly.area))
    if isinstance(poly, list) and len(poly) >= 3:
        area = 0.0
        for i in range(len(poly)):
            j = (i + 1) % len(poly)
            area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
        return abs(area) * 0.5
    return 0.0


def _distance_to_polygon(px, py, poly):
    if not HAS_SHAPELY or poly is None or not hasattr(poly, "distance"):
        return float("inf")
    return float(poly.distance(Point(px, py)))


def load_trajectories_from_csv(folder_path, floor_number=0):
    """
    Загружает треки из CSV. Каждый CSV = одна траектория.
    Возвращает list[list[tuple]] — список траекторий, каждая = [(x,y), ...] sorted by timestamp.
    """
    path = Path(folder_path).resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"Папка не найдена: {path}")
    csv_files = glob.glob(str(path / "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Нет CSV в {path}")
    trajectories = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            df_floor = df[df["floorNumber"] == floor_number].copy()
            if len(df_floor) > 0:
                df_floor = df_floor.sort_values("timestamp").reset_index(drop=True)
                points = [(float(row["x"]), float(row["y"])) for _, row in df_floor.iterrows()]
                trajectories.append(points)
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file}: {e}")
    if not trajectories:
        raise ValueError(f"Не найдено траекторий для этажа {floor_number}")
    return trajectories


def parse_zones_from_dxf(path_dxf, layer_area):
    path = Path(path_dxf).resolve()
    if not path.exists():
        raise FileNotFoundError(f"DXF не найден: {path}")
    if ezdxf is None:
        raise ImportError("Установите ezdxf: pip install ezdxf")
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    zone_labels = []
    for e in list(msp.query("TEXT")) + list(msp.query("MTEXT")):
        if getattr(e.dxf, "layer", "") != layer_area:
            continue
        raw = getattr(e.dxf, "text", None) or ""
        text = (e.plain_text() if hasattr(e, "plain_text") else raw).strip()
        if text.isdigit() and 0 <= int(text) <= 15:
            insert = e.dxf.insert
            zone_labels.append((float(insert.x), float(insert.y), int(text)))

    polygons = []
    for e in msp.query("POLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_area:
            continue
        if not hasattr(e, "get_mode"):
            continue
        try:
            if e.get_mode() != "AcDb2dPolyline":
                continue
        except Exception:
            continue
        closed = getattr(e, "is_closed", None)
        closed = closed() if callable(closed) else closed
        points = []
        try:
            for v in e.vertices:
                loc = v.dxf.location
                points.append((float(loc.x), float(loc.y)))
        except Exception:
            continue
        if len(points) < 3:
            continue
        if not closed:
            x0, y0 = points[0]
            x1, y1 = points[-1]
            if (x0 - x1) ** 2 + (y0 - y1) ** 2 > 1e-6:
                points.append(points[0])
        polygons.append(points)

    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_area:
            continue
        closed = getattr(e, "closed", False) or getattr(e, "is_closed", False)
        if callable(closed):
            closed = closed()
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            try:
                pts = [(float(p[0]), float(p[1])) for p in e]
            except Exception:
                continue
        if len(pts) < 3:
            continue
        if not closed:
            x0, y0 = pts[0]
            x1, y1 = pts[-1]
            if (x0 - x1) ** 2 + (y0 - y1) ** 2 > 1e-6:
                pts = list(pts) + [pts[0]]
        polygons.append(pts)

    geom_list = [_make_polygon(p) or p for p in polygons]
    polygons_with_zone = []
    for geom in geom_list:
        zone = None
        for (lx, ly, z) in zone_labels:
            if _point_inside(lx, ly, geom):
                zone = z
                break
        polygons_with_zone.append((geom, zone))

    polygons_with_zone.sort(key=lambda pwz: _polygon_area(pwz[0]))
    return polygons_with_zone, zone_labels


def get_bbox_from_dxf_layer(path_dxf, layer_name):
    """
    Извлекает bounding box геометрии указанного слоя DXF в сырых координатах.
    Возвращает (x_min, x_max, y_min, y_max). Если слой пуст — ValueError.
    """
    path = Path(path_dxf).resolve()
    if not path.exists():
        raise FileNotFoundError(f"DXF не найден: {path}")
    if ezdxf is None:
        raise ImportError("Установите ezdxf: pip install ezdxf")
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    xs, ys = [], []
    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_name:
            continue
        try:
            for pt in e.get_points("xy"):
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
        except Exception:
            continue
    for e in msp.query("LINE"):
        if getattr(e.dxf, "layer", "") != layer_name:
            continue
        try:
            s, en = e.dxf.start, e.dxf.end
            xs.extend([float(s.x), float(en.x)])
            ys.extend([float(s.y), float(en.y)])
        except Exception:
            continue
    for e in msp.query("POLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_name:
            continue
        try:
            for v in e.vertices:
                loc = v.dxf.location
                xs.append(float(loc.x))
                ys.append(float(loc.y))
        except Exception:
            continue
    if not xs or not ys:
        raise ValueError(f"Слой '{layer_name}' пуст или не найден в {path}")
    return float(min(xs)), float(max(xs)), float(min(ys)), float(max(ys))


def _compute_unity_to_floor_transform(bbox_bird, bbox_unity):
    """
    По двум bbox (x_min, x_max, y_min, y_max) вычисляет scale и offset
    для преобразования точки из unity в координаты Floor_0.dxf:
    x_bird = x_unity * scale_x + offset_x, y_bird = y_unity * scale_y + offset_y.
    """
    (bx_min, bx_max, by_min, by_max) = bbox_bird
    (ux_min, ux_max, uy_min, uy_max) = bbox_unity
    span_ux = ux_max - ux_min
    span_uy = uy_max - uy_min
    span_bx = bx_max - bx_min
    span_by = by_max - by_min
    scale_x = span_bx / span_ux if span_ux > 1e-9 else 1.0
    scale_y = span_by / span_uy if span_uy > 1e-9 else 1.0
    cx_bird = (bx_min + bx_max) / 2
    cy_bird = (by_min + by_max) / 2
    cx_unity = (ux_min + ux_max) / 2
    cy_unity = (uy_min + uy_max) / 2
    offset_x = cx_bird - cx_unity * scale_x
    offset_y = cy_bird - cy_unity * scale_y
    return scale_x, scale_y, offset_x, offset_y


def load_simulated_trajectories_from_unity_dxf(
    path_floor_dxf,
    path_unity_dxf,
    layer_reference_bird="Outline",
    layer_reference_unity="PLAN_FLOOR",
    layer_tracks_unity="TRACKS",
):
    """
    Загружает симулированные треки из unity_plan_and_tracks.dxf и приводит их
    к координатам Floor_0.dxf по референсу Outline (Floor_0) и PLAN_FLOOR (unity).
    Возвращает list[list[tuple]] в координатах Floor_0.dxf (сырые).
    """
    bbox_bird = get_bbox_from_dxf_layer(path_floor_dxf, layer_reference_bird)
    bbox_unity = get_bbox_from_dxf_layer(path_unity_dxf, layer_reference_unity)
    scale_x, scale_y, offset_x, offset_y = _compute_unity_to_floor_transform(bbox_bird, bbox_unity)

    raw_trajectories = parse_trajectories_from_dxf(path_unity_dxf, layer_tracks_unity)
    trajectories = []
    for points in raw_trajectories:
        transformed = [
            (x * scale_x + offset_x, y * scale_y + offset_y)
            for (x, y) in points
        ]
        trajectories.append(transformed)
    return trajectories


def parse_floor_plan_lines(path_dxf, layer_floor_plan):
    """
    Извлекает линии плана этажа из DXF (для отрисовки).
    Возвращает list of segments: [(x1,y1,x2,y2), ...].
    """
    path = Path(path_dxf).resolve()
    if not path.exists() or ezdxf is None:
        return []
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    segments = []
    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_floor_plan:
            continue
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            continue
        for i in range(len(pts) - 1):
            x1, y1 = float(pts[i][0]), float(pts[i][1])
            x2, y2 = float(pts[i + 1][0]), float(pts[i + 1][1])
            segments.append((x1, y1, x2, y2))
    for e in msp.query("LINE"):
        if getattr(e.dxf, "layer", "") != layer_floor_plan:
            continue
        try:
            s, en = e.dxf.start, e.dxf.end
            segments.append((float(s.x), float(s.y), float(en.x), float(en.y)))
        except Exception:
            continue
    return segments


def parse_trajectories_from_dxf(path_dxf, layer_trajectories):
    path = Path(path_dxf).resolve()
    if ezdxf is None:
        raise ImportError("Установите ezdxf: pip install ezdxf")
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    trajectories = []
    for e in msp.query("POLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_trajectories:
            continue
        try:
            mode = e.get_mode()
        except Exception:
            continue
        if mode != "AcDb2dPolyline":
            continue
        points = []
        try:
            for v in e.vertices:
                loc = v.dxf.location
                points.append((float(loc.x), float(loc.y)))
        except Exception:
            continue
        if len(points) >= 2:
            trajectories.append(points)

    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer_trajectories:
            continue
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            try:
                pts = [(float(p[0]), float(p[1])) for p in e]
            except Exception:
                continue
        if len(pts) >= 2:
            trajectories.append(pts)

    return trajectories


def assign_point_to_zone(px, py, polygons_with_zone, zone_labels):
    for geom, zone in polygons_with_zone:
        if zone is not None and _point_inside(px, py, geom):
            return zone
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
        return best_zone
    best_z, best_d2 = None, float("inf")
    for zx, zy, z in zone_labels:
        d2 = (px - zx) ** 2 + (py - zy) ** 2
        if d2 < best_d2:
            best_d2, best_z = d2, z
    return best_z if best_z is not None else -1


def compute_transition_matrix(polygons_with_zone, zone_labels, trajectories):
    """
    Переходы from_zone -> to_zone для соседних точек траектории (A != B, оба >= 0).
    Возвращает (pd.DataFrame с колонками from_zone, to_zone, count, dependency, dependency_pct), total_transitions.
    """
    transitions = {}
    for points in trajectories:
        zones_seq = [
            assign_point_to_zone(x, y, polygons_with_zone, zone_labels)
            for (x, y) in points
        ]
        for i in range(len(zones_seq) - 1):
            a, b = zones_seq[i], zones_seq[i + 1]
            if a >= 0 and b >= 0 and a != b:
                key = (a, b)
                transitions[key] = transitions.get(key, 0) + 1

    total_transitions = sum(transitions.values())
    rows = []
    for (from_z, to_z), count in sorted(transitions.items()):
        dependency = count / total_transitions if total_transitions > 0 else 0.0
        dependency_pct = 100.0 * dependency
        rows.append({
            "from_zone": from_z,
            "to_zone": to_z,
            "count": count,
            "dependency": round(dependency, 6),
            "dependency_pct": round(dependency_pct, 2),
        })
    df = pd.DataFrame(rows, columns=["from_zone", "to_zone", "count", "dependency", "dependency_pct"])
    return df, total_transitions


def _compute_ranking_from_trajectories(polygons_with_zone, zone_labels, trajectories):
    """Внутренняя логика: polygons_with_zone, zone_labels, trajectories -> (df, chain, n)."""
    trajectory_zones = {}
    for i, points in enumerate(trajectories):
        zones_visited = set()
        for (x, y) in points:
            z = assign_point_to_zone(x, y, polygons_with_zone, zone_labels)
            if z >= 0:
                zones_visited.add(z)
        trajectory_zones[f"traj_{i}"] = zones_visited

    zone_counts = {}
    for zones in trajectory_zones.values():
        for z in zones:
            zone_counts[z] = zone_counts.get(z, 0) + 1

    zones_sorted = sorted(zone_counts.keys(), key=lambda z: (zone_counts[z], z))
    ranking = [
        {"zone": zone, "n_agents_visited": zone_counts[zone], "rank": rank}
        for rank, zone in enumerate(zones_sorted, start=1)
    ]
    chain = [r["zone"] for r in ranking]
    df = pd.DataFrame(ranking, columns=["zone", "n_agents_visited", "rank"])
    return df, chain, len(trajectories)


def compute_room_popularity_ranking(path_dxf, layer_area, layer_trajectories=None, layer_floor_plan=None, trajectories=None):
    """
    Считает room popularity ranking.
    Если trajectories задан (list[list[tuple]]) — использует его; иначе загружает из DXF (layer_trajectories обязателен).
    Возвращает (pd.DataFrame, list[int] chain, int n_trajectories).
    """
    polygons_with_zone, zone_labels = parse_zones_from_dxf(path_dxf, layer_area)
    if trajectories is not None:
        pass
    elif layer_trajectories is not None:
        trajectories = parse_trajectories_from_dxf(path_dxf, layer_trajectories)
    else:
        raise ValueError("Укажите layer_trajectories или trajectories")
    return _compute_ranking_from_trajectories(polygons_with_zone, zone_labels, trajectories)


def save_ranking(ranking_df, chain, path_dxf, n_trajectories, layer_floor_plan=None, layer_area=None, layer_trajectories=None):
    """Сохраняет ranking в CSV и JSON рядом с DXF."""
    out_dir = Path(path_dxf).resolve().parent
    out_csv = out_dir / "room_popularity_ranking.csv"
    out_json = out_dir / "room_popularity_ranking.json"

    ranking_df.to_csv(out_csv, index=False)

    ranking_list = ranking_df.to_dict("records")
    out_data = {
        "ranking": ranking_list,
        "popularity_chain_least_to_most": chain,
        "n_trajectories": n_trajectories,
        "params": {
            "path_dxf": str(Path(path_dxf).resolve()),
            "layer_floor_plan": layer_floor_plan,
            "layer_area": layer_area,
            "layer_trajectories": layer_trajectories,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    return out_csv, out_json
