"""
Визуализация планов BIRD и Unity с наложенной сеткой 1×1 м.

Рисует план этажа (контур из Floor_0.dxf) и сетку — без окраски плотности.
Сохраняет density_grids_BIRD.png, density_grids_Unity.png, density_grids_combined.png.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:
    import ezdxf
except ImportError:
    ezdxf = None

BASE = Path(__file__).resolve().parent
PATH_DXF = BASE / "Floor_0.dxf"
LAYER_FLOOR_PLAN = "Floor_plan"
SCALE_FACTOR = 55.07 / 5401  # BIRD raw → метры
DENSITY_BIRD = BASE / "density_floor0.json"
DENSITY_UNITY = BASE / "density_simulation.json"
OUTPUT_BIRD = BASE / "density_grids_BIRD.png"
OUTPUT_UNITY = BASE / "density_grids_Unity.png"
OUTPUT_COMBINED = BASE / "density_grids_combined.png"


def load_floor_plan_segments(path_dxf, layer):
    """Извлекает линии плана этажа из DXF. Координаты в метрах (× SCALE_FACTOR)."""
    if ezdxf is None or not path_dxf.exists():
        return []
    doc = ezdxf.readfile(str(path_dxf))
    msp = doc.modelspace()
    segments = []
    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            continue
        for i in range(len(pts) - 1):
            x1, y1 = float(pts[i][0]) * SCALE_FACTOR, float(pts[i][1]) * SCALE_FACTOR
            x2, y2 = float(pts[i + 1][0]) * SCALE_FACTOR, float(pts[i + 1][1]) * SCALE_FACTOR
            segments.append((x1, y1, x2, y2))
    for e in msp.query("LINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            s, en = e.dxf.start, e.dxf.end
            x1, y1 = float(s.x) * SCALE_FACTOR, float(s.y) * SCALE_FACTOR
            x2, y2 = float(en.x) * SCALE_FACTOR, float(en.y) * SCALE_FACTOR
            segments.append((x1, y1, x2, y2))
        except Exception:
            continue
    return segments


def plot_heatmap_on_plan(ax, heatmap, x_edges, y_edges, segments, title, cmap="viridis", label="", vmin=None, vmax=None, draw_grid=True, interpolation="nearest"):
    """Рисует heatmap поверх плана этажа. vmin/vmax — единая шкала. interpolation: 'nearest' (чёткие ячейки) или 'bilinear' (сглаживание)."""
    ax.set_facecolor("white")
    for x1, y1, x2, y2 in segments:
        ax.plot([x1, x2], [y1, y2], "k-", linewidth=1.2)
    extent = [x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]]
    im = ax.imshow(heatmap, extent=extent, origin="lower", aspect="auto", cmap=cmap, interpolation=interpolation, vmin=vmin, vmax=vmax)
    if draw_grid:
        for x in x_edges:
            ax.axvline(x, color="white", linewidth=0.5, alpha=0.9)
        for y in y_edges:
            ax.axhline(y, color="white", linewidth=0.5, alpha=0.9)
    if label:
        plt.colorbar(im, ax=ax, label=label)
    ax.set_xlim(x_edges[0], x_edges[-1])
    ax.set_ylim(y_edges[0], y_edges[-1])
    ax.set_xlabel("x (м)")
    ax.set_ylabel("y (м)")
    ax.set_title(title)
    ax.set_aspect("equal")


def plot_plan_with_grid(x_edges, y_edges, segments, title, ax):
    """Рисует план этажа (чёрные линии) и сетку (серые линии)."""
    ax.set_facecolor("white")

    # План этажа
    for x1, y1, x2, y2 in segments:
        ax.plot([x1, x2], [y1, y2], "k-", linewidth=1.2)

    # Сетка 1×1 м
    for x in x_edges:
        ax.axvline(x, color="gray", linewidth=0.4, alpha=0.7, linestyle="-")
    for y in y_edges:
        ax.axhline(y, color="gray", linewidth=0.4, alpha=0.7, linestyle="-")

    ax.set_xlim(x_edges[0], x_edges[-1])
    ax.set_ylim(y_edges[0], y_edges[-1])
    ax.set_xlabel("x (м)")
    ax.set_ylabel("y (м)")
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.grid(False)


def plot_plan_with_grid_and_tracks(
    ax, segments, x_edges, y_edges, trajectories_list, title,
    track_color="tab:blue", track_alpha=0.4, extra_segments=None, extra_segments_color="red",
):
    """
    Рисует план этажа, сетку и треки.
    trajectories_list: list of [(x_m, y_m), ...] — каждая траектория в метрах.
    extra_segments: list of (x1,y1,x2,y2) — доп. план (напр. из unity_tracks.dxf), рисуется extra_segments_color.
    """
    ax.set_facecolor("white")

    # План этажа
    for x1, y1, x2, y2 in segments:
        ax.plot([x1, x2], [y1, y2], "k-", linewidth=1.2)

    # Доп. план (напр. Unity)
    if extra_segments:
        for x1, y1, x2, y2 in extra_segments:
            ax.plot([x1, x2], [y1, y2], "-", color=extra_segments_color, linewidth=1.5, alpha=0.9, zorder=10)

    # Сетка 1×1 м
    for x in x_edges:
        ax.axvline(x, color="gray", linewidth=0.4, alpha=0.7, linestyle="-")
    for y in y_edges:
        ax.axhline(y, color="gray", linewidth=0.4, alpha=0.7, linestyle="-")

    # Треки
    for traj in trajectories_list:
        if len(traj) < 2:
            continue
        xs = [p[0] for p in traj]
        ys = [p[1] for p in traj]
        ax.plot(xs, ys, "-", color=track_color, alpha=track_alpha, linewidth=0.8)

    ax.set_xlim(x_edges[0], x_edges[-1])
    ax.set_ylim(y_edges[0], y_edges[-1])
    ax.set_xlabel("x (м)")
    ax.set_ylabel("y (м)")
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.grid(False)


def main():
    segments = load_floor_plan_segments(PATH_DXF, LAYER_FLOOR_PLAN)
    if not segments:
        print(f"План не найден в {PATH_DXF} (слой {LAYER_FLOOR_PLAN})")

    if not DENSITY_BIRD.exists():
        print(f"Сначала запустите density.py. Файл не найден: {DENSITY_BIRD}")
        return
    if not DENSITY_UNITY.exists():
        print(f"Сначала запустите density_Unity.py. Файл не найден: {DENSITY_UNITY}")
        return

    with open(DENSITY_BIRD, encoding="utf-8") as f:
        data_bird = json.load(f)
    with open(DENSITY_UNITY, encoding="utf-8") as f:
        data_unity = json.load(f)

    x_edges = np.array(data_bird["x_edges_m"])
    y_edges = np.array(data_bird["y_edges_m"])

    # BIRD
    fig1, ax1 = plt.subplots(figsize=(10, 8))
    plot_plan_with_grid(
        x_edges, y_edges, segments,
        f"BIRD: план этажа (n={data_bird['n_trajectories']} траекторий)",
        ax1,
    )
    plt.tight_layout()
    plt.savefig(OUTPUT_BIRD, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Сохранено: {OUTPUT_BIRD}")

    # Unity
    fig2, ax2 = plt.subplots(figsize=(10, 8))
    plot_plan_with_grid(
        x_edges, y_edges, segments,
        f"Unity: план этажа (n={data_unity['n_trajectories']} траекторий)",
        ax2,
    )
    plt.tight_layout()
    plt.savefig(OUTPUT_UNITY, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Сохранено: {OUTPUT_UNITY}")

    # Combined
    fig3, (ax3, ax4) = plt.subplots(1, 2, figsize=(16, 8))
    plot_plan_with_grid(
        x_edges, y_edges, segments,
        f"BIRD (n={data_bird['n_trajectories']})",
        ax3,
    )
    plot_plan_with_grid(
        x_edges, y_edges, segments,
        f"Unity (n={data_unity['n_trajectories']})",
        ax4,
    )
    plt.suptitle("План этажа с общей сеткой 1×1 м (сопоставимые ячейки)", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUTPUT_COMBINED, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Сохранено: {OUTPUT_COMBINED}")


if __name__ == "__main__":
    main()
