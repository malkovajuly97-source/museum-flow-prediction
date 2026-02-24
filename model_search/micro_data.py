"""
Data loading and plotting for model_search_micro.ipynb.
Reduces notebook code by moving intro, density heatmaps, and ToP heatmaps here.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from scipy.ndimage import gaussian_filter

from density import (
    SCALE_FACTOR,
    compute_density_analysis,
    compute_time_of_presence,
    load_floor0_trajectories,
)
from plot_density_grids import (
    load_floor_plan_segments,
    plot_plan_with_grid,
    plot_plan_with_grid_and_tracks,
    plot_heatmap_on_plan,
)

MAX_JUMP_M = 5.0
MAX_GAP_SEC = 300.0
LONG_STOP_THRESHOLD_SEC = 30.0


def _split_trajectory_by_gaps(df, scale_factor, max_jump_m, max_gap_sec):
    """Split trajectory into segments when dist > max_jump_m (m) or time_diff > max_gap_sec (s)."""
    x_m = df["x"].astype(float).values * scale_factor
    y_m = df["y"].astype(float).values * scale_factor
    ts = df["timestamp"].astype(float).values
    if len(x_m) < 2:
        return [[(float(x_m[0]), float(y_m[0]))]] if len(x_m) == 1 else []
    dist = np.sqrt(np.diff(x_m) ** 2 + np.diff(y_m) ** 2)
    time_diff = np.diff(ts)
    breaks = np.where((dist > max_jump_m) | (time_diff > max_gap_sec))[0] + 1
    breaks = np.concatenate([[0], breaks, [len(x_m)]])
    segments = []
    for j in range(len(breaks) - 1):
        start, end = int(breaks[j]), int(breaks[j + 1])
        if end - start >= 2:
            segments.append([(float(x_m[k]), float(y_m[k])) for k in range(start, end)])
    return segments


def load_micro_data(
    path_trajectories,
    path_simulation_csv,
    path_dxf,
    path_unity_dxf,
    cell_size_m=1.0,
):
    """
    Load real and simulated density data, floor segments, and track lists for intro plot.
    Returns: d_real, d_sim (or None), xe, ye, segments, traj_real_m, traj_sim_m (or None).
    """
    path_dxf = Path(path_dxf) if isinstance(path_dxf, str) else Path(path_dxf)
    path_unity_dxf = Path(path_unity_dxf) if isinstance(path_unity_dxf, str) else Path(path_unity_dxf)

    segments = load_floor_plan_segments(path_dxf, "Floor_plan")
    d_real = compute_density_analysis(path_trajectories, cell_size_m=cell_size_m)
    xe, ye = d_real["x_edges"], d_real["y_edges"]

    base = Path("model_search") if (Path.cwd() / "model_search").exists() else Path(".")
    grid_json = base / "density_floor0.json"
    if not grid_json.exists():
        json.dump(
            {"x_edges_m": [round(float(x), 4) for x in xe], "y_edges_m": [round(float(y), 4) for y in ye]},
            open(grid_json, "w", encoding="utf-8"),
            indent=2,
        )

    traj_bird, _, _, _ = load_floor0_trajectories(path_trajectories)
    traj_real_m = []
    for df in traj_bird:
        traj_real_m.extend(_split_trajectory_by_gaps(df, SCALE_FACTOR, MAX_JUMP_M, MAX_GAP_SEC))

    traj_sim_m = None
    if path_unity_dxf.exists():
        try:
            from room_popularity import load_simulated_trajectories_from_unity_dxf
            traj_sim_raw = load_simulated_trajectories_from_unity_dxf(
                path_dxf, path_unity_dxf, layer_reference_bird="Outline", layer_tracks_unity="TRACKS"
            )
            traj_sim_m = [[(x * SCALE_FACTOR, y * SCALE_FACTOR) for (x, y) in tr] for tr in traj_sim_raw]
        except Exception as e:
            print(f"[Simulation] Failed to load tracks from unity DXF: {e}")

    d_sim = None
    if path_simulation_csv and path_unity_dxf.exists():
        try:
            from room_popularity import load_simulated_trajectories_from_csv_in_meters
            traj_sim_csv = load_simulated_trajectories_from_csv_in_meters(
                path_dxf, path_unity_dxf, path_simulation_csv, SCALE_FACTOR
            )
            nx, ny = len(xe) - 1, len(ye) - 1
            all_x = np.concatenate([df["x"].values for df in traj_sim_csv])
            all_y = np.concatenate([df["y"].values for df in traj_sim_csv])
            hm, _, _ = np.histogram2d(all_x, all_y, bins=[xe, ye])
            hm = hm.T
            top_matrix, stop_durations = compute_time_of_presence(
                traj_sim_csv, xe, ye, nx, ny, scale_factor=1.0
            )
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
            d_sim = {
                "heatmap": hm,
                "top_matrix": top_matrix,
                "x_edges": xe,
                "y_edges": ye,
                "n_trajectories": len(traj_sim_csv),
                "stop_duration_stats": stop_duration_stats,
            }
        except Exception as e:
            print(f"[Simulation CSV] Failed to load: {e}")

    if d_sim is None and traj_sim_m and len(traj_sim_m) > 0:
        all_x = np.concatenate([[p[0] for p in tr] for tr in traj_sim_m])
        all_y = np.concatenate([[p[1] for p in tr] for tr in traj_sim_m])
        hm, _, _ = np.histogram2d(all_x, all_y, bins=[xe, ye])
        hm = hm.T
        d_sim = {
            "heatmap": hm,
            "top_matrix": np.zeros_like(hm),
            "x_edges": xe,
            "y_edges": ye,
            "n_trajectories": len(traj_sim_m),
        }

    return d_real, d_sim, xe, ye, segments, traj_real_m, traj_sim_m


def plot_intro_tracks(segments, xe, ye, traj_real_m, traj_sim_m=None):
    """Plot floor plan + grid with real and (optional) simulated tracks."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    plot_plan_with_grid_and_tracks(
        axes[0], segments, xe, ye, traj_real_m,
        f"Real tracks (n={len(traj_real_m)})",
        track_color="tab:blue",
    )
    if traj_sim_m is not None:
        plot_plan_with_grid_and_tracks(
            axes[1], segments, xe, ye, traj_sim_m,
            f"Simulated tracks (n={len(traj_sim_m)})",
            track_color="tab:orange",
        )
    else:
        plot_plan_with_grid(xe, ye, segments, "Simulated tracks — no data", axes[1])
    plt.tight_layout()
    plt.show()


def _density_cmap():
    colors = [
        (0, (33/255, 102/255, 172/255)), (0.14, (67/255, 147/255, 195/255)),
        (0.29, (146/255, 197/255, 222/255)), (0.43, (209/255, 229/255, 240/255)),
        (0.57, (253/255, 219/255, 199/255)), (0.71, (244/255, 165/255, 130/255)),
        (0.86, (214/255, 96/255, 77/255)), (1, (178/255, 24/255, 43/255)),
    ]
    return mcolors.LinearSegmentedColormap.from_list("density_cool_warm", colors, N=256)


def plot_density_heatmaps(d_real, d_sim, segments, xe, ye, sigma_d=1.2):
    """Plot density heatmaps (real and sim), return hm_real_smooth, hm_sim_smooth for later comparison."""
    hm_real = d_real["heatmap"]
    hm_sim = d_sim["heatmap"] if d_sim is not None else None
    vals_d = np.concatenate([
        hm_real[hm_real > 0].ravel(),
        hm_sim[hm_sim > 0].ravel() if hm_sim is not None else [],
    ])
    vmax_d = float(np.percentile(vals_d, 95)) if len(vals_d) > 0 else max(
        hm_real.max(), hm_sim.max() if hm_sim is not None else 0
    )
    vmin_d, vmax_d = 0, vmax_d

    hm_real_smooth = gaussian_filter(hm_real.astype(float), sigma=sigma_d, mode="constant", cval=0)
    hm_sim_smooth = (
        gaussian_filter(hm_sim.astype(float), sigma=sigma_d, mode="constant", cval=0)
        if hm_sim is not None else None
    )
    cmap = _density_cmap()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    plot_heatmap_on_plan(
        axes[0], hm_real_smooth, xe, ye, segments,
        f"Density real (n={d_real['n_trajectories']})",
        label="points", vmin=vmin_d, vmax=vmax_d, cmap=cmap,
        draw_grid=False, interpolation="bilinear",
    )
    if d_sim is not None:
        plot_heatmap_on_plan(
            axes[1], hm_sim_smooth, xe, ye, segments,
            f"Density simulated (n={d_sim['n_trajectories']})",
            label="points", vmin=vmin_d, vmax=vmax_d, cmap=cmap,
            draw_grid=False, interpolation="bilinear",
        )
    else:
        axes[1].set_title("Density simulated — no data")
    plt.tight_layout()
    plt.show()
    return hm_real_smooth, hm_sim_smooth


def plot_top_heatmaps(d_real, d_sim, segments, xe, ye, sigma=1.2):
    """Plot ToP heatmaps (real and sim), return top_real_smooth, top_sim_smooth for later comparison."""
    top_real = d_real["top_matrix"]
    top_sim = d_sim["top_matrix"] if d_sim is not None else None
    top_real_smooth = gaussian_filter(top_real.astype(float), sigma=sigma, mode="constant", cval=0)
    top_sim_smooth = (
        gaussian_filter(top_sim.astype(float), sigma=sigma, mode="constant", cval=0)
        if top_sim is not None else None
    )
    vals_t = np.concatenate([
        top_real[top_real > 0].ravel(),
        top_sim[top_sim > 0].ravel() if top_sim is not None else [],
    ])
    vmax_t = float(np.percentile(vals_t, 95)) if len(vals_t) > 0 else max(
        top_real.max(), top_sim.max() if top_sim is not None else 0
    )
    vmin_t, vmax_t = 0, vmax_t

    colors_top = [
        (0, (33/255, 102/255, 172/255)), (0.14, (67/255, 147/255, 195/255)),
        (0.29, (146/255, 197/255, 222/255)), (0.43, (209/255, 229/255, 240/255)),
        (0.57, (253/255, 219/255, 199/255)), (0.71, (244/255, 165/255, 130/255)),
        (0.86, (214/255, 96/255, 77/255)), (1, (178/255, 24/255, 43/255)),
    ]
    top_cmap = mcolors.LinearSegmentedColormap.from_list("top_cool_warm", colors_top, N=256)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    plot_heatmap_on_plan(
        axes[0], top_real_smooth, xe, ye, segments,
        f"ToP real (n={d_real['n_trajectories']})",
        label="sec", vmin=vmin_t, vmax=vmax_t, cmap=top_cmap,
        draw_grid=False, interpolation="bilinear",
    )
    if d_sim is not None:
        plot_heatmap_on_plan(
            axes[1], top_sim_smooth, xe, ye, segments,
            f"ToP simulated (n={d_sim['n_trajectories']})",
            label="sec", vmin=vmin_t, vmax=vmax_t, cmap=top_cmap,
            draw_grid=False, interpolation="bilinear",
        )
    else:
        axes[1].set_title("ToP simulated — no data")
    plt.tight_layout()
    plt.show()
    return top_real_smooth, top_sim_smooth
