"""
Data loading and plotting for model_search_macro.ipynb: tracks on plan, edge-load real/sim.
Reduces inline code in the notebook.
"""
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

try:
    import ezdxf
except ImportError:
    ezdxf = None


def _parse_floor_plan(path_dxf, layer):
    if ezdxf is None:
        return []
    doc = ezdxf.readfile(str(Path(path_dxf).resolve()))
    msp = doc.modelspace()
    segs = []
    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            continue
        for i in range(len(pts) - 1):
            segs.append((float(pts[i][0]), float(pts[i][1]), float(pts[i + 1][0]), float(pts[i + 1][1])))
    for e in msp.query("LINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            s, en = e.dxf.start, e.dxf.end
            segs.append((float(s.x), float(s.y), float(en.x), float(en.y)))
        except Exception:
            continue
    return segs


def _plot_tracks_with_plan(plan_segments, trajectories, title):
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect("equal")
    for (x1, y1, x2, y2) in plan_segments:
        ax.plot([x1, x2], [y1, y2], "k-", linewidth=0.8, alpha=0.7)
    JUMP_THRESHOLD = 500
    colors = plt.cm.plasma(np.linspace(0.2, 0.9, max(len(trajectories), 1)))
    for i, points in enumerate(trajectories):
        if len(points) < 2:
            continue
        xs = np.array([p[0] for p in points])
        ys = np.array([p[1] for p in points])
        dist = np.sqrt(np.diff(xs) ** 2 + np.diff(ys) ** 2)
        breaks = np.concatenate([[0], np.where(dist > JUMP_THRESHOLD)[0] + 1, [len(points)]])
        for j in range(len(breaks) - 1):
            start, end = int(breaks[j]), int(breaks[j + 1])
            if end - start >= 2:
                ax.plot(
                    xs[start:end], ys[start:end], "-",
                    color=colors[i % len(colors)], alpha=0.6, linewidth=1.2
                )
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


def load_tracks_and_plot(path_dxf, layer_floor_plan, path_csv, path_unity_dxf, layer_tracks_unity):
    """
    Load real and simulated tracks, draw floor plan and both track plots.
    Returns (plan_segments, traj_real, traj_sim) for use in later cells.
    """
    from room_popularity import load_trajectories_from_csv, load_simulated_trajectories_from_unity_dxf

    plan_segments = _parse_floor_plan(path_dxf, layer_floor_plan)
    traj_real = load_trajectories_from_csv(path_csv, floor_number=0)
    traj_sim = load_simulated_trajectories_from_unity_dxf(
        path_dxf, path_unity_dxf,
        layer_reference_bird="Outline",
        layer_tracks_unity=layer_tracks_unity,
    )
    _plot_tracks_with_plan(plan_segments, traj_real, f"Real tracks (n={len(traj_real)})")
    _plot_tracks_with_plan(plan_segments, traj_sim, f"Simulated tracks (n={len(traj_sim)})")
    return plan_segments, traj_real, traj_sim


def load_edge_load_real(path_dxf, layer_area, path_csv):
    """
    Load zones and real trajectories, compute edge-load (transition matrix), print stats, show table and bar plot.
    Returns (polygons_with_zone, zone_labels, df_trans_real, total_real).
    """
    from room_popularity import parse_zones_from_dxf, load_trajectories_from_csv, compute_transition_matrix

    polygons_with_zone, zone_labels = parse_zones_from_dxf(path_dxf, layer_area)
    traj_real = load_trajectories_from_csv(path_csv, floor_number=0)
    df_trans_real, total_real = compute_transition_matrix(polygons_with_zone, zone_labels, traj_real)

    print("Edge-load (real), total transitions:", total_real)
    print("n_edges (unique transitions):", len(df_trans_real))
    print(
        "dependency_pct: min={:.2f}, max={:.2f}, mean={:.2f}, median={:.2f}, std={:.2f}".format(
            df_trans_real["dependency_pct"].min(), df_trans_real["dependency_pct"].max(),
            df_trans_real["dependency_pct"].mean(), df_trans_real["dependency_pct"].median(),
            df_trans_real["dependency_pct"].std(),
        )
    )
    print(
        "count: min={}, max={}, mean={:.2f}, median={:.2f}, std={:.2f}".format(
            df_trans_real["count"].min(), df_trans_real["count"].max(),
            df_trans_real["count"].mean(), df_trans_real["count"].median(),
            df_trans_real["count"].std(),
        )
    )
    try:
        from IPython.display import display
        display(df_trans_real)
    except ImportError:
        print(df_trans_real)

    df_plot = df_trans_real.sort_values("dependency_pct", ascending=True)
    df_plot = df_plot.copy()
    df_plot["edge"] = df_plot["from_zone"].astype(str) + " -> " + df_plot["to_zone"].astype(str)
    plt.figure(figsize=(8, max(8, len(df_plot) * 0.25)))
    plt.barh(df_plot["edge"], df_plot["dependency_pct"], color="steelblue", alpha=0.8)
    plt.xlabel("Edge load (%)")
    plt.title("Edge-load (real), all transitions")
    plt.tight_layout()
    plt.show()

    return polygons_with_zone, zone_labels, df_trans_real, total_real


def load_edge_load_sim(path_dxf, path_unity_dxf, layer_tracks_unity, polygons_with_zone, zone_labels):
    """
    Load simulated tracks from Unity DXF, compute edge-load, print stats, show table and bar plot.
    Returns (df_trans_sim, total_sim). If no tracks, returns (empty DataFrame, 0).
    """
    import pandas as pd
    from room_popularity import load_simulated_trajectories_from_unity_dxf, compute_transition_matrix

    traj_sim = load_simulated_trajectories_from_unity_dxf(
        path_dxf, path_unity_dxf,
        layer_reference_bird="Outline",
        layer_tracks_unity=layer_tracks_unity,
    )
    total_sim, df_trans_sim = 0, pd.DataFrame()
    if len(traj_sim) == 0:
        print("No simulated tracks (unity DXF layer TRACKS empty or file missing).")
        return df_trans_sim, total_sim

    df_trans_sim, total_sim = compute_transition_matrix(polygons_with_zone, zone_labels, traj_sim)
    print("Edge-load (simulated), total transitions:", total_sim)
    print("n_edges (unique transitions):", len(df_trans_sim))
    print(
        "dependency_pct: min={:.2f}, max={:.2f}, mean={:.2f}, median={:.2f}, std={:.2f}".format(
            df_trans_sim["dependency_pct"].min(), df_trans_sim["dependency_pct"].max(),
            df_trans_sim["dependency_pct"].mean(), df_trans_sim["dependency_pct"].median(),
            df_trans_sim["dependency_pct"].std(),
        )
    )
    print(
        "count: min={}, max={}, mean={:.2f}, median={:.2f}, std={:.2f}".format(
            df_trans_sim["count"].min(), df_trans_sim["count"].max(),
            df_trans_sim["count"].mean(), df_trans_sim["count"].median(),
            df_trans_sim["count"].std(),
        )
    )
    try:
        from IPython.display import display
        display(df_trans_sim)
    except ImportError:
        print(df_trans_sim)

    df_plot = df_trans_sim.sort_values("dependency_pct", ascending=True)
    df_plot = df_plot.copy()
    df_plot["edge"] = df_plot["from_zone"].astype(str) + " -> " + df_plot["to_zone"].astype(str)
    plt.figure(figsize=(8, max(8, len(df_plot) * 0.25)))
    plt.barh(df_plot["edge"], df_plot["dependency_pct"], color="coral", alpha=0.8)
    plt.xlabel("Edge load (%)")
    plt.title("Edge-load (simulated), all transitions")
    plt.tight_layout()
    plt.show()

    return df_trans_sim, total_sim
