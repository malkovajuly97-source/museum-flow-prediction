"""
Конвертирует JSON плана и треков из Unity (PlanAndTrackExporter) в DXF.
Вход: например 10_02_unity_plan_and_tracks.json
Выход: тот же базовый имя + .dxf (10_02_unity_plan_and_tracks.dxf).
Unity: метры → DXF: миллиметры (для Rhino с Model units = Millimeters).
Запуск: python export_unity_plan_and_tracks_to_dxf.py <путь_к_json>
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


def main():
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        print("Укажите путь: python export_unity_plan_and_tracks_to_dxf.py <путь_к_json>")
        sys.exit(1)
    if not json_path.exists():
        print(f"Файл не найден: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    floor_outline = data.get("floor_outline") or []
    wall_rects = data.get("wall_rects") or []
    wall_outlines = data.get("wall_outlines") or []
    floor_bounds = data.get("floor_bounds") or {}
    trajectories = data.get("trajectories") or []

    if not floor_outline and not wall_rects and not wall_outlines:
        mnx = floor_bounds.get("minX", 0)
        mxx = floor_bounds.get("maxX", 0)
        mnz = floor_bounds.get("minZ", 0)
        mxz = floor_bounds.get("maxZ", 0)
        if mxx - mnx > 0.01 and mxz - mnz > 0.01:
            floor_outline = [{"x": mnx, "y": mnz}, {"x": mxx, "y": mnz}, {"x": mxx, "y": mxz}, {"x": mnx, "y": mxz}]
        elif trajectories:
            all_xy = []
            for t in trajectories:
                for p in t.get("points", []):
                    all_xy.append((p.get("x", 0), p.get("y", 0)))
            if all_xy:
                xs, ys = [a[0] for a in all_xy], [a[1] for a in all_xy]
                ext = max(max(xs) - min(xs), max(ys) - min(ys), 1) * 0.05
                mnx, mxx = min(xs) - ext, max(xs) + ext
                mnz, mxz = min(ys) - ext, max(ys) + ext
                floor_outline = [{"x": mnx, "y": mnz}, {"x": mxx, "y": mnz}, {"x": mxx, "y": mxz}, {"x": mnx, "y": mxz}]
    if not floor_outline and not wall_rects and not wall_outlines:
        print("Нет данных плана в файле.")
        sys.exit(1)

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.new(name="PLAN_FLOOR", dxfattribs={"color": 8})
    doc.layers.new(name="PLAN_WALLS", dxfattribs={"color": 7})
    doc.layers.new(name="TRACKS", dxfattribs={"color": 1})

    if floor_outline:
        pts = [(p.get("x", 0) * SCALE, p.get("y", 0) * SCALE, 0) for p in floor_outline]
        if len(pts) >= 3:
            msp.add_lwpolyline(points=pts, close=True, dxfattribs={"layer": "PLAN_FLOOR", "color": 8})

    for w in wall_rects:
        a, b = w.get("minX", 0), w.get("minZ", 0)
        c, d = w.get("maxX", 0), w.get("maxZ", 0)
        rect = [(a * SCALE, b * SCALE, 0), (c * SCALE, b * SCALE, 0), (c * SCALE, d * SCALE, 0), (a * SCALE, d * SCALE, 0)]
        msp.add_lwpolyline(points=rect, close=True, dxfattribs={"layer": "PLAN_WALLS", "color": 7})

    for wo in wall_outlines:
        pts = wo.get("points") or []
        if len(pts) >= 2:
            coords = [(p.get("x", 0) * SCALE, p.get("y", 0) * SCALE, 0) for p in pts]
            msp.add_lwpolyline(points=coords, close=len(pts) >= 3, dxfattribs={"layer": "PLAN_WALLS", "color": 7})

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

    # Имя DXF = то же базовое имя, что у входного JSON
    out_name = json_path.stem + ".dxf"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else (json_path.parent / out_name)
    if out_path.is_dir():
        out_path = out_path / out_name
    doc.saveas(str(out_path))
    print(f"Сохранено: {out_path}")
    print(f"Треков: {len(trajectories)}")


if __name__ == "__main__":
    main()
