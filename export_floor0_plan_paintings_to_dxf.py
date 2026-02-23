"""
Экспорт плана этажа 0 в DXF:
- слой с планом (стены);
- отдельный слой с точечными локациями картин (без подписей и названий).
"""

import json
from pathlib import Path

try:
    import ezdxf
except ImportError:
    raise ImportError("Установите ezdxf: pip install ezdxf")

# Пути (от корня репозитория)
SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_JSON = SCRIPT_DIR / "bird-dataset-main" / "data" / "NMFA_3floors_plan.json"
OUTPUT_DXF = SCRIPT_DIR / "floor0_plan_painting_points.dxf"

LAYER_FLOOR_PLAN = "Floor_plan"
LAYER_PAINTINGS = "Paintings"  # точечные локации картин, без подписей


def painting_position_on_wall(wall, painting_index, total_paintings):
    """
    Координаты (x, y) центра картины на стене.
    leftDistance из JSON — смещение от начала стены; иначе — равномерное распределение.
    """
    pos = wall["position"]
    x1, y1 = pos[0]["x"], pos[0]["y"]
    x2, y2 = pos[1]["x"], pos[1]["y"]
    paintings = wall.get("paintings", [])
    if not paintings:
        return None
    p = paintings[painting_index] if painting_index < len(paintings) else paintings[0]
    wall_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if wall_len < 1e-6:
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    left_dist = p.get("leftDistance")
    if left_dist is not None and total_paintings == 1:
        t = min(1.0, max(0.0, left_dist / wall_len))
    else:
        t = (painting_index + 0.5) / total_paintings if total_paintings else 0.5
    x = x1 + t * (x2 - x1)
    y = y1 + t * (y2 - y1)
    return (x, y)


def main():
    plan_path = PLAN_JSON
    if not plan_path.exists():
        alt = SCRIPT_DIR / "data" / "NMFA_3floors_plan.json"
        plan_path = alt if alt.exists() else plan_path
    if not plan_path.exists():
        raise FileNotFoundError(f"Файл плана не найден: {plan_path}")
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    floor = next((f for f in data["floors"] if f["number"] == 0), None)
    if floor is None:
        raise ValueError("Этаж 0 не найден в плане")
    walls = floor["walls"]

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.new(name=LAYER_FLOOR_PLAN, dxfattribs={"color": 7})  # белый/серый
    doc.layers.new(name=LAYER_PAINTINGS, dxfattribs={"color": 1})    # красный

    # План: отрезки стен
    for wall in walls:
        pos = wall.get("position", [])
        if len(pos) < 2:
            continue
        x1, y1 = pos[0]["x"], pos[0]["y"]
        x2, y2 = pos[1]["x"], pos[1]["y"]
        msp.add_line(
            start=(x1, y1),
            end=(x2, y2),
            dxfattribs={"layer": LAYER_FLOOR_PLAN},
        )

    # Точечные локации картин (без подписей и названий)
    n_points = 0
    for wall in walls:
        paintings = wall.get("paintings", [])
        n = len(paintings)
        for i in range(n):
            pt = painting_position_on_wall(wall, i, n)
            if pt is None:
                continue
            msp.add_point(
                (pt[0], pt[1]),
                dxfattribs={"layer": LAYER_PAINTINGS},
            )
            n_points += 1

    OUTPUT_DXF.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(OUTPUT_DXF)
    print(f"Сохранено: {OUTPUT_DXF}")
    print(f"  Слой «{LAYER_FLOOR_PLAN}»: {len(walls)} стен (отрезки)")
    print(f"  Слой «{LAYER_PAINTINGS}»: {n_points} точек (локации картин, без подписей)")


if __name__ == "__main__":
    main()
