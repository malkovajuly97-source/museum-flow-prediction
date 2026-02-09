"""
Экспорт треков и плана этажа из Unity (unity_tracks.json) в DXF.
Unity: метры → DXF: миллиметры (для Rhino с Model units = Millimeters).
Запуск: python export_unity_tracks_to_dxf.py [путь_к_json]
"""
import json

# Unity (метры) → Rhino (миллиметры)
SCALE = 1000
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("Установите ezdxf: pip install ezdxf")
    sys.exit(1)


def _convex_hull(pts):
    """Convex hull (Graham scan) — внешний контур по точкам стен и треков."""
    if len(pts) < 3:
        return pts
    pts = list(set(pts))
    if len(pts) < 3:
        return pts
    # Найти нижнюю-левую точку
    start = min(pts, key=lambda p: (p[1], p[0]))
    def angle_key(p):
        if p == start:
            return -999
        import math
        return math.atan2(p[1] - start[1], p[0] - start[0])
    sorted_pts = sorted(pts, key=angle_key)
    hull = [sorted_pts[0], sorted_pts[1]]
    for i in range(2, len(sorted_pts)):
        p = sorted_pts[i]
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    return hull


def find_tracks_json():
    candidates = [
        Path("unity_tracks.json"),
        Path("Assets/StreamingAssets/unity_tracks.json"),
        Path(__file__).parent / "unity_tracks.json",
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        json_path = Path(args[0])
    else:
        json_path = find_tracks_json()
    if not json_path or not json_path.exists():
        print("Файл unity_tracks.json не найден.")
        print("Укажите путь: python export_unity_tracks_to_dxf.py <путь> [--plan <план.dxf>]")
        print("Или положите unity_tracks.json в папку со скриптом.")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    trajectories = data.get("trajectories", [])
    if not trajectories:
        print("Нет треков в файле.")
        sys.exit(0)

    floor_bounds = data.get("floor_bounds")
    floor_outline = data.get("floor_outline") or []
    # Контур пола: если пуст — берём из unity_plan.json (от Export_floor_plan)
    if not floor_outline and json_path.parent:
        plan_path = json_path.parent / "unity_plan.json"
        if plan_path.exists():
            try:
                with open(plan_path, "r", encoding="utf-8") as pf:
                    plan_data = json.load(pf)
                    floor_outline = plan_data.get("floor_outline") or []
            except Exception:
                pass
    wall_rects = data.get("wall_rects") or []
    wall_outlines = data.get("wall_outlines") or []
    has_unity_plan = bool(floor_bounds or floor_outline or wall_rects or wall_outlines)

    def all_xy():
        for t in trajectories:
            for p in t.get("points", []):
                yield p.get("x", 0), p.get("y", 0)
        for w in wall_rects:
            yield w.get("minX", 0), w.get("minZ", 0)
            yield w.get("maxX", 0), w.get("maxZ", 0)
        for wo in wall_outlines:
            for p in wo.get("points") or []:
                yield p.get("x", 0), p.get("y", 0)

    all_pts = list(all_xy())
    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        extent = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    else:
        extent = 50.0

    if has_unity_plan:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        doc.layers.new(name="PLAN_FLOOR", dxfattribs={"color": 8})
        doc.layers.new(name="PLAN_WALLS", dxfattribs={"color": 7})
        doc.layers.new(name="PLAN_POINTS", dxfattribs={"color": 4})
        doc.layers.new(name="TRACKS", dxfattribs={"color": 1})

        mnx = mxx = mnz = mxz = None
        if floor_outline:
            pts = [(p.get("x", 0) * SCALE, p.get("y", 0) * SCALE, 0) for p in floor_outline]
            if len(pts) >= 3:
                msp.add_lwpolyline(points=pts, close=True, dxfattribs={"layer": "PLAN_FLOOR", "color": 8})
        elif floor_bounds:
            mnx = floor_bounds.get("minX", 0)
            mnz = floor_bounds.get("minZ", 0)
            mxx = floor_bounds.get("maxX", 0)
            mxz = floor_bounds.get("maxZ", 0)
            if mxx - mnx > 0.01 and mxz - mnz > 0.01:
                rect = [(mnx * SCALE, mnz * SCALE, 0), (mxx * SCALE, mnz * SCALE, 0), (mxx * SCALE, mxz * SCALE, 0), (mnx * SCALE, mxz * SCALE, 0), (mnx * SCALE, mnz * SCALE, 0)]
                msp.add_lwpolyline(points=rect, dxfattribs={"layer": "PLAN_FLOOR", "color": 8})

        fb = floor_bounds or {}
        fw = (fb.get("maxX", 0) or 0) - (fb.get("minX", 0) or 0)
        fh = (fb.get("maxZ", 0) or 0) - (fb.get("minZ", 0) or 0)
        if not floor_outline and (fw < 0.01 or fh < 0.01) and all_pts:
            mnx, mxx = min(xs), max(xs)
            mnz, mxz = min(ys), max(ys)
            pad = extent * 0.05
            rect = [((mnx - pad) * SCALE, (mnz - pad) * SCALE, 0), ((mxx + pad) * SCALE, (mnz - pad) * SCALE, 0),
                    ((mxx + pad) * SCALE, (mxz + pad) * SCALE, 0), ((mnx - pad) * SCALE, (mxz + pad) * SCALE, 0), ((mnx - pad) * SCALE, (mnz - pad) * SCALE, 0)]
            msp.add_lwpolyline(points=rect, dxfattribs={"layer": "PLAN_FLOOR", "color": 8})

        for w in wall_rects:
            a, b = w.get("minX", 0), w.get("minZ", 0)
            c, d = w.get("maxX", 0), w.get("maxZ", 0)
            rect = [(a * SCALE, b * SCALE, 0), (c * SCALE, b * SCALE, 0), (c * SCALE, d * SCALE, 0), (a * SCALE, d * SCALE, 0), (a * SCALE, b * SCALE, 0)]
            msp.add_lwpolyline(points=rect, dxfattribs={"layer": "PLAN_WALLS", "color": 7})

        for wo in wall_outlines:
            pts = wo.get("points") or []
            if len(pts) >= 2:
                coords = [(p.get("x", 0) * SCALE, p.get("y", 0) * SCALE, 0) for p in pts]
                msp.add_lwpolyline(points=coords, close=len(coords) >= 3, dxfattribs={"layer": "PLAN_WALLS", "color": 7})

        # Fallback: convex hull (внешний контур) — только если контур пола не найден
        if not floor_outline and all_pts:
            hull_pts = _convex_hull([(p[0], p[1]) for p in all_pts])
            if len(hull_pts) >= 3:
                pts3d = [(x * SCALE, y * SCALE, 0) for x, y in hull_pts]
                msp.add_lwpolyline(points=pts3d, close=True, dxfattribs={"layer": "PLAN_FLOOR", "color": 8})

        print(f"План: пол, стен {len(wall_rects) + len(wall_outlines)}")
    else:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        doc.layers.new(name="TRACKS", dxfattribs={"color": 1})

    for i, traj in enumerate(trajectories):
        pts = traj.get("points", [])
        if len(pts) < 2:
            continue
        if isinstance(pts[0], dict):
            coords = [(p["x"] * SCALE, p["y"] * SCALE, 0) for p in pts]
        else:
            coords = [(p[0] * SCALE, p[1] * SCALE, 0) for p in pts]
        msp.add_lwpolyline(
            points=coords,
            dxfattribs={"layer": "TRACKS", "color": (i % 7) + 1}
        )

    out_path = json_path.parent / "unity_tracks.dxf"
    doc.saveas(str(out_path))
    print(f"Сохранено: {out_path}")
    print(f"Треков: {len(trajectories)}")


if __name__ == "__main__":
    main()
