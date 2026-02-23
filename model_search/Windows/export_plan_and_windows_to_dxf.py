"""
Экспорт плана этажа 0 и отрезков окон в один DXF для проверки.

Слои:
  Plan_floor0 — стены этажа 0 из NMFA_3floors_plan.json
  Windows     — отрезки из floor0_windows.json (то, что считаем окнами)

Выход: floor0_plan_and_windows.dxf (в этой же папке)
"""

import json
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("Установите ezdxf: pip install ezdxf")
    raise

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
WINDOWS_JSON = BASE / "floor0_windows.json"
OUTPUT_DXF = BASE / "floor0_plan_and_windows.dxf"

LAYER_PLAN = "Plan_floor0"
LAYER_WINDOWS = "Windows"


def main():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.new(name=LAYER_PLAN, dxfattribs={"color": 5})   # blue
    doc.layers.new(name=LAYER_WINDOWS, dxfattribs={"color": 1})  # red

    # План этажа 0 — стены
    if not PLAN_FILE.exists():
        print(f"Не найден план: {PLAN_FILE}")
    else:
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            plan = json.load(f)
        for floor in plan.get("floors", []):
            if floor.get("number") != 0:
                continue
            n_walls = 0
            for wall in floor.get("walls", []):
                pos = wall.get("position", [])
                if len(pos) < 2:
                    continue
                x1, y1 = pos[0]["x"], pos[0]["y"]
                x2, y2 = pos[1]["x"], pos[1]["y"]
                msp.add_line(
                    start=(x1, y1),
                    end=(x2, y2),
                    dxfattribs={"layer": LAYER_PLAN},
                )
                n_walls += 1
            print(f"План: слой {LAYER_PLAN}, стен {n_walls}")
            break

    # Окна
    if not WINDOWS_JSON.exists():
        print(f"Не найден файл окон: {WINDOWS_JSON}")
    else:
        with open(WINDOWS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        segments = data.get("segments", [])
        for seg in segments:
            pos = seg.get("position", [])
            if len(pos) < 2:
                continue
            x1, y1 = pos[0]["x"], pos[0]["y"]
            x2, y2 = pos[1]["x"], pos[1]["y"]
            msp.add_line(
                start=(x1, y1),
                end=(x2, y2),
                dxfattribs={"layer": LAYER_WINDOWS},
            )
        print(f"Окна: слой {LAYER_WINDOWS}, отрезков {len(segments)}")

    doc.saveas(OUTPUT_DXF)
    print(f"Сохранено: {OUTPUT_DXF}")


if __name__ == "__main__":
    main()
