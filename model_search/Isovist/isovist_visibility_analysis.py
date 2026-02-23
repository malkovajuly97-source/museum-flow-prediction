"""
Изовисты (видимость) и поведение посетителей.

Для точек траекторий (или центров зон) по плану стен считаем видимую область (ray-casting):
  - площадь видимости (isovist_area),
  - длина видимого периметра (isovist_perimeter).
Агрегируем по траектории (средняя/мин/макс видимость по пути) и ищем связи с поведением.

Запуск из корня проекта:
  python "model_search/Isovist/isovist_visibility_analysis.py"
  python "model_search/Isovist/isovist_visibility_analysis.py" --sample 5   # быстрее: каждая 5-я точка по траектории

Зависимости: openness_space_analysis (этап 1) выполнен — openness_and_movement.csv и точки.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Входы
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
TRAJECTORIES_WITH_FEATURES = PROJECT_ROOT / "analysis_results/floor0_trajectories_with_features.csv"
OPENNESS_DIR = PROJECT_ROOT / "model_search/Openness and size of the space"
OPENNESS_AND_MOVEMENT_CSV = OPENNESS_DIR / "openness_and_movement.csv"
POINTS_WITH_ZONE_CSV = OPENNESS_DIR / "points_with_zone_and_width.csv"

# Выходы — всё в папке Isovist
OUTPUT_DIR = BASE
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
POINTS_ISOVIST_CSV = OUTPUT_DIR / "points_isovist_features.csv"
TRAJECTORY_ISOVIST_CSV = OUTPUT_DIR / "trajectory_isovist_features.csv"
ISOVIST_AND_MOVEMENT_CSV = OUTPUT_DIR / "isovist_and_movement.csv"
ISOVIST_ANALYSIS_DIR = OUTPUT_DIR / "analysis"
ISOVIST_ANALYSIS_DIR.mkdir(exist_ok=True)

# Параметры ray-casting: число лучей, макс. длина луча в единицах плана
N_RAYS = 180  # шаг 2°
MAX_RAY_LENGTH = 15000.0
T_MIN = 1e-6  # не считать пересечение у самой точки наблюдения
# Сэмплирование: каждую N-ю точку (1 = все точки; 5 = в 5 раз быстрее)
SAMPLE_EVERY = 1  # задать через --sample 5 для ускорения


def load_wall_segments(plan_file: Path):
    """Стены этажа 0 как список отрезков (x1, y1, x2, y2) в координатах плана."""
    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)
    segments = []
    for floor in plan_data.get("floors", []):
        if floor.get("number", 0) != 0:
            continue
        for wall in floor.get("walls", []):
            pos = wall.get("position", [])
            if len(pos) >= 2:
                x1, y1 = pos[0]["x"], pos[0]["y"]
                x2, y2 = pos[1]["x"], pos[1]["y"]
                segments.append((float(x1), float(y1), float(x2), float(y2)))
    return segments


def ray_segment_intersection(ox: float, oy: float, dx: float, dy: float,
                            x1: float, y1: float, x2: float, y2: float):
    """
    Пересечение луча из (ox,oy) в направлении (dx,dy) с отрезком (x1,y1)-(x2,y2).
    Возвращает t (расстояние вдоль луча) или None.
    """
    seg_dx = x2 - x1
    seg_dy = y2 - y1
    det = -dx * seg_dy + dy * seg_dx
    if abs(det) < 1e-12:
        return None
    inv = 1.0 / det
    t = ((x1 - ox) * seg_dy - (y1 - oy) * seg_dx) * inv
    s = (dx * (y1 - oy) - dy * (x1 - ox)) * inv
    if t < T_MIN or s < -1e-9 or s > 1 + 1e-9:
        return None
    return t


def compute_isovist_at_point(ox: float, oy: float, segments: list,
                             n_rays: int = N_RAYS, max_ray: float = MAX_RAY_LENGTH):
    """
    Изовист из точки (ox, oy): лучи во все стороны, до стен.
    Возвращает (area, perimeter) в единицах плана (площадь в ед.², периметр в ед.).
    """
    angles = np.linspace(0, 2 * np.pi, n_rays, endpoint=False)
    distances = np.full(n_rays, max_ray, dtype=float)
    for i, a in enumerate(angles):
        dx, dy = np.cos(a), np.sin(a)
        best_t = max_ray
        for (x1, y1, x2, y2) in segments:
            t = ray_segment_intersection(ox, oy, dx, dy, x1, y1, x2, y2)
            if t is not None and t < best_t:
                best_t = t
        distances[i] = best_t

    # Полигон изовиста: вершины (ox + d*cos(a), oy + d*sin(a))
    xs = ox + distances * np.cos(angles)
    ys = oy + distances * np.sin(angles)
    # Площадь по формуле гаусса (shoelace)
    x_roll = np.roll(xs, 1)
    y_roll = np.roll(ys, 1)
    area = 0.5 * np.abs(np.sum(xs * y_roll - x_roll * ys))
    # Периметр
    dx = np.diff(np.append(xs, xs[0]))
    dy = np.diff(np.append(ys, ys[0]))
    perimeter = np.sum(np.hypot(dx, dy))
    return float(area), float(perimeter)


def compute_isovist_features_for_points(df_points: pd.DataFrame, segments: list) -> pd.DataFrame:
    """Для каждой точки: isovist_area, isovist_perimeter."""
    n = len(df_points)
    areas = np.full(n, np.nan, dtype=float)
    perims = np.full(n, np.nan, dtype=float)
    for i in range(n):
        ox = float(df_points["x"].iloc[i])
        oy = float(df_points["y"].iloc[i])
        a, p = compute_isovist_at_point(ox, oy, segments)
        areas[i] = a
        perims[i] = p
    out = df_points[["trajectory_id", "x", "y"]].copy()
    out["isovist_area"] = areas
    out["isovist_perimeter"] = perims
    return out


def aggregate_isovist_by_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """По траектории: средняя/мин/макс площадь и периметр изовиста."""
    agg = df.groupby("trajectory_id").agg(
        isovist_area_mean=("isovist_area", "mean"),
        isovist_area_min=("isovist_area", "min"),
        isovist_area_max=("isovist_area", "max"),
        isovist_perimeter_mean=("isovist_perimeter", "mean"),
        isovist_perimeter_min=("isovist_perimeter", "min"),
        isovist_perimeter_max=("isovist_perimeter", "max"),
        n_points=("isovist_area", "count"),
    ).reset_index()
    return agg


def run_analysis():
    """Корреляции изовист–движение, квартили, графики."""
    if not ISOVIST_AND_MOVEMENT_CSV.exists():
        print("Сначала выполните этап 1 (расчёт изовистов и объединение с движением).")
        return
    df = pd.read_csv(ISOVIST_AND_MOVEMENT_CSV)
    df["trajectory_id"] = df["trajectory_id"].astype(str)
    isovist_cols = [c for c in ["isovist_area_mean", "isovist_perimeter_mean",
                                "isovist_area_min", "isovist_area_max", "isovist_area_range"] if c in df.columns]
    movement_cols = [c for c in ["speed", "duration", "nb_stops", "nb_items", "length", "stop_intensity"] if c in df.columns]
    analysis_cols = isovist_cols + movement_cols
    analysis_cols = [c for c in analysis_cols if c in df.columns]
    if len(analysis_cols) < 2:
        print("Недостаточно колонок для анализа.")
        return
    corr = df[analysis_cols].corr()
    corr.to_csv(ISOVIST_ANALYSIS_DIR / "isovist_correlation_matrix.csv")
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
    ax.set_title("Correlations: isovist visibility vs movement")
    plt.tight_layout()
    plt.savefig(ISOVIST_ANALYSIS_DIR / "isovist_correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Корреляции: {ISOVIST_ANALYSIS_DIR / 'isovist_correlation_heatmap.png'}")

    # Квартильный анализ по isovist_area_mean и isovist_perimeter_mean
    quartile_vars = [v for v in ["isovist_area_mean", "isovist_perimeter_mean"] if v in df.columns]
    q_rows = []
    for var in quartile_vars:
        df_tmp = df.copy()
        try:
            df_tmp["quartile"] = pd.qcut(df_tmp[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        except ValueError:
            continue
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            sub = df_tmp[df_tmp["quartile"] == q]
            if len(sub) == 0:
                continue
            row = {"variable": var, "quartile": q, "n": len(sub)}
            for m in movement_cols:
                if m in sub.columns:
                    row[f"{m}_mean"] = sub[m].mean()
            q_rows.append(row)
    if q_rows:
        pd.DataFrame(q_rows).to_csv(ISOVIST_ANALYSIS_DIR / "quartile_analysis_isovist.csv", index=False)
        print(f"  Квартильный анализ: {ISOVIST_ANALYSIS_DIR / 'quartile_analysis_isovist.csv'}")

    # Scatter: площадь и периметр изовиста vs скорость, nb_stops, nb_items
    scatter_configs = [
        ("isovist_area_mean", "speed"), ("isovist_perimeter_mean", "speed"),
        ("isovist_area_mean", "nb_stops"), ("isovist_area_mean", "nb_items"),
    ]
    for xcol, ycol in scatter_configs:
        if xcol not in df.columns or ycol not in df.columns:
            continue
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(df[xcol], df[ycol], alpha=0.5, s=20)
        ax.set_xlabel(xcol)
        ax.set_ylabel(ycol)
        ax.set_title(f"{xcol} vs {ycol}")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        safe_name = f"isovist_scatter_{xcol}_vs_{ycol}.png"
        plt.savefig(ISOVIST_ANALYSIS_DIR / safe_name, dpi=150, bbox_inches="tight")
        plt.close()
    print(f"  Scatter-графики: {ISOVIST_ANALYSIS_DIR}")

    # Boxplot: speed и nb_stops по квартилям isovist_area_mean
    var = "isovist_area_mean"
    if var in df.columns:
        try:
            df_q = df.copy()
            df_q["quartile"] = pd.qcut(df_q[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
            df_q = df_q.dropna(subset=["quartile"])
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            for ax, ycol in zip(axes, ["speed", "nb_stops"]):
                if ycol not in df_q.columns:
                    ax.set_visible(False)
                    continue
                ax.boxplot(
                    [df_q[df_q["quartile"] == q][ycol].values for q in ["Q1", "Q2", "Q3", "Q4"]],
                    tick_labels=["Q1", "Q2", "Q3", "Q4"],
                    patch_artist=True,
                )
                ax.set_xlabel(f"Квартиль {var}")
                ax.set_ylabel(ycol)
                ax.set_title(f"{ycol} по квартилям изовиста (площадь)")
                ax.grid(True, alpha=0.3, axis="y")
            plt.tight_layout()
            plt.savefig(ISOVIST_ANALYSIS_DIR / "boxplot_speed_nb_stops_by_quartile_isovist.png", dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  Boxplot по квартилям: {ISOVIST_ANALYSIS_DIR / 'boxplot_speed_nb_stops_by_quartile_isovist.png'}")
        except Exception:
            pass
    print("Анализ сохранён в", ISOVIST_ANALYSIS_DIR)


def main():
    global SAMPLE_EVERY
    if len(sys.argv) >= 2 and sys.argv[1] == "--sample" and len(sys.argv) >= 3:
        try:
            SAMPLE_EVERY = max(1, int(sys.argv[2]))
            sys.argv = [sys.argv[0]] + sys.argv[3:]
        except ValueError:
            pass

    print("=" * 60)
    print("ИЗОВИСТЫ: видимость по плану стен")
    print("=" * 60)

    if not PLAN_FILE.exists():
        raise FileNotFoundError(f"Не найден план: {PLAN_FILE}")
    segments = load_wall_segments(PLAN_FILE)
    print(f"Загружено отрезков стен (этаж 0): {len(segments)}")
    print(f"Лучей на точку: {N_RAYS}, макс. длина луча: {MAX_RAY_LENGTH}")

    # Точки траекторий
    if POINTS_WITH_ZONE_CSV.exists():
        df_points = pd.read_csv(POINTS_WITH_ZONE_CSV)
    else:
        if not TRAJECTORIES_WITH_FEATURES.exists():
            raise FileNotFoundError(
                "Нет точек. Запустите openness_space_analysis.py (этап 1) или подготовьте floor0_trajectories_with_features.csv"
            )
        df_points = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_points["trajectory_id"] = df_points["trajectory_id"].astype(str)
    df_points = df_points[["trajectory_id", "x", "y"]].drop_duplicates()
    if SAMPLE_EVERY > 1:
        # В каждой траектории оставляем каждую N-ю точку
        idx = df_points.groupby("trajectory_id").cumcount() % SAMPLE_EVERY == 0
        df_points = df_points.loc[idx].copy()
        print(f"Сэмплирование: каждая {SAMPLE_EVERY}-я точка по траектории, осталось {len(df_points)} точек")
    else:
        print(f"Точек для расчёта изовиста: {len(df_points)}")

    # Изовисты по точкам
    print("Расчёт изовистов (площадь и периметр видимости)...")
    df_isovist = compute_isovist_features_for_points(df_points, segments)
    df_isovist.to_csv(POINTS_ISOVIST_CSV, index=False)
    print(f"  Сохранено: {POINTS_ISOVIST_CSV}")

    # Агрегация по траектории
    df_agg = aggregate_isovist_by_trajectory(df_isovist)
    df_agg["isovist_area_range"] = df_agg["isovist_area_max"] - df_agg["isovist_area_min"]
    df_agg.to_csv(TRAJECTORY_ISOVIST_CSV, index=False)
    print(f"  По траекториям: {TRAJECTORY_ISOVIST_CSV} ({len(df_agg)} траекторий)")

    # Объединение с движением (openness_and_movement)
    if not OPENNESS_AND_MOVEMENT_CSV.exists():
        print("Нет openness_and_movement.csv. Сохраняем только признаки изовиста по траекториям.")
        run_analysis()
        return
    df_mov = pd.read_csv(OPENNESS_AND_MOVEMENT_CSV)
    df_mov["trajectory_id"] = df_mov["trajectory_id"].astype(str)
    isovist_cols = [c for c in df_agg.columns if c != "trajectory_id"]
    df_merged = df_mov.merge(df_agg[["trajectory_id"] + isovist_cols], on="trajectory_id", how="left")
    df_merged.to_csv(ISOVIST_AND_MOVEMENT_CSV, index=False)
    print(f"  Изовист + движение: {ISOVIST_AND_MOVEMENT_CSV} ({len(df_merged)} траекторий)")

    run_analysis()
    print("\nГотово. Дальше: смотреть корреляции в analysis/, при необходимости добавить признаки (см. README).")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--stage" and sys.argv[2] == "2":
        run_analysis()
    else:
        main()
