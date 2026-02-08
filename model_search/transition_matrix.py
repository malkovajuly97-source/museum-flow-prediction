"""
Transition matrix between areas (zones 0-15) по траекториям BIRD, этаж 0.

Для каждой пары зон (from_zone, to_zone) считает:
- count: число переходов (соседние точки траектории по времени, A!=B)
- dependency: Edge load = count / total_transitions (доля 0-1)
- dependency_pct: доля в процентах (0-100)
Сохраняет transition_matrix.csv, transition_matrix.json, transition_matrix_chart.png в model_search/.
"""
import glob
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Переиспользуем парсинг DXF из build_floor0_paintings_with_zones (проект root)
import sys
BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
sys.path.insert(0, str(PROJECT_ROOT))
import build_floor0_paintings_with_zones as _b
# Указываем путь к DXF (файл в корне проекта)
_b.DXF_FILE = PROJECT_ROOT / "floor0_paintings_areas.dxf"
from build_floor0_paintings_with_zones import (
    parse_dxf_zones_and_contours,
    _point_inside,
    _distance_to_polygon,
    NEAREST_POLYGON_MAX_DIST,
)

DXF_FILE = PROJECT_ROOT / "floor0_paintings_areas.dxf"
TRAJECTORIES_FOLDER = PROJECT_ROOT / "bird-dataset-main/data/normalized_trajectories"
OUTPUT_CSV = BASE / "transition_matrix.csv"
OUTPUT_JSON = BASE / "transition_matrix.json"
OUTPUT_CHART = BASE / "transition_matrix_chart.png"


def assign_point_to_zone(px: float, py: float, polygons_with_zone, zone_labels) -> int:
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
    if zone_labels:
        best_z, best_d2 = None, float("inf")
        for zx, zy, z in zone_labels:
            d2 = (px - zx) ** 2 + (py - zy) ** 2
            if d2 < best_d2:
                best_d2, best_z = d2, z
        if best_z is not None:
            return best_z
    return -1


def load_floor0_trajectories():
    """Загружает все треки этажа 0, возвращает список DataFrame (сортированы по timestamp)."""
    csv_files = glob.glob(str(TRAJECTORIES_FOLDER / "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Нет CSV в {TRAJECTORIES_FOLDER}")
    all_trajectories = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            df_floor0 = df[df["floorNumber"] == 0].copy()
            if len(df_floor0) > 0:
                trajectory_id = Path(csv_file).stem.replace("_traj_normalized", "")
                df_floor0["trajectory_id"] = trajectory_id
                df_floor0 = df_floor0.sort_values("timestamp").reset_index(drop=True)
                all_trajectories.append(df_floor0)
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file}: {e}")
    if not all_trajectories:
        raise ValueError("Не найдено траекторий для этажа 0")
    return all_trajectories


def compute_transition_matrix(polygons_with_zone, zone_labels, all_trajectories):
    """
    Для каждой траектории: последовательность зон по времени.
    Переход from_zone -> to_zone учитывается при соседних точках (zone_i != zone_j, оба >= 0).
    Возвращает: dict (from_zone, to_zone) -> count, set all_zones.
    """
    transitions = {}  # (from_zone, to_zone) -> count
    for df in all_trajectories:
        zones_seq = []
        for _, row in df.iterrows():
            x, y = float(row["x"]), float(row["y"])
            z = assign_point_to_zone(x, y, polygons_with_zone, zone_labels)
            zones_seq.append(z)

        for i in range(len(zones_seq) - 1):
            a, b = zones_seq[i], zones_seq[i + 1]
            if a >= 0 and b >= 0 and a != b:
                key = (a, b)
                transitions[key] = transitions.get(key, 0) + 1

    all_zones = set()
    for (a, b) in transitions:
        all_zones.add(a)
        all_zones.add(b)
    return transitions, all_zones


def main():
    print("Загрузка полигонов зон из DXF...")
    polygons_with_zone, zone_labels = parse_dxf_zones_and_contours()
    if not polygons_with_zone and not zone_labels:
        raise RuntimeError("Не удалось загрузить зоны из DXF.")
    print(f"  Контуров с зоной: {sum(1 for _, z in polygons_with_zone if z is not None)}")

    print("\nЗагрузка треков этажа 0...")
    all_trajectories = load_floor0_trajectories()
    print(f"  Траекторий: {len(all_trajectories)}")

    print("\nВычисление переходов между зонами...")
    transitions, all_zones = compute_transition_matrix(
        polygons_with_zone, zone_labels, all_trajectories
    )
    total_transitions = sum(transitions.values())
    print(f"  Всего переходов (A->B, A!=B): {total_transitions}")

    zones_sorted = sorted(all_zones)
    n = len(zones_sorted)
    zone_to_idx = {z: i for i, z in enumerate(zones_sorted)}

    # Матрица: rows = from, cols = to
    matrix = [[0] * n for _ in range(n)]
    matrix_dependency = [[0.0] * n for _ in range(n)]
    for (a, b), count in transitions.items():
        i, j = zone_to_idx[a], zone_to_idx[b]
        matrix[i][j] = count
        matrix_dependency[i][j] = count / total_transitions if total_transitions > 0 else 0.0

    # CSV: длинный формат (count + dependency + dependency_pct для всех переходов)
    rows_csv = []
    for (from_z, to_z), count in sorted(transitions.items()):
        dependency = count / total_transitions if total_transitions > 0 else 0.0
        dependency_pct = 100.0 * dependency
        rows_csv.append({
            "from_zone": from_z,
            "to_zone": to_z,
            "count": count,
            "dependency": round(dependency, 6),
            "dependency_pct": round(dependency_pct, 2),
        })
    df_trans = pd.DataFrame(rows_csv)
    df_trans.to_csv(OUTPUT_CSV, index=False)
    print(f"\nСохранено: {OUTPUT_CSV}")

    # JSON: матрица, зоны, dependency (Edge load), метаданные
    transitions_list = []
    for (a, b), c in sorted(transitions.items()):
        dep = c / total_transitions if total_transitions > 0 else 0.0
        dep_pct = 100.0 * dep
        transitions_list.append({
            "from_zone": int(a),
            "to_zone": int(b),
            "count": c,
            "dependency": round(dep, 6),
            "dependency_pct": round(dep_pct, 2),
        })
    out_json = {
        "zones": zones_sorted,
        "zone_to_idx": zone_to_idx,
        "matrix": matrix,
        "matrix_dependency": [[round(v, 6) for v in row] for row in matrix_dependency],
        "transitions_list": transitions_list,
        "n_trajectories": len(all_trajectories),
        "total_transitions": total_transitions,
        "params": {
            "dxf_file": str(DXF_FILE),
            "trajectories_folder": str(TRAJECTORIES_FOLDER),
        },
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {OUTPUT_JSON}")

    # Диаграмма: Edge load (dependency %) по всем переходам
    df_plot = df_trans.copy()
    df_plot["edge"] = df_plot["from_zone"].astype(str) + " -> " + df_plot["to_zone"].astype(str)
    df_plot = df_plot.sort_values("dependency_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(8, len(df_plot) * 0.25)))
    bars = ax.barh(df_plot["edge"], df_plot["dependency_pct"], color="steelblue", alpha=0.8)
    ax.set_xlabel("Edge load (%)")
    ax.set_ylabel("Переход (from_zone -> to_zone)")
    ax.set_title("Transition matrix: Edge load (dependency %) — BIRD dataset, этаж 0")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_CHART, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Сохранено: {OUTPUT_CHART}")

    # Вывод топ переходов (count + dependency %)
    top = sorted(transitions.items(), key=lambda x: -x[1])[:10]
    print("\nТоп-10 переходов (count, dependency %):")
    for (a, b), c in top:
        dep = 100.0 * c / total_transitions if total_transitions > 0 else 0
        print(f"  {a} -> {b}: {c} ({dep:.2f}%)")


if __name__ == "__main__":
    main()
