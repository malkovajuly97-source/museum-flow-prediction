"""
Гипотезы: влияние окон (естественное освещение) на поведение в музее.
Проверка 5 гипотез: движение у окон, связь с остановками, экспонаты у окон.

1. Загружаем окна из DXF (слой Windows) или floor0_windows.json.
2. Признаки по траекториям: dist_window_mean, pct_near_window.
3. Объединяем с openness_and_movement, корреляции и графики.
4. Отчёт по 5 гипотезам + анализ экспонатов у окон (H5).

Запуск: из корня проекта
  python "model_search/Windows/windows_natural_light_analysis.py"
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Входы: план и траектории из корня; openness — из папки Openness
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
TRAJECTORIES_WITH_FEATURES = PROJECT_ROOT / "analysis_results/floor0_trajectories_with_features.csv"
OPENNESS_DIR = BASE.parent / "Openness and size of the space"
OPENNESS_AND_MOVEMENT_CSV = OPENNESS_DIR / "openness_and_movement.csv"
POINTS_WITH_ZONE_CSV = OPENNESS_DIR / "points_with_zone_and_width.csv"
# Экспонаты и наблюдения для гипотезы 5
PAINTINGS_WITH_ZONES_CSV = PROJECT_ROOT / "floor0_paintings_with_zones.csv"
ARTWORKS_CSV = PROJECT_ROOT / "bird-dataset-main/data/artworks_dataset.csv"
START_OBS_DIR = PROJECT_ROOT / "bird-dataset-main/data/start_obs_artworks"
END_OBS_DIR = PROJECT_ROOT / "bird-dataset-main/data/end_obs_artworks"

# Выходы — всё в папке Windows
WINDOWS_JSON = BASE / "floor0_windows.json"
WINDOWS_DXF = BASE / "floor0_plan_and_windows.dxf"
WINDOWS_DXF_LAYER = "Windows"
WINDOWS_ANALYSIS_DIR = BASE / "analysis"
WINDOWS_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
WINDOWS_AND_MOVEMENT_CSV = BASE / "windows_and_movement.csv"
WINDOW_FEATURES_CSV = BASE / "trajectory_window_features.csv"
HYPOTHESES_REPORT_MD = WINDOWS_ANALYSIS_DIR / "windows_hypotheses_report.md"
EXHIBITS_NEAR_WINDOWS_CSV = WINDOWS_ANALYSIS_DIR / "exhibits_near_windows_stats.csv"

# Радиус «рядом с окном» в единицах плана (как x,y траекторий). Подберите по масштабу.
NEAR_WINDOW_RADIUS = 250.0


def load_window_segments_from_dxf(path_dxf: Path, layer: str):
    """Загружает отрезки окон из DXF (LINE и LWPOLYLINE на указанном слое). Координаты без масштаба."""
    try:
        import ezdxf
    except ImportError:
        return []
    if not path_dxf.exists():
        return []
    try:
        doc = ezdxf.readfile(str(path_dxf))
        msp = doc.modelspace()
        lines = []
        for e in msp.query("LWPOLYLINE"):
            if getattr(e.dxf, "layer", "") != layer:
                continue
            try:
                pts = list(e.get_points("xy"))
            except Exception:
                continue
            for i in range(len(pts) - 1):
                p1 = (float(pts[i][0]), float(pts[i][1]))
                p2 = (float(pts[i + 1][0]), float(pts[i + 1][1]))
                lines.append(LineString([p1, p2]))
        for e in msp.query("LINE"):
            if getattr(e.dxf, "layer", "") != layer:
                continue
            try:
                s, en = e.dxf.start, e.dxf.end
                p1 = (float(s.x), float(s.y))
                p2 = (float(en.x), float(en.y))
                lines.append(LineString([p1, p2]))
            except Exception:
                continue
        return lines
    except Exception:
        return []


def load_window_segments(windows_path: Path):
    """Загружает список сегментов окон из JSON. Каждый сегмент — LineString по двум точкам."""
    if not windows_path.exists():
        return []
    with open(windows_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments") or []
    lines = []
    for seg in segments:
        pos = seg.get("position", [])
        if len(pos) >= 2:
            coords = [(pos[0]["x"], pos[0]["y"]), (pos[1]["x"], pos[1]["y"])]
            lines.append(LineString(coords))
    return lines


def get_window_lines():
    """Сначала пробует DXF, затем JSON. Возвращает список LineString."""
    lines = load_window_segments_from_dxf(WINDOWS_DXF, WINDOWS_DXF_LAYER)
    if lines:
        return lines
    return load_window_segments(WINDOWS_JSON)


def distance_to_nearest_window(px: float, py: float, window_lines: list) -> float:
    """Минимальное расстояние от точки (px, py) до любого сегмента окна."""
    if not window_lines:
        return np.nan
    p = Point(px, py)
    return min(ls.distance(p) for ls in window_lines)


def compute_point_window_features(
    df_points: pd.DataFrame, window_lines: list, near_radius: float
) -> pd.DataFrame:
    """Для каждой точки: dist_window, near_window (bool)."""
    x = df_points["x"].values
    y = df_points["y"].values
    n = len(x)
    dist_window = np.full(n, np.nan, dtype=float)
    near_window = np.zeros(n, dtype=bool)
    for i in range(n):
        d = distance_to_nearest_window(float(x[i]), float(y[i]), window_lines)
        dist_window[i] = d
        near_window[i] = not np.isnan(d) and d <= near_radius
    out = df_points[["trajectory_id", "x", "y"]].copy()
    out["dist_window"] = dist_window
    out["near_window"] = near_window
    return out


def aggregate_window_features_by_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """По траектории: dist_window_mean, dist_window_min, pct_near_window, n_points."""
    agg = df.groupby("trajectory_id").agg(
        dist_window_mean=("dist_window", "mean"),
        dist_window_min=("dist_window", "min"),
        pct_near_window=("near_window", "mean"),
        n_points=("dist_window", "count"),
    ).reset_index()
    return agg


def run_windows_analysis():
    """Основной пайплайн: окна + движение, корреляции, квартили, графики, отчёт по 5 гипотезам."""
    window_lines = get_window_lines()
    if not window_lines:
        print(
            "Сегменты окон не найдены. Добавьте DXF с слоем 'Windows' (floor0_plan_and_windows.dxf)\n"
            "  или заполните floor0_windows.json."
        )
        return

    print(f"Загружено сегментов окон: {len(window_lines)}")
    print(f"Радиус «рядом с окном»: {NEAR_WINDOW_RADIUS} (в единицах плана)")

    # Точки траекторий (из папки Openness или analysis_results)
    if POINTS_WITH_ZONE_CSV.exists():
        df_points = pd.read_csv(POINTS_WITH_ZONE_CSV)
    else:
        if not TRAJECTORIES_WITH_FEATURES.exists():
            print("Не найден файл точек. Запустите openness_space_analysis.py (этап 1) в папке Openness.")
            return
        df_points = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_points["trajectory_id"] = df_points["trajectory_id"].astype(str)
    df_points = df_points[["trajectory_id", "x", "y"]].drop_duplicates()

    # Признаки окон по точкам
    df_win = compute_point_window_features(df_points, window_lines, NEAR_WINDOW_RADIUS)
    df_win_agg = aggregate_window_features_by_trajectory(df_win)
    df_win_agg.to_csv(WINDOW_FEATURES_CSV, index=False)
    print(f"  Признаки по окнам: {WINDOW_FEATURES_CSV}")

    # Объединение с движением (openness_and_movement из папки Openness)
    if not OPENNESS_AND_MOVEMENT_CSV.exists():
        print("Не найден openness_and_movement.csv. Сначала запустите openness_space_analysis.py в папке Openness.")
        return
    df_mov = pd.read_csv(OPENNESS_AND_MOVEMENT_CSV)
    df_mov["trajectory_id"] = df_mov["trajectory_id"].astype(str)
    df_merged = df_mov.merge(
        df_win_agg[["trajectory_id", "dist_window_mean", "dist_window_min", "pct_near_window"]],
        on="trajectory_id",
        how="left",
    )
    df_merged.to_csv(WINDOWS_AND_MOVEMENT_CSV, index=False)
    print(f"  Окна + движение: {WINDOWS_AND_MOVEMENT_CSV} ({len(df_merged)} траекторий)")

    # Переменные для анализа
    window_cols = ["dist_window_mean", "dist_window_min", "pct_near_window"]
    movement_cols = ["speed", "duration", "nb_stops", "nb_items", "length", "stop_intensity"]
    movement_cols = [c for c in movement_cols if c in df_merged.columns]

    # Корреляции
    analysis_cols = [c for c in window_cols + movement_cols if c in df_merged.columns]
    df_clean = df_merged.dropna(subset=window_cols)
    corr = None
    if len(df_clean) >= 5:
        corr = df_clean[analysis_cols].corr()
        corr.to_csv(WINDOWS_ANALYSIS_DIR / "windows_correlation_matrix.csv")
        print(f"  Корреляции: {WINDOWS_ANALYSIS_DIR / 'windows_correlation_matrix.csv'}")

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
        ax.set_title("Correlations: windows (natural light) vs movement")
        plt.tight_layout()
        plt.savefig(WINDOWS_ANALYSIS_DIR / "windows_correlation_heatmap.png", dpi=150, bbox_inches="tight")
        plt.close()

    # Квартили dist_window_mean -> speed, nb_stops
    for var in ["dist_window_mean", "pct_near_window"]:
        if var not in df_merged.columns:
            continue
        df_q = df_merged.dropna(subset=[var]).copy()
        df_q["quartile"] = pd.qcut(
            df_q[var], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop"
        )
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for ax, m in zip(axes, ["speed", "nb_stops"]):
            if m not in df_q.columns:
                ax.set_visible(False)
                continue
            ax.boxplot(
                [df_q[df_q["quartile"] == q][m].values for q in ["Q1", "Q2", "Q3", "Q4"]],
                tick_labels=["Q1", "Q2", "Q3", "Q4"],
                patch_artist=True,
            )
            ax.set_xlabel(f"Quartile {var}")
            ax.set_ylabel(m)
            ax.set_title(f"{m} by quartile of {var}")
            ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        safe_var = var.replace(".", "_")
        plt.savefig(
            WINDOWS_ANALYSIS_DIR / f"windows_boxplot_{safe_var}.png",
            dpi=150,
            bbox_inches="tight",
        )
        plt.close()
    print(f"  Графики: {WINDOWS_ANALYSIS_DIR}")

    # Scatter: расстояние до окна vs скорость / nb_stops
    if "dist_window_mean" in df_merged.columns and "speed" in df_merged.columns:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        axes[0].scatter(df_merged["dist_window_mean"], df_merged["speed"], alpha=0.6, s=40)
        axes[0].set_xlabel("dist_window_mean")
        axes[0].set_ylabel("speed")
        axes[0].set_title("Distance to window vs speed")
        axes[0].grid(True, alpha=0.3)
        if "nb_stops" in df_merged.columns:
            axes[1].scatter(df_merged["dist_window_mean"], df_merged["nb_stops"], alpha=0.6, s=40)
            axes[1].set_xlabel("dist_window_mean")
            axes[1].set_ylabel("nb_stops")
            axes[1].set_title("Distance to window vs nb_stops")
            axes[1].grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(
            WINDOWS_ANALYSIS_DIR / "windows_scatter_dist_vs_movement.png",
            dpi=150,
            bbox_inches="tight",
        )
        plt.close()

    # Отчёт по 5 гипотезам и анализ экспонатов у окон (H5)
    run_hypotheses_report(df_merged, corr)
    run_exhibits_near_windows_analysis(window_lines)

    print("\nАнализ окон завершён. Результаты в", BASE, "и", WINDOWS_ANALYSIS_DIR)


def run_hypotheses_report(df_merged: pd.DataFrame, corr: pd.DataFrame):
    """Пишет отчёт по 5 гипотезам: выводы по корреляциям и квартилям."""
    lines = ["# Проверка гипотез: окна и поведение в музее\n"]
    if corr is None or df_merged is None or len(df_merged) < 5:
        lines.append("Недостаточно данных для выводов.\n")
        WINDOWS_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        (WINDOWS_ANALYSIS_DIR / "windows_hypotheses_report.md").write_text("\n".join(lines), encoding="utf-8")
        return

    def corr_val(a, b):
        if a not in corr.columns or b not in corr.columns:
            return np.nan
        return corr.loc[a, b]

    # H1: Окна ускоряют движение (проходные зоны)
    r_speed_pct = corr_val("pct_near_window", "speed")
    r_speed_dist = corr_val("dist_window_mean", "speed")
    h1 = "подтверждается" if not np.isnan(r_speed_pct) and r_speed_pct > 0.15 else (
        "не подтверждается" if not np.isnan(r_speed_pct) and r_speed_pct < -0.15 else "неоднозначно"
    )
    lines.append("## 1. Окна ускоряют движение (проходные зоны)\n")
    lines.append(f"- Корреляция pct_near_window ↔ speed: {r_speed_pct:.3f}" if not np.isnan(r_speed_pct) else "- Нет данных")
    lines.append(f"- Вывод: гипотеза **{h1}** (больше времени у окон → выше скорость).\n")

    # H2: Окна замедляют / притягивают
    r_stops_pct = corr_val("pct_near_window", "nb_stops")
    h2 = "подтверждается" if not np.isnan(r_stops_pct) and r_stops_pct > 0.15 else (
        "не подтверждается" if not np.isnan(r_stops_pct) and r_stops_pct < -0.15 else "неоднозначно"
    )
    lines.append("## 2. Окна замедляют / притягивают (люди задерживаются у света)\n")
    lines.append(f"- Корреляция pct_near_window ↔ nb_stops: {r_stops_pct:.3f}" if not np.isnan(r_stops_pct) else "- Нет данных")
    lines.append(f"- Вывод: гипотеза **{h2}** (больше времени у окон → больше остановок).\n")

    # H3: Чем дальше от окон, тем иначе двигаются
    r_dist_speed = corr_val("dist_window_mean", "speed")
    r_dist_stops = corr_val("dist_window_mean", "nb_stops")
    lines.append("## 3. Чем дальше от окон, тем иначе двигаются\n")
    lines.append(f"- dist_window_mean ↔ speed: {r_dist_speed:.3f}; dist_window_mean ↔ nb_stops: {r_dist_stops:.3f}")
    lines.append("- Вывод: по знаку корреляций видно, меняются ли скорость и число остановок с расстоянием до окон.\n")

    # H4: Доля времени у окон связана с числом остановок
    lines.append("## 4. Доля времени у окон связана с числом остановок\n")
    lines.append(f"- Корреляция pct_near_window ↔ nb_stops: {r_stops_pct:.3f}" if not np.isnan(r_stops_pct) else "- Нет данных")
    lines.append("- Вывод: связь есть, если |r| > 0.15–0.2.\n")

    # H5 — кратко, детали в разделе экспонатов
    lines.append("## 5. Чаще ли смотрят экспонаты у окон, дольше ли у них стоят\n")
    lines.append("- См. раздел «Экспонаты у окон» ниже и файл exhibits_near_windows_stats.csv.\n")

    WINDOWS_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    (WINDOWS_ANALYSIS_DIR / "windows_hypotheses_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  Отчёт по гипотезам: {HYPOTHESES_REPORT_MD}")


def run_exhibits_near_windows_analysis(window_lines: list):
    """Гипотеза 5: экспонаты у окон — чаще ли смотрят, дольше ли стоят. Пишет CSV и дополняет отчёт."""
    if not window_lines:
        return
    if not PAINTINGS_WITH_ZONES_CSV.exists():
        print("  Пропуск H5: не найден floor0_paintings_with_zones.csv")
        return

    paintings = pd.read_csv(PAINTINGS_WITH_ZONES_CSV)
    if "x" not in paintings.columns or "y" not in paintings.columns:
        print("  Пропуск H5: в paintings нет x, y")
        return

    # Расстояние до окна для каждого экспоната
    dist = []
    for _, row in paintings.iterrows():
        d = distance_to_nearest_window(float(row["x"]), float(row["y"]), window_lines)
        dist.append(d)
    paintings = paintings.copy()
    paintings["dist_to_window"] = dist
    paintings["near_window"] = paintings["dist_to_window"].notna() & (paintings["dist_to_window"] <= NEAR_WINDOW_RADIUS)

    # Наблюдения: число просмотров и среднее время просмотра по экспонату
    obs_rows = []
    for start_path in START_OBS_DIR.glob("items_*.csv"):
        if "_end" in start_path.stem:
            continue
        tid = start_path.stem.replace("items_", "")
        end_path = END_OBS_DIR / f"items_{tid}_end.csv"
        if not end_path.exists():
            continue
        try:
            df_s = pd.read_csv(start_path)
            df_e = pd.read_csv(end_path)
        except Exception:
            continue
        df_s = df_s[df_s["floorNumber"] == 0]
        df_e = df_e[df_e["floorNumber"] == 0]
        for _, s in df_s.iterrows():
            pid = str(s["paintingId"])
            t0 = s["timestamp"]
            ends = df_e[df_e["paintingId"].astype(str) == pid]
            ends = ends[ends["timestamp"] > t0]
            if len(ends) == 0:
                continue
            dur = ends["timestamp"].min() - t0
            if 0 < dur < 3600:
                obs_rows.append({"paintingId": pid, "trajectory_id": tid, "duration": dur})
    if not obs_rows:
        print("  Пропуск H5: нет данных наблюдений (start_obs/end_obs)")
        return

    obs_df = pd.DataFrame(obs_rows)
    by_painting = obs_df.groupby("paintingId").agg(
        n_observations=("duration", "count"),
        mean_observation_time=("duration", "mean"),
    ).reset_index()
    by_painting = by_painting.rename(columns={"paintingId": "id"})
    paintings["id"] = paintings["id"].astype(str)
    merged = paintings.merge(by_painting, on="id", how="left")
    merged["n_observations"] = merged["n_observations"].fillna(0).astype(int)

    near = merged[merged["near_window"]]
    far = merged[~merged["near_window"]]
    if len(near) == 0 or len(far) == 0:
        print("  Пропуск H5: нет экспонатов в одной из групп (near/far)")
        return

    stats = []
    for label, sub in [("near_window", near), ("far_from_window", far)]:
        stats.append({
            "group": label,
            "n_exhibits": len(sub),
            "n_observations_total": sub["n_observations"].sum(),
            "mean_observations_per_exhibit": sub["n_observations"].mean(),
            "mean_observation_time_sec": sub["mean_observation_time"].mean(),
        })
    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(EXHIBITS_NEAR_WINDOWS_CSV, index=False)
    print(f"  Экспонаты у окон (H5): {EXHIBITS_NEAR_WINDOWS_CSV}")

    # Дополняем отчёт
    report_path = WINDOWS_ANALYSIS_DIR / "windows_hypotheses_report.md"
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8")
        add = "\n---\n## Экспонаты у окон (гипотеза 5)\n\n"
        add += f"- Экспонатов «у окна» (dist ≤ {NEAR_WINDOW_RADIUS}): {len(near)}; вдали от окон: {len(far)}.\n"
        add += f"- Среднее число наблюдений на экспонат: у окна {near['n_observations'].mean():.2f}, вдали {far['n_observations'].mean():.2f}.\n"
        add += f"- Среднее время просмотра (с): у окна {near['mean_observation_time'].mean():.1f}, вдали {far['mean_observation_time'].mean():.1f}.\n"
        more_obs_near = near["n_observations"].mean() > far["n_observations"].mean()
        longer_near = near["mean_observation_time"].mean() > far["mean_observation_time"].mean()
        h5_ok = more_obs_near and longer_near
        if h5_ok:
            add += "- Вывод: гипотеза 5 **подтверждается** (у экспонатов у окон в среднем больше наблюдений и дольше время просмотра).\n"
        else:
            add += "- Вывод: гипотеза 5 **не подтверждается** (у экспонатов у окон не больше наблюдений и не дольше время просмотра, чем вдали).\n"
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(add)


if __name__ == "__main__":
    run_windows_analysis()
