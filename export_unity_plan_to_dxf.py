"""
Конвертирует unity_plan.json (из Unity ExportPlanToDxf) в DXF для Rhino.
Запуск: python export_unity_plan_to_dxf.py <путь_к_json> [путь_к_dxf]
Если путь к DXF не указан — сохраняет рядом с JSON.
"""
import json
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
        for p in [Path("unity_plan.json"), Path("UnityScripts/unity_plan.json"), Path("UnityScripts/unity_tracks.json")]:
            if p.exists():
                json_path = p
                break
        else:
            json_path = Path("UnityScripts/unity_plan.json")
    if not json_path.exists():
        print("Файл не найден. Укажите путь: python export_unity_plan_to_dxf.py <путь>")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    floor_outline = data.get("floor_outline") or []
    wall_rects = data.get("wall_rects") or []
    wall_outlines = data.get("wall_outlines") or []
    floor_bounds = data.get("floor_bounds") or {}

    if not floor_outline and not wall_rects and not wall_outlines:
        mnx = floor_bounds.get("minX", 0)
        mxx = floor_bounds.get("maxX", 0)
        mnz = floor_bounds.get("minZ", 0)
        mxz = floor_bounds.get("maxZ", 0)
        if mxx - mnx > 0.01 and mxz - mnz > 0.01:
            floor_outline = [{"x": mnx, "y": mnz}, {"x": mxx, "y": mnz}, {"x": mxx, "y": mxz}, {"x": mnx, "y": mxz}]
        else:
            traj = data.get("trajectories") or []
            all_xy = []
            for t in traj:
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
    doc.layers.new(name="FLOOR", dxfattribs={"color": 8})
    doc.layers.new(name="WALLS", dxfattribs={"color": 7})

    if floor_outline:
        pts = [(p.get("x", 0), p.get("y", 0), 0) for p in floor_outline]
        if len(pts) >= 3:
            # Порядок точек из Unity уже правильный — не сортируем, иначе получаются серые диагонали
            msp.add_lwpolyline(points=pts, close=True, dxfattribs={"layer": "FLOOR", "color": 8})

    for w in wall_rects:
        a, b = w.get("minX", 0), w.get("minZ", 0)
        c, d = w.get("maxX", 0), w.get("maxZ", 0)
        rect = [(a, b, 0), (c, b, 0), (c, d, 0), (a, d, 0)]
        msp.add_lwpolyline(points=rect, close=True, dxfattribs={"layer": "WALLS", "color": 7})

    for wo in wall_outlines:
        pts = wo.get("points") or []
        if len(pts) >= 2:
            coords = [(p.get("x", 0), p.get("y", 0), 0) for p in pts]
            msp.add_lwpolyline(points=coords, close=len(coords) >= 3, dxfattribs={"layer": "WALLS", "color": 7})

    out_name = "unity_plan.dxf" if "tracks" in json_path.stem.lower() else (json_path.stem + ".dxf")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else (json_path.parent / out_name)
    if out_path.is_dir():
        out_path = out_path / out_name
    doc.saveas(str(out_path))
    print(f"Сохранено: {out_path}")


if __name__ == "__main__":
    main()
