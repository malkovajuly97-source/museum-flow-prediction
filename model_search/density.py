"""
Density (presence intensity), Time of Presence (ToP) и Stop duration distribution по траекториям BIRD, этаж 0.

Разбивает план на сетку 1x1 м, считает в каждой ячейке:
- density: число точек траекторий
- time_of_presence: ToP(cell) = Σ (T_exit - T_entry) по всем пребываниям в ячейке
Stop duration: список длительностей остановок (run из 2+ точек в одной ячейке).
Статистика: mean, median, 75th/90th percentiles, proportion of long stops.
Сохраняет density_floor0.csv, density_floor0.json в model_search/.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
TRAJECTORIES_FOLDER = PROJECT_ROOT / "bird-dataset-main/data/normalized_trajectories"
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
OUTPUT_CSV = BASE / "density_floor0.csv"
OUTPUT_JSON = BASE / "density_floor0.json"

CELL_SIZE_M = 1.0  # размер ячейки в метрах
SCALE_FACTOR = 55.07 / 5401  # м/единица координат (как в create_trajectories_heatmap)
LONG_STOP_THRESHOLD_SEC = 30.0  # порог для "длинной" остановки (proportion of long stops)


def load_floor0_trajectories():
    """Загружает все треки этажа 0. Возвращает (list of DataFrame, all_x, all_y, n_traj)."""
    csv_files = glob.glob(str(TRAJECTORIES_FOLDER / "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Нет CSV в {TRAJECTORIES_FOLDER}")
    trajectories = []
    all_x, all_y = [], []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            df_floor0 = df[df["floorNumber"] == 0].copy()
            if len(df_floor0) > 0:
                df_floor0 = df_floor0.sort_values("timestamp").reset_index(drop=True)
                trajectories.append(df_floor0)
                all_x.extend(df_floor0["x"].astype(float).tolist())
                all_y.extend(df_floor0["y"].astype(float).tolist())
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file}: {e}")
    if not trajectories:
        raise ValueError("Не найдено траекторий для этажа 0")
    return trajectories, np.array(all_x), np.array(all_y), len(trajectories)


def get_cell_indices(x_m, y_m, x_edges, y_edges):
    """Возвращает (ix, iy) для каждой точки. Bin i: edges[i] <= x < edges[i+1]."""
    ix = np.searchsorted(x_edges, x_m, side="right") - 1
    iy = np.searchsorted(y_edges, y_m, side="right") - 1
    nx, ny = len(x_edges) - 1, len(y_edges) - 1
    ix = np.clip(ix, 0, nx - 1)
    iy = np.clip(iy, 0, ny - 1)
    return ix, iy


def compute_time_of_presence(trajectories, x_edges, y_edges, nx, ny):
    """
    ToP(cell) = Σ (T_exit - T_entry) по всем пребываниям.
    Для каждой траектории: runs последовательных точек в одной ячейке -> ToP_run = t_last - t_first.
    Возвращает (top_matrix, stop_durations) — список длительностей остановок (run из 2+ точек).
    """
    top_matrix = np.zeros((ny, nx))
    stop_durations = []
    for df in trajectories:
        x_m = df["x"].astype(float).values * SCALE_FACTOR
        y_m = df["y"].astype(float).values * SCALE_FACTOR
        ts = df["timestamp"].astype(float).values
        ix, iy = get_cell_indices(x_m, y_m, x_edges, y_edges)
        # Находим runs последовательных точек в одной ячейке
        i = 0
        while i < len(ix):
            cx, cy = ix[i], iy[i]
            j = i + 1
            while j < len(ix) and ix[j] == cx and iy[j] == cy:
                j += 1
            if j > i + 1:  # run из 2+ точек
                top_run = ts[j - 1] - ts[i]
                if top_run > 0:
                    top_matrix[cy, cx] += top_run
                    stop_durations.append(top_run)
            i = j
    return top_matrix, stop_durations


def main():
    print("Загрузка треков этажа 0...")
    trajectories, all_x, all_y, n_traj = load_floor0_trajectories()
    print(f"  Траекторий: {n_traj}, точек: {len(all_x)}")

    # Конвертируем в метры
    x_m = all_x * SCALE_FACTOR
    y_m = all_y * SCALE_FACTOR
    min_x_m, max_x_m = x_m.min(), x_m.max()
    min_y_m, max_y_m = y_m.min(), y_m.max()

    # Сетка 1 м
    x_edges = np.arange(min_x_m, max_x_m + CELL_SIZE_M * 0.5, CELL_SIZE_M)
    y_edges = np.arange(min_y_m, max_y_m + CELL_SIZE_M * 0.5, CELL_SIZE_M)

    # 2D гистограмма: число точек в каждой ячейке (density)
    heatmap, x_edges, y_edges = np.histogram2d(x_m, y_m, bins=[x_edges, y_edges])
    heatmap = heatmap.T  # для согласованной ориентации (y по строкам)

    ny, nx = heatmap.shape
    print(f"\nСетка: {nx} x {ny} ячеек (размер ячейки: {CELL_SIZE_M} м)")
    print(f"  Всего ячеек: {nx * ny}")
    print(f"  Ячеек с density > 0: {np.sum(heatmap > 0)}")

    # Time of Presence: ToP(cell) = Σ (T_exit - T_entry)
    print("\nВычисление Time of Presence...")
    top_matrix, stop_durations = compute_time_of_presence(trajectories, x_edges, y_edges, nx, ny)
    top_sum = top_matrix.sum()
    print(f"  ToP sum: {top_sum:.1f} сек ({top_sum / 60:.1f} мин)")

    # Stop duration stats
    stop_duration_stats = {}
    if stop_durations:
        arr = np.array(stop_durations)
        stop_duration_stats = {
            "n_stops": len(stop_durations),
            "mean_sec": round(float(np.mean(arr)), 2),
            "median_sec": round(float(np.median(arr)), 2),
            "p75_sec": round(float(np.percentile(arr, 75)), 2),
            "p90_sec": round(float(np.percentile(arr, 90)), 2),
            "long_stop_threshold_sec": LONG_STOP_THRESHOLD_SEC,
            "proportion_long_stops": round(float(np.mean(arr >= LONG_STOP_THRESHOLD_SEC)), 4),
        }
        print(f"\nStop duration (остановки 2+ точек):")
        print(f"  n_stops: {stop_duration_stats['n_stops']}")
        print(f"  mean: {stop_duration_stats['mean_sec']} сек, median: {stop_duration_stats['median_sec']} сек")
        print(f"  75th: {stop_duration_stats['p75_sec']} сек, 90th: {stop_duration_stats['p90_sec']} сек")
        print(f"  proportion of long stops (>{LONG_STOP_THRESHOLD_SEC} сек): {stop_duration_stats['proportion_long_stops']:.2%}")

    # Таблица: cell_x, cell_y, center_x_m, center_y_m, density, time_of_presence
    rows = []
    for iy in range(ny):
        for ix in range(nx):
            d = int(heatmap[iy, ix])
            top = float(top_matrix[iy, ix])
            if d > 0 or top > 0:  # сохраняем ячейки с точками или ToP
                cx = (x_edges[ix] + x_edges[ix + 1]) / 2
                cy = (y_edges[iy] + y_edges[iy + 1]) / 2
                rows.append({
                    "cell_x": ix,
                    "cell_y": iy,
                    "center_x_m": round(cx, 3),
                    "center_y_m": round(cy, 3),
                    "density": d,
                    "time_of_presence": round(top, 2),
                })
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nСохранено: {OUTPUT_CSV} ({len(df)} ячеек)")

    # JSON: матрицы, границы, метаданные
    out_json = {
        "matrix": heatmap.astype(int).tolist(),
        "matrix_time_of_presence": [[round(float(v), 2) for v in row] for row in top_matrix],
        "x_edges_m": [round(float(x), 4) for x in x_edges],
        "y_edges_m": [round(float(y), 4) for y in y_edges],
        "cell_size_m": CELL_SIZE_M,
        "n_cells_x": nx,
        "n_cells_y": ny,
        "n_trajectories": n_traj,
        "n_points": len(all_x),
        "density_max": int(heatmap.max()),
        "density_sum": int(heatmap.sum()),
        "time_of_presence_sum_sec": round(float(top_sum), 2),
        "time_of_presence_max_sec": round(float(top_matrix.max()), 2),
        "stop_duration_stats": stop_duration_stats,
        "params": {
            "trajectories_folder": str(TRAJECTORIES_FOLDER),
            "plan_file": str(PLAN_FILE),
        },
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {OUTPUT_JSON}")

    print(f"\nСтатистика density: min: {heatmap[heatmap > 0].min()}, max: {heatmap.max()}, sum: {heatmap.sum()}")
    top_nonzero = top_matrix[top_matrix > 0]
    if len(top_nonzero) > 0:
        print(f"Статистика ToP (сек): min: {top_nonzero.min():.1f}, max: {top_matrix.max():.1f}, sum: {top_sum:.1f}")


if __name__ == "__main__":
    main()
