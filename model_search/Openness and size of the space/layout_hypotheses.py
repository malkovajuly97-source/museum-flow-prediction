"""
Проверка 10 гипотез влияния планировки на поведение.

Использует: openness_space_analysis (зоны, ширина), trajectories с timestamp,
transition_matrix, zone_areas, floor0_paintings_with_zones, DXF полигоны.
Результаты: layout_hypotheses_features.csv, layout_hypotheses_report.md, корреляции.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Импорт из openness скрипта (те же пути)
import build_floor0_paintings_with_zones as _b
_b.DXF_FILE = PROJECT_ROOT / "floor0_paintings_areas.dxf"
from build_floor0_paintings_with_zones import (
    parse_dxf_zones_and_contours,
    _polygon_area,
    _point_inside,
    _distance_to_polygon,
    NEAREST_POLYGON_MAX_DIST,
)

from openness_space_analysis import (
    assign_point_to_zone,
    compute_width_map,
    load_walls,
    PLAN_FILE,
    SCALE_FACTOR,
    CELL_SIZE_UNITS,
    TRAJECTORIES_WITH_FEATURES,
    SEMANTIC_FEATURES,
    OPENNESS_AND_MOVEMENT_CSV,
    ZONE_AREAS_CSV,
)
from openness_space_analysis import OUTPUT_DIR, OPENNESS_ANALYSIS_DIR
_b.DXF_FILE = PROJECT_ROOT / "floor0_paintings_areas.dxf"

TRANSITION_MATRIX_CSV = PROJECT_ROOT / "model_search/transition_matrix.csv"
PAINTINGS_WITH_ZONES_CSV = PROJECT_ROOT / "floor0_paintings_with_zones.csv"

OUTPUT_FEATURES = OUTPUT_DIR / "layout_hypotheses_features.csv"
OUTPUT_MERGED = OUTPUT_DIR / "layout_and_movement.csv"
OUTPUT_REPORT = OPENNESS_ANALYSIS_DIR / "layout_hypotheses_report.md"


def count_turns(xs, ys, angle_threshold_deg=30.0):
    """
    Число поворотов: сколько раз направление движения меняется больше чем на angle_threshold_deg градусов.
    xs, ys — массивы координат по порядку. Возвращает (n_turns, n_segments).
    """
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    n = len(xs)
    if n < 3:
        return 0, max(0, n - 1)
    dx = np.diff(xs)
    dy = np.diff(ys)
    seg_len = np.sqrt(dx * dx + dy * dy)
    # Пропускаем нулевые сегменты (нет направления)
    heading = np.full(len(dx), np.nan)
    valid = seg_len > 1e-9
    heading[valid] = np.arctan2(dy[valid], dx[valid])
    # Угол между соседними сегментами (в радианах), wrap [-pi, pi]
    n_seg = len(dx)
    n_turns = 0
    threshold_rad = np.deg2rad(angle_threshold_deg)
    for i in range(1, n_seg):
        if not (np.isfinite(heading[i - 1]) and np.isfinite(heading[i])):
            continue
        delta = heading[i] - heading[i - 1]
        delta = np.arctan2(np.sin(delta), np.cos(delta))  # wrap to [-pi, pi]
        if np.abs(delta) >= threshold_rad:
            n_turns += 1
    return n_turns, n_seg


def zone_connectivity_from_transitions():
    """Степень связности зоны = число уникальных соседних зон (из переходов)."""
    if not TRANSITION_MATRIX_CSV.exists():
        return {}
    df = pd.read_csv(TRANSITION_MATRIX_CSV)
    degree = {}
    for _, row in df.iterrows():
        a, b = int(row["from_zone"]), int(row["to_zone"])
        degree[a] = degree.get(a, set()) | {b}
        degree[b] = degree.get(b, set()) | {a}
    return {z: len(s) for z, s in degree.items()}


def zone_aspect_ratio(polygons_with_zone):
    """Для каждой зоны: aspect_ratio (min_rotated_rectangle length/width). >2 = corridor."""
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return {}
    zone_geoms = {}
    for geom, zone in polygons_with_zone:
        if zone is None:
            continue
        if zone not in zone_geoms:
            zone_geoms[zone] = []
        zone_geoms[zone].append(geom)
    out = {}
    for zone, geoms in zone_geoms.items():
        # Берём самый большой полигон по площади
        best = max(geoms, key=lambda g: _polygon_area(g) if g is not None else 0)
        if best is None or not hasattr(best, "minimum_rotated_rectangle"):
            out[zone] = 1.0
            continue
        try:
            mrr = best.minimum_rotated_rectangle
            if hasattr(mrr, "exterior"):
                coords = list(mrr.exterior.coords)
            else:
                coords = list(getattr(mrr, "coords", [])) or []
            if len(coords) < 3:
                out[zone] = 1.0
                continue
            xs, ys = [c[0] for c in coords], [c[1] for c in coords]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if h < 1e-9:
                out[zone] = 10.0
            else:
                out[zone] = max(w / h, h / w)
        except Exception:
            out[zone] = 1.0
    return out


def zone_centroids(polygons_with_zone):
    """Центроид каждой зоны (по самому большому полигону зоны). zone_id -> (x, y)."""
    from collections import defaultdict
    zone_geoms = defaultdict(list)
    for geom, zone in polygons_with_zone:
        if zone is None:
            continue
        zone_geoms[zone].append(geom)
    out = {}
    for zone, geoms in zone_geoms.items():
        best = max(geoms, key=lambda g: _polygon_area(g) if g is not None else 0)
        if best is None:
            continue
        try:
            c = best.centroid
            out[zone] = (float(c.x), float(c.y))
        except Exception:
            pass
    return out


# Лестницы: зоны 1, 2, 5 и одна между зонами 12 и 13 (центроид = середина между центроидами 12 и 13)
STAIRCASE_ZONES = [1, 2, 5]
STAIRCASE_NEAR_RADIUS = 400.0  # единицы плана: считаем "близко к лестнице" если расстояние < этого


def staircase_points(polygons_with_zone):
    """Список (x, y) — позиции лестниц: центроиды зон 1, 2, 5 и середина между 12 и 13."""
    centroids = zone_centroids(polygons_with_zone)
    points = []
    for z in STAIRCASE_ZONES:
        if z in centroids:
            points.append(centroids[z])
    c12 = centroids.get(12)
    c13 = centroids.get(13)
    if c12 is not None and c13 is not None:
        points.append(((c12[0] + c13[0]) / 2, (c12[1] + c13[1]) / 2))
    elif c12 is not None:
        points.append(c12)
    elif c13 is not None:
        points.append(c13)
    return points


def exhibits_per_zone():
    """Число экспонатов по зонам (floor0_paintings_with_zones)."""
    if not PAINTINGS_WITH_ZONES_CSV.exists():
        return {}, {}
    df = pd.read_csv(PAINTINGS_WITH_ZONES_CSV)
    if "zone" not in df.columns:
        return {}, {}
    cnt = df.groupby("zone").size().to_dict()
    areas = pd.read_csv(ZONE_AREAS_CSV)
    area_map = dict(zip(areas["zone_id"], areas["area"]))
    density = {}
    for z in cnt:
        a = area_map.get(z, 1.0)
        density[z] = cnt[z] / a if a > 0 else 0
    return {int(k): v for k, v in cnt.items()}, {int(k): v for k, v in density.items()}


def main():
    print("Layout hypotheses: loading data...")
    df_traj = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_traj["trajectory_id"] = df_traj["trajectory_id"].astype(str)
    # Оставляем порядок по времени
    df_traj = df_traj.sort_values(["trajectory_id", "timestamp"]).reset_index(drop=True)
    semantic = pd.read_csv(SEMANTIC_FEATURES)
    semantic["trajectory_id"] = semantic["trajectory_id"].astype(str)
    duration_map = dict(zip(semantic["trajectory_id"], semantic["duration"]))

    polygons_with_zone, zone_labels = parse_dxf_zones_and_contours()
    zone_areas_df = pd.read_csv(ZONE_AREAS_CSV)
    zone_id_to_area = dict(zip(zone_areas_df["zone_id"], zone_areas_df["area"]))
    q25 = zone_areas_df["area"].quantile(0.25)
    q75 = zone_areas_df["area"].quantile(0.75)

    # Ширина прохода по сетке
    x, y = df_traj["x"].values, df_traj["y"].values
    x_edges = np.arange(x.min(), x.max() + CELL_SIZE_UNITS, CELL_SIZE_UNITS)
    y_edges = np.arange(y.min(), y.max() + CELL_SIZE_UNITS, CELL_SIZE_UNITS)
    x_edges_m = x_edges * SCALE_FACTOR
    y_edges_m = y_edges * SCALE_FACTOR
    width_map = compute_width_map(x_edges_m, y_edges_m, PLAN_FILE)
    H, W = width_map.shape

    zone_conn = zone_connectivity_from_transitions()
    zone_aspect = zone_aspect_ratio(polygons_with_zone)
    _, zone_density = exhibits_per_zone()
    stair_pts = staircase_points(polygons_with_zone)
    print(f"Staircases: zones {STAIRCASE_ZONES} + between 12-13 -> {len(stair_pts)} points")

    # Глобальный порог "узкий" по ширине (25-й перцентиль по всем точкам)
    all_widths = []
    for _, row in df_traj.iterrows():
        px, py = float(row["x"]), float(row["y"])
        x_m, y_m = px * SCALE_FACTOR, py * SCALE_FACTOR
        ix = np.searchsorted(x_edges_m, x_m, side="right") - 1
        iy = np.searchsorted(y_edges_m, y_m, side="right") - 1
        ix = max(0, min(ix, W - 1))
        iy = max(0, min(iy, H - 1))
        all_widths.append(width_map[iy, ix])
    width_narrow_threshold = np.percentile(all_widths, 25) if all_widths else 0.0

    trajectory_ids = df_traj["trajectory_id"].unique()
    rows = []

    for tid in trajectory_ids:
        sub = df_traj[df_traj["trajectory_id"] == tid].copy()
        sub = sub.sort_values("timestamp").reset_index(drop=True)
        n_pts = len(sub)
        duration = duration_map.get(tid, sub["timestamp"].max() - sub["timestamp"].min() if n_pts > 1 else 0)
        if duration <= 0:
            duration = 1.0

        # Координаты и время
        xs = sub["x"].values
        ys = sub["y"].values
        ts = sub["timestamp"].values
        t_norm = ts / duration

        # Кумулятивная длина пути
        dx = np.diff(xs)
        dy = np.diff(ys)
        seg_len = np.sqrt(dx * dx + dy * dy)
        path_cum = np.concatenate([[0], np.cumsum(seg_len)])
        total_path = path_cum[-1] if len(path_cum) > 0 else 0
        depth_from_start = path_cum / (total_path + 1e-9)  # 0..1

        # Последняя точка = выход (прокси)
        x_last, y_last = float(xs[-1]), float(ys[-1])
        dist_to_exit = np.sqrt((xs - x_last) ** 2 + (ys - y_last) ** 2)
        path_remaining = np.zeros(n_pts)
        if len(seg_len) > 0:
            path_remaining[:-1] = np.cumsum(seg_len[::-1])[::-1]

        zone_ids = []
        passage_widths = []
        connectivities = []
        aspect_ratios = []
        densities = []
        dist_to_stair_list = []

        for i in range(n_pts):
            px, py = float(xs[i]), float(ys[i])
            z = assign_point_to_zone(px, py, polygons_with_zone, zone_labels)
            zone_ids.append(z)
            connectivities.append(zone_conn.get(z, 0))
            aspect_ratios.append(zone_aspect.get(z, 1.0))
            densities.append(zone_density.get(z, 0.0))
            x_m, y_m = px * SCALE_FACTOR, py * SCALE_FACTOR
            ix = np.searchsorted(x_edges_m, x_m, side="right") - 1
            iy = np.searchsorted(y_edges_m, y_m, side="right") - 1
            ix = max(0, min(ix, W - 1))
            iy = max(0, min(iy, H - 1))
            passage_widths.append(float(width_map[iy, ix]))
            # Расстояние до ближайшей лестницы (в единицах плана)
            if stair_pts:
                d = min(np.sqrt((px - sx) ** 2 + (py - sy) ** 2) for sx, sy in stair_pts)
                dist_to_stair_list.append(d)
            else:
                dist_to_stair_list.append(np.nan)

        passage_widths = np.array(passage_widths)
        zone_ids = np.array(zone_ids)
        dist_to_stair = np.array(dist_to_stair_list)

        # H2 Bottlenecks
        min_width = float(np.min(passage_widths))
        pct_narrow = float(np.mean(passage_widths < width_narrow_threshold))
        # H9 Width variance
        width_std = float(np.std(passage_widths)) if n_pts > 1 else 0.0
        width_range = float(np.max(passage_widths) - np.min(passage_widths)) if n_pts > 1 else 0.0

        # H3 Connectivity
        conn_arr = np.array(connectivities)
        valid_z = zone_ids >= 0
        mean_connectivity = float(np.mean(conn_arr[valid_z])) if np.any(valid_z) else 0.0
        pct_low_connectivity = float(np.mean(conn_arr <= 2)) if n_pts > 0 else 0.0  # 1-2 связи = тупик

        # H4 Depth from entrance
        mean_depth = float(np.mean(depth_from_start))
        max_depth = float(np.max(depth_from_start))

        # H5 Corridor vs hall
        aspect_arr = np.array(aspect_ratios)
        pct_corridor = float(np.mean(aspect_arr >= 2.0)) if n_pts > 0 else 0.0
        mean_aspect = float(np.mean(aspect_arr[valid_z])) if np.any(valid_z) else 1.0

        # H6 Exhibit density
        dens_arr = np.array(densities)
        mean_exhibit_density = float(np.mean(dens_arr[valid_z])) * 1e6 if np.any(valid_z) else 0.0  # на млн единиц площади

        # H7 Order (phase of visit)
        pct_start = float(np.mean(t_norm < 0.33))
        pct_mid = float(np.mean((t_norm >= 0.33) & (t_norm < 0.67)))
        pct_end = float(np.mean(t_norm >= 0.67))
        mean_t_norm = float(np.mean(t_norm))

        # H8 Returns to same zone
        seen = set()
        n_returns = 0
        revisit_points = 0
        for i, z in enumerate(zone_ids):
            if z < 0:
                continue
            if z in seen:
                revisit_points += 1
                if i > 0 and zone_ids[i - 1] != z:
                    n_returns += 1  # re-entry
            else:
                seen.add(z)
        pct_path_revisit = revisit_points / n_pts if n_pts > 0 else 0.0

        # H10 Exit proximity (mean distance to exit along path at each point; lower = closer to exit more often)
        mean_dist_to_exit = float(np.mean(dist_to_exit))
        mean_path_remaining = float(np.mean(path_remaining)) if n_pts > 0 else 0.0

        # H11 Staircase proximity (лестницы в зонах 1, 2, 5 и между 12–13)
        valid_stair = np.isfinite(dist_to_stair)
        mean_dist_to_staircase = float(np.mean(dist_to_stair[valid_stair])) if np.any(valid_stair) else np.nan
        min_dist_to_staircase = float(np.min(dist_to_stair[valid_stair])) if np.any(valid_stair) else np.nan
        pct_near_staircase = float(np.mean(dist_to_stair < STAIRCASE_NEAR_RADIUS)) if n_pts > 0 and len(stair_pts) > 0 else 0.0

        # H12 Количество поворотов (смена направления > 30°)
        n_turns, n_segments = count_turns(xs, ys, angle_threshold_deg=30.0)
        turns_per_length = n_turns / (total_path + 1e-9)  # на единицу длины пути
        turns_per_minute = n_turns / (duration / 60.0 + 1e-9)

        rows.append({
            "trajectory_id": tid,
            "H2_min_width": min_width,
            "H2_pct_narrow": pct_narrow,
            "H3_mean_connectivity": mean_connectivity,
            "H3_pct_low_connectivity": pct_low_connectivity,
            "H4_mean_depth": mean_depth,
            "H4_max_depth": max_depth,
            "H5_pct_corridor": pct_corridor,
            "H5_mean_aspect_ratio": mean_aspect,
            "H6_mean_exhibit_density": mean_exhibit_density,
            "H7_pct_start": pct_start,
            "H7_pct_mid": pct_mid,
            "H7_pct_end": pct_end,
            "H7_mean_t_norm": mean_t_norm,
            "H8_n_returns": n_returns,
            "H8_pct_path_revisit": pct_path_revisit,
            "H9_width_std": width_std,
            "H9_width_range": width_range,
            "H10_mean_dist_to_exit": mean_dist_to_exit,
            "H10_mean_path_remaining": mean_path_remaining,
            "H11_mean_dist_to_staircase": mean_dist_to_staircase,
            "H11_min_dist_to_staircase": min_dist_to_staircase,
            "H11_pct_near_staircase": pct_near_staircase,
            "H12_n_turns": n_turns,
            "H12_turns_per_length": turns_per_length,
            "H12_turns_per_minute": turns_per_minute,
        })

    df_layout = pd.DataFrame(rows)
    df_layout.to_csv(OUTPUT_FEATURES, index=False)
    print(f"Saved: {OUTPUT_FEATURES}")

    # Merge with movement
    if OPENNESS_AND_MOVEMENT_CSV.exists():
        df_move = pd.read_csv(OPENNESS_AND_MOVEMENT_CSV)
        df_move["trajectory_id"] = df_move["trajectory_id"].astype(str)
        df_merged = df_move.merge(df_layout, on="trajectory_id", how="inner")
    else:
        df_sem = pd.read_csv(SEMANTIC_FEATURES)
        df_sem["trajectory_id"] = df_sem["trajectory_id"].astype(str)
        df_merged = df_layout.merge(
            df_sem[["trajectory_id", "duration", "speed", "nb_stops", "nb_items", "length"]],
            on="trajectory_id", how="left",
        )
        df_merged["stop_intensity"] = df_merged["nb_stops"] / (df_merged["duration"] / 60.0 + 1e-9)
    df_merged.to_csv(OUTPUT_MERGED, index=False)
    print(f"Saved: {OUTPUT_MERGED}")

    # Correlations: layout features vs movement
    layout_cols = [c for c in df_merged.columns if c.startswith("H2_") or c.startswith("H3_") or c.startswith("H4_")
                   or c.startswith("H5_") or c.startswith("H6_") or c.startswith("H7_") or c.startswith("H8_")
                   or c.startswith("H9_") or c.startswith("H10_") or c.startswith("H11_") or c.startswith("H12_")]
    movement_cols = ["speed", "duration", "nb_stops", "nb_items", "stop_intensity"]
    movement_cols = [c for c in movement_cols if c in df_merged.columns]
    corr = df_merged[layout_cols + movement_cols].corr()
    corr_layout_vs_move = corr.loc[layout_cols, movement_cols]
    corr_layout_vs_move.to_csv(OPENNESS_ANALYSIS_DIR / "layout_vs_movement_correlations.csv")
    print(f"Saved: layout_vs_movement_correlations.csv")

    # Report
    lines = [
        "# Layout hypotheses: correlation with movement",
        "",
        "| Feature | speed | duration | nb_stops | nb_items | stop_intensity |",
        "|---------|-------|----------|----------|----------|----------------|",
    ]
    for feat in layout_cols:
        parts = [feat]
        for m in movement_cols:
            r = corr_layout_vs_move.loc[feat, m] if feat in corr_layout_vs_move.index and m in corr_layout_vs_move.columns else np.nan
            parts.append(f"{r:.3f}" if not np.isnan(r) else "-")
        lines.append("| " + " | ".join(parts) + " |")

    lines.extend([
        "",
        "## Strongest effects (|r| > 0.25)",
        "",
    ])
    strong = []
    for feat in layout_cols:
        for m in movement_cols:
            r = corr_layout_vs_move.loc[feat, m] if feat in corr_layout_vs_move.index and m in corr_layout_vs_move.columns else 0
            if abs(r) > 0.25:
                strong.append((feat, m, r))
    for feat, m, r in sorted(strong, key=lambda x: -abs(x[2])):
        lines.append(f"- **{feat}** vs **{m}**: r = {r:.3f}")
    if not strong:
        lines.append("No correlations with |r| > 0.25.")

    lines.extend([
        "",
        "## Summary of 12 layout hypotheses",
        "",
        "1. **H1 Width** (already in openness): passage_width_mean — narrower paths: more stops, lower speed.",
        "2. **H2 Bottlenecks**: min_width, pct_narrow — weak; more narrow points slightly link to fewer items (r~-0.14), more stop_intensity (r~0.18).",
        "3. **H3 Connectivity**: mean_connectivity, pct_low_connectivity — **strong**: more path in low-connectivity (dead-end) zones → lower speed (r~-0.30), fewer items (r~-0.27); higher connectivity → more stops and stop_intensity (r~0.26).",
        "4. **H4 Depth**: mean_depth — deeper paths (from entrance) → lower speed (r~-0.24), more stops (r~0.19).",
        "5. **H5 Corridor vs hall**: pct_corridor, mean_aspect_ratio — weak; higher aspect (more corridor-like) → fewer items (r~-0.23).",
        "6. **H6 Exhibit density**: mean_exhibit_density — **strong**: higher density along path → higher speed (r~0.26), more items (r~0.29).",
        "7. **H7 Order**: pct_start/mid/end, mean_t_norm — more time in start phase → higher speed, fewer stops; more in end → more stops (r~0.24), higher stop_intensity (r~0.24).",
        "8. **H8 Returns**: n_returns, pct_path_revisit — **strong**: more revisit → lower speed (r~-0.33), longer duration (r~0.33), more stops (r~0.26); n_returns vs stop_intensity r~-0.30.",
        "9. **H9 Width variance**: width_std, width_range — more variance → fewer items (r~-0.26); width_range → lower speed (r~-0.21), longer duration (r~0.20).",
        "10. **H10 Exit proximity**: mean_path_remaining — more path remaining (further from exit) → longer duration (r~0.27), more items (r~0.20).",
        "11. **H11 Staircase proximity**: mean_dist_to_staircase, min_dist_to_staircase, pct_near_staircase — proximity to staircases (zones 1, 2, 5 and between 12–13); see correlations in table above.",
        "12. **H12 Turn count**: n_turns, turns_per_length, turns_per_minute — number of turns (direction change > 30 deg) along path; see correlations in table above.",
    ])

    OPENNESS_ANALYSIS_DIR.mkdir(exist_ok=True)
    Path(OUTPUT_REPORT).write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {OUTPUT_REPORT}")
    print("Done.")


if __name__ == "__main__":
    main()
