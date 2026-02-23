"""
Этап 1: Признаки открытости и размера пространства по траекториям (этаж 0).
Этап 2: Общий анализ — корреляции, квартили, графики (без типов поведения).

Скрипт расположен в model_search/Openness and size of the space/.
Входные данные и DXF берутся из корня проекта (PROJECT_ROOT).
Результаты сохраняются в эту же папку.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

# Папка скрипта и корень проекта (два уровня вверх)
BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import build_floor0_paintings_with_zones as _b
_b.DXF_FILE = PROJECT_ROOT / "floor0_paintings_areas.dxf"

from build_floor0_paintings_with_zones import (
    parse_dxf_zones_and_contours,
    _polygon_area,
    _point_inside,
    _distance_to_polygon,
    NEAREST_POLYGON_MAX_DIST,
)

# Пути: входы из корня проекта, выходы в папку скрипта
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
TRAJECTORIES_WITH_FEATURES = PROJECT_ROOT / "analysis_results/floor0_trajectories_with_features.csv"
SEMANTIC_FEATURES = PROJECT_ROOT / "analysis_results/floor0_semantic_features.csv"
OUTPUT_DIR = BASE
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ZONE_AREAS_CSV = OUTPUT_DIR / "zone_areas.csv"
POINTS_WITH_ZONE_CSV = OUTPUT_DIR / "points_with_zone_and_width.csv"
TRAJECTORY_OPENNESS_CSV = OUTPUT_DIR / "trajectory_openness_features.csv"
OPENNESS_AND_MOVEMENT_CSV = OUTPUT_DIR / "openness_and_movement.csv"
OPENNESS_ANALYSIS_DIR = OUTPUT_DIR / "openness_analysis"
OPENNESS_ANALYSIS_DIR.mkdir(exist_ok=True)

SCALE_FACTOR = 55.07 / 5401
CELL_SIZE_UNITS = 50.0


def assign_point_to_zone(px: float, py: float, polygons_with_zone, zone_labels) -> int:
    """Определяет зону (0–15) для точки (x, y) в координатах DXF/треков."""
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


def load_walls(plan_file: Path, scale_factor: float):
    """Стены этажа 0 как LineString в метрах (для расчёта ширины прохода)."""
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
    """Ширина прохода в каждой ячейке сетки (2 * min distance до стен). shape = (H, W)."""
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
            widths[iy, ix] = 2.0 * d_min
    return widths


def compute_zone_areas():
    """
    1.1. Площади зон из DXF. Возвращает (df_zone_areas, zone_id_to_area dict).
    Пороги малая/большая зона — по квартилям площади (по всем зонам с площадью > 0).
    """
    print("Загрузка полигонов зон из DXF...")
    polygons_with_zone, zone_labels = parse_dxf_zones_and_contours()
    if not polygons_with_zone:
        raise RuntimeError("Не удалось загрузить зоны из DXF.")

    from collections import defaultdict
    zone_areas_sum = defaultdict(float)
    for geom, zone in polygons_with_zone:
        if zone is None:
            continue
        area = _polygon_area(geom)
        zone_areas_sum[zone] += area

    zone_id_to_area = dict(zone_areas_sum)
    rows = [{"zone_id": z, "area": a} for z, a in sorted(zone_id_to_area.items())]
    df = pd.DataFrame(rows)
    df.to_csv(ZONE_AREAS_CSV, index=False)
    print(f"  Сохранено: {ZONE_AREAS_CSV} ({len(df)} зон)")

    # Квартили для меток малая/большая (только зоны с area > 0)
    areas = df["area"].values
    q25 = np.percentile(areas, 25)
    q75 = np.percentile(areas, 75)
    return df, zone_id_to_area, q25, q75


def assign_zones_and_width_to_points(
    df_points: pd.DataFrame,
    polygons_with_zone,
    zone_labels,
    zone_id_to_area: dict,
    q25: float,
    q75: float,
):
    """
    1.2. Для каждой точки: zone_id, zone_area, passage_width, is_small_zone, is_large_zone.
    """
    x = df_points["x"].values
    y = df_points["y"].values
    n = len(x)

    # Сетка для ширины прохода (как в cluster_density_time_zones)
    x_edges = np.arange(x.min(), x.max() + CELL_SIZE_UNITS, CELL_SIZE_UNITS)
    y_edges = np.arange(y.min(), y.max() + CELL_SIZE_UNITS, CELL_SIZE_UNITS)
    x_edges_m = x_edges * SCALE_FACTOR
    y_edges_m = y_edges * SCALE_FACTOR
    width_map = compute_width_map(x_edges_m, y_edges_m, PLAN_FILE)
    H, W = width_map.shape

    zone_ids = np.full(n, -1, dtype=int)
    zone_areas = np.full(n, np.nan, dtype=float)
    passage_widths = np.full(n, np.nan, dtype=float)

    for i in range(n):
        px, py = float(x[i]), float(y[i])
        z = assign_point_to_zone(px, py, polygons_with_zone, zone_labels)
        zone_ids[i] = z
        if z >= 0 and z in zone_id_to_area:
            zone_areas[i] = zone_id_to_area[z]

        # Ширина прохода: точка в метрах -> ячейка
        x_m, y_m = px * SCALE_FACTOR, py * SCALE_FACTOR
        ix = np.searchsorted(x_edges_m, x_m, side="right") - 1
        iy = np.searchsorted(y_edges_m, y_m, side="right") - 1
        ix = max(0, min(ix, W - 1))
        iy = max(0, min(iy, H - 1))
        passage_widths[i] = width_map[iy, ix]

    out = df_points[["trajectory_id", "x", "y"]].copy()
    out["zone_id"] = zone_ids
    out["zone_area"] = zone_areas
    out["passage_width"] = passage_widths
    out["is_small_zone"] = zone_areas < q25
    out["is_large_zone"] = zone_areas > q75
    return out


def aggregate_openness_by_trajectory(df_points_with_zone: pd.DataFrame) -> pd.DataFrame:
    """
    1.3. Агрегация по траектории: zone_area_mean, zone_area_min, zone_area_max,
    pct_small_zone, pct_large_zone, passage_width_mean.
    """
    agg = df_points_with_zone.groupby("trajectory_id").agg(
        zone_area_mean=("zone_area", "mean"),
        zone_area_min=("zone_area", "min"),
        zone_area_max=("zone_area", "max"),
        pct_small_zone=("is_small_zone", "mean"),  # доля точек в малых зонах
        pct_large_zone=("is_large_zone", "mean"),
        passage_width_mean=("passage_width", "mean"),
        n_points=("zone_id", "count"),
    ).reset_index()
    agg["pct_small_zone"] = agg["pct_small_zone"].fillna(0)
    agg["pct_large_zone"] = agg["pct_large_zone"].fillna(0)
    return agg


def run_general_analysis():
    """
    Этап 2: Общий анализ без типов поведения.
    Корреляции, квартильный анализ, scatter и boxplot по openness_and_movement.csv.
    """
    print("\n" + "=" * 60)
    print("ETAP 2: Obshchiy analiz (otkrytost/razmer prostranstva i dvizhenie)")
    print("=" * 60)

    if not OPENNESS_AND_MOVEMENT_CSV.exists():
        print(f"  Файл не найден: {OPENNESS_AND_MOVEMENT_CSV}. Сначала выполните этап 1.")
        return

    df = pd.read_csv(OPENNESS_AND_MOVEMENT_CSV)
    df["trajectory_id"] = df["trajectory_id"].astype(str)
    print(f"\nЗагружено траекторий: {len(df)}")

    openness_cols = ["distwall", "zone_area_mean", "passage_width_mean", "pct_small_zone", "pct_large_zone"]
    movement_cols = ["speed", "duration", "nb_stops", "nb_items", "length", "stop_intensity"]
    openness_cols = [c for c in openness_cols if c in df.columns]
    movement_cols = [c for c in movement_cols if c in df.columns]

    # --- Корреляции ---
    analysis_cols = openness_cols + movement_cols
    analysis_cols = [c for c in analysis_cols if c in df.columns]
    corr = df[analysis_cols].corr()
    corr.to_csv(OPENNESS_ANALYSIS_DIR / "correlation_matrix.csv")
    print(f"  Корреляционная матрица: {OPENNESS_ANALYSIS_DIR / 'correlation_matrix.csv'}")

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)
    plt.colorbar(im, ax=ax, shrink=0.8)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Correlations: openness/space size vs movement")
    plt.tight_layout()
    plt.savefig(OPENNESS_ANALYSIS_DIR / "correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Тепловая карта: {OPENNESS_ANALYSIS_DIR / 'correlation_heatmap.png'}")

    # --- Квартильный анализ ---
    quartile_vars = ["distwall", "zone_area_mean", "passage_width_mean"]
    quartile_vars = [v for v in quartile_vars if v in df.columns]
    q_rows = []
    for var in quartile_vars:
        df_tmp = df.copy()
        df_tmp["quartile"] = pd.qcut(df_tmp[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            sub = df_tmp[df_tmp["quartile"] == q]
            if len(sub) == 0:
                continue
            row = {"variable": var, "quartile": q, "n": len(sub)}
            for m in movement_cols:
                row[f"{m}_mean"] = sub[m].mean()
            q_rows.append(row)
    df_quart = pd.DataFrame(q_rows)
    if len(df_quart) > 0:
        df_quart.to_csv(OPENNESS_ANALYSIS_DIR / "quartile_analysis.csv", index=False)
        print(f"  Квартильный анализ: {OPENNESS_ANALYSIS_DIR / 'quartile_analysis.csv'}")

    # --- Scatter: открытость vs скорость ---
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, xcol in zip(axes, ["distwall", "zone_area_mean", "passage_width_mean"]):
        if xcol not in df.columns:
            ax.set_visible(False)
            continue
        ax.scatter(df[xcol], df["speed"], alpha=0.7, s=40)
        ax.set_xlabel(xcol)
        ax.set_ylabel("speed")
        ax.set_title(f"{xcol} vs speed")
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OPENNESS_ANALYSIS_DIR / "scatter_openness_vs_speed.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Scatter открытость vs speed: {OPENNESS_ANALYSIS_DIR / 'scatter_openness_vs_speed.png'}")

    # --- Boxplot: скорость по квартилям distwall / zone_area_mean / passage_width ---
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, var in zip(axes, ["distwall", "zone_area_mean", "passage_width_mean"]):
        if var not in df.columns:
            ax.set_visible(False)
            continue
        df_q = df.copy()
        df_q["quartile"] = pd.qcut(df_q[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        df_q = df_q.dropna(subset=["quartile"])
        ax.boxplot(
            [df_q[df_q["quartile"] == q]["speed"].values for q in ["Q1", "Q2", "Q3", "Q4"]],
            tick_labels=["Q1", "Q2", "Q3", "Q4"],
            patch_artist=True,
        )
        ax.set_xlabel(f"Kvartil {var}")
        ax.set_ylabel("speed")
        ax.set_title(f"Speed by quartile {var}")
        ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(OPENNESS_ANALYSIS_DIR / "boxplot_speed_by_quartile.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Boxplot скорость по квартилям: {OPENNESS_ANALYSIS_DIR / 'boxplot_speed_by_quartile.png'}")

    # --- Boxplot: nb_stops по квартилям ---
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, var in zip(axes, ["distwall", "zone_area_mean", "passage_width_mean"]):
        if var not in df.columns:
            ax.set_visible(False)
            continue
        df_q = df.copy()
        df_q["quartile"] = pd.qcut(df_q[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        df_q = df_q.dropna(subset=["quartile"])
        ax.boxplot(
            [df_q[df_q["quartile"] == q]["nb_stops"].values for q in ["Q1", "Q2", "Q3", "Q4"]],
            tick_labels=["Q1", "Q2", "Q3", "Q4"],
            patch_artist=True,
        )
        ax.set_xlabel(f"Kvartil {var}")
        ax.set_ylabel("nb_stops")
        ax.set_title(f"nb_stops by quartile {var}")
        ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(OPENNESS_ANALYSIS_DIR / "boxplot_nb_stops_by_quartile.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Boxplot nb_stops по квартилям: {OPENNESS_ANALYSIS_DIR / 'boxplot_nb_stops_by_quartile.png'}")

    print("\nЭтап 2 завершён. Результаты в", OPENNESS_ANALYSIS_DIR)


def main():
    print("=" * 60)
    print("ЭТАП 1: Признаки открытости и размера пространства")
    print("=" * 60)

    if not TRAJECTORIES_WITH_FEATURES.exists():
        raise FileNotFoundError(
            f"Не найден файл траекторий: {TRAJECTORIES_WITH_FEATURES}. Запустите prepare_floor0_data.py"
        )
    if not SEMANTIC_FEATURES.exists():
        raise FileNotFoundError(
            f"Не найден файл семантики: {SEMANTIC_FEATURES}. Запустите prepare_floor0_data.py"
        )
    if not PLAN_FILE.exists():
        raise FileNotFoundError(f"Не найден план музея: {PLAN_FILE}")

    # 1.1. Площади зон
    df_zone_areas, zone_id_to_area, q25, q75 = compute_zone_areas()
    print(f"  Квартили площади зоны: Q25={q25:.0f}, Q75={q75:.0f} (малая < Q25, большая > Q75)")

    polygons_with_zone, zone_labels = parse_dxf_zones_and_contours()

    # Загрузка точек (только trajectory_id, x, y)
    print("\nЗагрузка точек траекторий...")
    df_points = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_points["trajectory_id"] = df_points["trajectory_id"].astype(str)
    df_points = df_points[["trajectory_id", "x", "y"]].drop_duplicates()
    print(f"  Точек: {len(df_points)}")

    # 1.2. Привязка зона + площадь + ширина прохода
    print("\nПривязка зон и ширины прохода к точкам...")
    df_points_with_zone = assign_zones_and_width_to_points(
        df_points, polygons_with_zone, zone_labels, zone_id_to_area, q25, q75
    )
    df_points_with_zone.to_csv(POINTS_WITH_ZONE_CSV, index=False)
    print(f"  Сохранено: {POINTS_WITH_ZONE_CSV}")

    # 1.3. Агрегация по траектории
    print("\nАгрегация по траектории...")
    df_openness = aggregate_openness_by_trajectory(df_points_with_zone)

    # Добавляем distwall из семантики
    df_semantic = pd.read_csv(SEMANTIC_FEATURES)
    df_semantic["trajectory_id"] = df_semantic["trajectory_id"].astype(str)
    df_openness = df_openness.merge(
        df_semantic[["trajectory_id", "distwall"]], on="trajectory_id", how="left"
    )
    # Порядок колонок: trajectory_id, distwall, zone_area_mean, ...
    cols = ["trajectory_id", "distwall", "zone_area_mean", "zone_area_min", "zone_area_max",
            "pct_small_zone", "pct_large_zone", "passage_width_mean", "n_points"]
    df_openness = df_openness[[c for c in cols if c in df_openness.columns]]
    df_openness.to_csv(TRAJECTORY_OPENNESS_CSV, index=False)
    print(f"  Сохранено: {TRAJECTORY_OPENNESS_CSV} ({len(df_openness)} траекторий)")

    # 1.4. Объединение с метриками движения
    print("\nОбъединение с метриками движения...")
    move_cols = ["trajectory_id", "duration", "speed", "nb_items", "nb_stops", "length"]
    if "curvature" in df_semantic.columns:
        move_cols.append("curvature")
    if "avg_observation_time" in df_semantic.columns:
        move_cols.append("avg_observation_time")
    df_semantic_sub = df_semantic[[c for c in move_cols if c in df_semantic.columns]]
    df_merged = df_openness.merge(df_semantic_sub, on="trajectory_id", how="inner")
    df_merged["stop_intensity"] = df_merged["nb_stops"] / (df_merged["duration"] / 60.0 + 1e-9)
    df_merged.to_csv(OPENNESS_AND_MOVEMENT_CSV, index=False)
    print(f"  Сохранено: {OPENNESS_AND_MOVEMENT_CSV} ({len(df_merged)} траекторий)")

    print("\nЭтап 1 завершён.")
    print(f"  Зоны: {ZONE_AREAS_CSV}")
    print(f"  Точки с зоной и шириной: {POINTS_WITH_ZONE_CSV}")
    print(f"  Признаки открытости по траекториям: {TRAJECTORY_OPENNESS_CSV}")
    print(f"  Открытость + движение: {OPENNESS_AND_MOVEMENT_CSV}")

    run_general_analysis()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--stage" and sys.argv[2] == "2":
        run_general_analysis()
    else:
        main()
