"""
Визуализация плана этажа 0 музея с отметками локаций картин.
Использует NMFA_3floors_plan.json и при необходимости artworks_dataset.csv.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Пути
PLAN_FILE = Path("bird-dataset-main/data/NMFA_3floors_plan.json")
OUTPUT_FILE = Path("floor0_plan_with_paintings.png")


def load_floor0_from_plan():
    """Загружает план и возвращает данные этажа 0."""
    with open(PLAN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for floor in data["floors"]:
        if floor["number"] == 0:
            return floor
    raise ValueError("Этаж 0 не найден в плане")


def wall_segment_to_line(wall):
    """Возвращает (x1, y1, x2, y2) для отрезка стены."""
    pos = wall["position"]
    return (pos[0]["x"], pos[0]["y"], pos[1]["x"], pos[1]["y"])


def painting_position_on_wall(wall, painting_index, total_paintings):
    """
    Вычисляет координаты (x, y) центра картины на стене.
    Используется середина стены или доля вдоль стены при нескольких картинах.
    leftDistance из JSON (если есть) интерпретируется как смещение от начала стены (в тех же единицах, что координаты).
    """
    pos = wall["position"]
    x1, y1 = pos[0]["x"], pos[0]["y"]
    x2, y2 = pos[1]["x"], pos[1]["y"]
    paintings = wall.get("paintings", [])
    if not paintings:
        return None
    p = paintings[painting_index] if painting_index < len(paintings) else paintings[0]
    wall_len = np.hypot(x2 - x1, y2 - y1)
    if wall_len < 1e-6:
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    # Если есть leftDistance — берём точку на стене на этой дистанции от начала
    left_dist = p.get("leftDistance")
    if left_dist is not None and total_paintings == 1:
        t = min(1.0, max(0.0, left_dist / wall_len))  # доля длины стены
    else:
        # Иначе распределяем равномерно: для одной — середина, для нескольких — равные доли
        t = (painting_index + 0.5) / total_paintings if total_paintings else 0.5
    x = x1 + t * (x2 - x1)
    y = y1 + t * (y2 - y1)
    return (x, y)


def main():
    floor = load_floor0_from_plan()
    walls = floor["walls"]

    fig, ax = plt.subplots(figsize=(14, 12))

    # Рисуем все стены этажа 0
    for w in walls:
        x1, y1, x2, y2 = wall_segment_to_line(w)
        ax.plot([x1, x2], [y1, y2], "k-", linewidth=0.8, zorder=1)

    # Собираем координаты картин и рисуем маркеры
    px, py, labels = [], [], []
    for w in walls:
        paintings = w.get("paintings", [])
        n = len(paintings)
        for i, p in enumerate(paintings):
            pt = painting_position_on_wall(w, i, n)
            if pt is None:
                continue
            px.append(pt[0])
            py.append(pt[1])
            pid = p.get("id", "")
            labels.append(pid)

    if px:
        ax.scatter(px, py, s=28, c="tab:red", alpha=0.85, edgecolors="darkred", linewidths=0.5, zorder=2, label="картины")
        # Подписи только для части точек, чтобы не перегружать
        step = max(1, len(px) // 25)
        for i in range(0, len(px), step):
            ax.annotate(labels[i], (px[i], py[i]), fontsize=5, alpha=0.8, xytext=(3, 3), textcoords="offset points")

    ax.set_aspect("equal")
    ax.set_xlabel("x (ед. плана)")
    ax.set_ylabel("y (ед. плана)")
    ax.set_title("Этаж 0 — план и локации картин (NMFA)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Сохранено: {OUTPUT_FILE}")
    print(f"Стен на этаже 0: {len(walls)}, картин отмечено: {len(px)}")


if __name__ == "__main__":
    main()
