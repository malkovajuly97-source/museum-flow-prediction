import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from sklearn.cluster import KMeans
from scipy.ndimage import label as cc_label
from shapely.geometry import LineString, Point


# --------- Загрузка траекторий и расчёт heatmap / time_heatmap ---------

TRAJ_DIR = Path("bird-dataset-main/data/normalized_trajectories")
PLAN_FILE = Path("bird-dataset-main/data/NMFA_3floors_plan.json")


def load_trajectories_floor0():
    csv_files = list(TRAJ_DIR.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"Не найдено CSV файлов в {TRAJ_DIR}")

    print(f"Найдено {len(csv_files)} файлов с траекториями")

    all_x = []
    all_y = []
    all_floors = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            all_x.extend(df["x"].values)
            all_y.extend(df["y"].values)
            all_floors.extend(df["floorNumber"].values)
            print(f"Загружен {csv_file.name}: {len(df)} точек")
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file.name}: {e}")

    all_x = np.array(all_x)
    all_y = np.array(all_y)
    all_floors = np.array(all_floors)

    print(f"\nВсего точек до фильтрации: {len(all_x)}")
    print(f"Этажи: {np.unique(all_floors)}")

    floor_mask = all_floors == 0
    all_x = all_x[floor_mask]
    all_y = all_y[floor_mask]
    all_floors = all_floors[floor_mask]

    print(f"\nТочек на этаже 0: {len(all_x)}")
    print(f"Диапазон X (ед.): {all_x.min():.2f} - {all_x.max():.2f}")
    print(f"Диапазон Y (ед.): {all_y.min():.2f} - {all_y.max():.2f}")

    return all_x, all_y


def compute_heatmaps():
    all_x, all_y = load_trajectories_floor0()

    # Коэффициент масштабирования: 5401 единиц = 55.07 метров
    SCALE_FACTOR = 55.07 / 5401

    all_x_m = all_x * SCALE_FACTOR
    all_y_m = all_y * SCALE_FACTOR

    # Параметры сетки такие же, как в create_trajectories_heatmap.py
    cell_size_units = 50.0
    cell_size_meters = cell_size_units * SCALE_FACTOR
    print(f"\nРазмер ячейки: {cell_size_units} ед. ({cell_size_meters:.2f} м)")

    min_x_m, max_x_m = all_x_m.min(), all_x_m.max()
    min_y_m, max_y_m = all_y_m.min(), all_y_m.max()

    padding_m = 2.0
    min_x_m -= padding_m
    max_x_m += padding_m
    min_y_m -= padding_m
    max_y_m += padding_m

    # Сетка в исходных единицах координат
    x_bins_units = np.arange(all_x.min(), all_x.max() + cell_size_units, cell_size_units)
    y_bins_units = np.arange(all_y.min(), all_y.max() + cell_size_units, cell_size_units)

    # 2D гистограмма по точкам
    heatmap, x_edges, y_edges = np.histogram2d(all_x, all_y, bins=[x_bins_units, y_bins_units])
    heatmap = heatmap.T  # для согласованной ориентации

    # Время в каждой ячейке
    TIME_STEP_SECONDS = 2.0
    time_heatmap = heatmap.astype(float) * TIME_STEP_SECONDS

    # Границы в метрах для отображения
    x_edges_m = x_edges * SCALE_FACTOR
    y_edges_m = y_edges * SCALE_FACTOR
    extent = [x_edges_m[0], x_edges_m[-1], y_edges_m[0], y_edges_m[-1]]

    return heatmap, time_heatmap, x_edges_m, y_edges_m, extent


def draw_floor_plan(ax, plan_file: Path, scale_factor: float) -> bool:
    if not plan_file.exists():
        return False


def load_walls(plan_file: Path, scale_factor: float):
    """Загружаем стены этажа 0 как LineString в метрах."""
    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    walls = []
    for floor in plan_data.get("floors", []):
        if floor.get("number", 0) != 0:
            continue
        for wall in floor.get("walls", []):
            pos = wall.get("position", [])
            if len(pos) >= 2:
                coords = [(p["x"] * scale_factor, p["y"] * scale_factor) for p in pos]
                walls.append(LineString(coords))
    return walls


def compute_width_map(x_edges_m: np.ndarray, y_edges_m: np.ndarray, plan_file: Path) -> np.ndarray:
    """Оцениваем ширину прохода в центре каждой ячейки как 2 * min distance до стен."""
    SCALE_FACTOR = 55.07 / 5401
    walls = load_walls(plan_file, SCALE_FACTOR)

    H = len(y_edges_m) - 1
    W = len(x_edges_m) - 1
    widths = np.zeros((H, W), dtype=float)

    for iy in range(H):
        y_center = 0.5 * (y_edges_m[iy] + y_edges_m[iy + 1])
        for ix in range(W):
            x_center = 0.5 * (x_edges_m[ix] + x_edges_m[ix + 1])
            p = Point(x_center, y_center)
            if not walls:
                widths[iy, ix] = 0.0
                continue
            d_min = min(w.distance(p) for w in walls)
            widths[iy, ix] = 2.0 * d_min  # грубая оценка полной ширины прохода

    return widths

    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            plan_data = json.load(f)

        for floor in plan_data.get("floors", []):
            if floor.get("number", 0) == 0:
                for wall in floor.get("walls", []):
                    if len(wall.get("position", [])) >= 2:
                        x_coords = [pos["x"] * scale_factor for pos in wall["position"]]
                        y_coords = [pos["y"] * scale_factor for pos in wall["position"]]
                        ax.plot(
                            x_coords,
                            y_coords,
                            "w-",
                            linewidth=1.0,
                            alpha=0.5,
                            zorder=10,
                        )
        return True
    except Exception as e:
        print(f"Не удалось загрузить план этажа: {e}")
        return False


# --------- Кластеризация зон по (density, ToP) ---------


def cluster_zones(heatmap: np.ndarray, time_heatmap: np.ndarray, n_clusters: int = 4):
    # Векторизуем ячейки
    H, W = heatmap.shape
    density_flat = heatmap.reshape(-1)
    time_flat = time_heatmap.reshape(-1)

    # Берём только ячейки, где что-то происходило
    mask = (density_flat > 0) | (time_flat > 0)
    if not np.any(mask):
        raise ValueError("Все ячейки пусты, кластеризовать нечего")

    # Лог-нормализация признаков (сглаживаем хвост)
    d_feat = np.log1p(density_flat[mask])
    t_feat = np.log1p(time_flat[mask])

    # Стандартизация к [0, 1] по каждому признаку
    d_min, d_max = d_feat.min(), d_feat.max()
    t_min, t_max = t_feat.min(), t_feat.max()
    d_norm = (d_feat - d_min) / (d_max - d_min + 1e-9)
    t_norm = (t_feat - t_min) / (t_max - t_min + 1e-9)

    X = np.column_stack([d_norm, t_norm])

    print(f"\nКластеризация KMeans, точек: {X.shape[0]}, кластеры: {n_clusters}")
    kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init=20)
    cluster_ids = kmeans.fit_predict(X)
    centers = kmeans.cluster_centers_

    print("Кластерные центры (D_norm, T_norm):")
    for i, (dc, tc) in enumerate(centers):
        print(f"  Кластер {i}: D={dc:.3f}, T={tc:.3f}")

    # Определяем типы кластеров
    d_cent = centers[:, 0]
    t_cent = centers[:, 1]

    # bottleneck: и D, и T высокие
    bottleneck_idx = np.argmax(d_cent + t_cent)

    remaining = [i for i in range(n_clusters) if i != bottleneck_idx]
    # transit: D высокое, T относительно низкое
    transit_idx = max(remaining, key=lambda i: (d_cent[i] - t_cent[i]))

    remaining = [i for i in remaining if i != transit_idx]
    # interest: T высокое, D относительно низкое
    interest_idx = max(remaining, key=lambda i: (t_cent[i] - d_cent[i]))

    other_idxs = [i for i in range(n_clusters) if i not in {bottleneck_idx, transit_idx, interest_idx}]

    print(
        f"\nТипы кластеров:\n"
        f"  bottleneck: {bottleneck_idx}\n"
        f"  transit:    {transit_idx}\n"
        f"  interest:   {interest_idx}\n"
        f"  other:      {other_idxs}"
    )

    # Собираем карту меток
    labels_flat = np.zeros_like(density_flat, dtype=int)  # 0 = фон / другие
    full_cluster_ids = np.full_like(density_flat, -1, dtype=int)
    full_cluster_ids[mask] = cluster_ids

    labels_flat[np.isin(full_cluster_ids, other_idxs)] = 0
    labels_flat[full_cluster_ids == transit_idx] = 1
    labels_flat[full_cluster_ids == interest_idx] = 2
    labels_flat[full_cluster_ids == bottleneck_idx] = 3

    labels = labels_flat.reshape(H, W)
    return labels


def visualize_zones(labels: np.ndarray, extent, x_edges_m, y_edges_m):
    # 0 = фон, 1 = транзит, 2 = зона интереса, 3 = bottleneck
    colors = [
        (0.0, 0.0, 0.0, 0.0),   # фон — прозрачный
        (0.0, 1.0, 1.0, 0.8),   # транзит — циан
        (0.3, 1.0, 0.3, 0.9),   # зона интереса — зелёный
        (1.0, 0.3, 0.0, 0.9),   # bottleneck — оранжево‑красный
    ]
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(20, 16))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    im = ax.imshow(
        labels,
        extent=extent,
        cmap=cmap,
        origin="lower",
        interpolation="nearest",
        alpha=1.0,
    )

    # Легенда
    legend_patches = [
        Patch(color=colors[1], label="Transit (high D, low ToP)"),
        Patch(color=colors[2], label="Interest zone (low D, high ToP)"),
        Patch(color=colors[3], label="Bottleneck (high D, high ToP)"),
    ]
    ax.legend(
        handles=legend_patches,
        loc="upper right",
        framealpha=0.7,
        facecolor="black",
        edgecolor="white",
        labelcolor="white",
    )

    # План этажа поверх
    SCALE_FACTOR = 55.07 / 5401
    draw_floor_plan(ax, PLAN_FILE, SCALE_FACTOR)

    ax.set_xlabel("X координата (м)", fontsize=14, color="white")
    ax.set_ylabel("Y координата (м)", fontsize=14, color="white")
    ax.set_title(
        "Зоны по кластеризации (Density vs Time of Presence)",
        fontsize=16,
        fontweight="bold",
        color="white",
    )
    ax.tick_params(colors="white")
    ax.set_aspect("equal")
    ax.grid(False)

    output_file = "zones_density_time_clustering.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\nКарта кластеров сохранена в {output_file}")


def main():
    heatmap, time_heatmap, x_edges_m, y_edges_m, extent = compute_heatmaps()
    labels = cluster_zones(heatmap, time_heatmap, n_clusters=4)

    # Карта ширины прохода по плану (в метрах)
    width_map = compute_width_map(x_edges_m, y_edges_m, PLAN_FILE)

    # Сначала уберём совсем мелкий шум среди bottleneck-ов по связным компонентам,
    # затем отфильтруем bottleneck по ширине прохода.
    bottleneck_mask = labels == 3
    labeled_cc, num_cc = cc_label(bottleneck_mask)
    if num_cc > 0:
        sizes = np.bincount(labeled_cc.ravel())

        min_size = 5   # слишком мелкие пятна считаем шумом
        print(f"\nСвязных bottleneck-компонент: {num_cc}")
        for cc_id in range(1, num_cc + 1):
            size = sizes[cc_id]
            if size < min_size:
                labels[labeled_cc == cc_id] = 0  # шум -> other

    # Порог ширины для bottleneck (метры) — можно будет подстроить
    width_threshold = 2.0

    H, W = labels.shape
    for iy in range(H):
        for ix in range(W):
            if labels[iy, ix] == 3:  # кандидат в bottleneck
                w = width_map[iy, ix]
                if w <= 0:
                    continue
                if w > width_threshold:
                    # Широкая зона: оставляем как зону интереса, а не "узкое горлышко"
                    labels[iy, ix] = 2

    # Сохраняем метки в numpy и csv для дальнейшего анализа
    np.save("zones_labels.npy", labels)

    H, W = labels.shape
    flat = labels.reshape(-1)
    unique, counts = np.unique(flat, return_counts=True)
    print("\nРазмер сетки:", H, "x", W)
    print("Распределение классов (0=other,1=transit,2=interest,3=bottleneck):")
    for u, c in zip(unique, counts):
        print(f"  {u}: {c}")

    visualize_zones(labels, extent, x_edges_m, y_edges_m)


if __name__ == "__main__":
    main()

