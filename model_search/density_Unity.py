"""
Density (presence intensity), Time of Presence (ToP) и Stop duration distribution по траекториям Unity (симуляция).

Использует общую сетку BIRD (density_floor0.json) для поячеечного сравнения.
Преобразует Unity координаты в метры BIRD: x_m = x_unity + offset_x, y_m = y_unity + offset_y.
Offset вычисляется по центрам bounding box траекторий (или задаётся вручную через --offset-x, --offset-y).

Сохраняет density_simulation.csv, density_simulation.json в model_search/.
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import ezdxf
except ImportError:
    ezdxf = None

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
NANCY_STREAMING = Path(r"C:\Users\malko\Nancy_floor0\Assets\StreamingAssets")
DEFAULT_TRAJECTORIES_FOLDER = NANCY_STREAMING / "unity_tracks_bird"
DEFAULT_UNITY_PLAN_DXF = NANCY_STREAMING / "unity_tracks.dxf"
DEFAULT_GRID_FILE = BASE / "density_floor0.json"
OUTPUT_CSV = BASE / "density_simulation.csv"
OUTPUT_JSON = BASE / "density_simulation.json"

CELL_SIZE = 1.0  # размер ячейки (м), как в BIRD
LONG_STOP_THRESHOLD_SEC = 30.0  # порог для "длинной" остановки (proportion of long stops)


def load_common_grid(grid_path=None):
    """Загружает x_edges, y_edges из BIRD density_floor0.json."""
    path = Path(grid_path) if grid_path else Path(DEFAULT_GRID_FILE)
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл сетки не найден: {path}\nСначала запустите density.py")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    x_edges = np.array(data.get("x_edges_m", []))
    y_edges = np.array(data.get("y_edges_m", []))
    if len(x_edges) < 2 or len(y_edges) < 2:
        raise ValueError(f"Неверный формат сетки в {path}")
    return x_edges, y_edges


def compute_unity_to_bird_offset(x_edges, y_edges, unity_x, unity_y):
    """offset = BIRD_center - Unity_center для выравнивания по центрам bounding box (без scale)."""
    bird_center_x = (x_edges[0] + x_edges[-1]) / 2
    bird_center_y = (y_edges[0] + y_edges[-1]) / 2
    unity_center_x = float(np.mean(unity_x))
    unity_center_y = float(np.mean(unity_y))
    return bird_center_x - unity_center_x, bird_center_y - unity_center_y


def compute_unity_to_bird_transform(x_edges, y_edges, unity_x, unity_y):
    """
    Возвращает (scale_x, scale_y, offset_x, offset_y) для преобразования Unity → BIRD метры.
    Масштабирование по bounding box: Unity bbox растягивается/сжимается в BIRD grid bbox,
    сохраняя выравнивание центров. Треки Unity и план DXF (BIRD) используют разные масштабы.
    """
    bird_x_min, bird_x_max = float(x_edges[0]), float(x_edges[-1])
    bird_y_min, bird_y_max = float(y_edges[0]), float(y_edges[-1])
    bird_center_x = (bird_x_min + bird_x_max) / 2
    bird_center_y = (bird_y_min + bird_y_max) / 2

    unity_x_min, unity_x_max = float(np.min(unity_x)), float(np.max(unity_x))
    unity_y_min, unity_y_max = float(np.min(unity_y)), float(np.max(unity_y))
    unity_center_x = (unity_x_min + unity_x_max) / 2
    unity_center_y = (unity_y_min + unity_y_max) / 2

    span_unity_x = unity_x_max - unity_x_min
    span_unity_y = unity_y_max - unity_y_min
    span_bird_x = bird_x_max - bird_x_min
    span_bird_y = bird_y_max - bird_y_min

    # Защита от div by zero
    scale_x = span_bird_x / span_unity_x if span_unity_x > 1e-6 else 1.0
    scale_y = span_bird_y / span_unity_y if span_unity_y > 1e-6 else 1.0

    # x_m = (x_u - u_cx) * scale_x + b_cx  =>  offset = b_cx - u_cx * scale_x
    offset_x = bird_center_x - unity_center_x * scale_x
    offset_y = bird_center_y - unity_center_y * scale_y

    return scale_x, scale_y, offset_x, offset_y


def load_plan_floor_bbox_from_dxf(path_dxf, layer=None, dxf_scale=1000.0):
    """
    Извлекает bounding box из слоя плана пола в unity_tracks.dxf.
    DXF: export_unity_tracks_to_dxf (PLAN_FLOOR) или export_unity_plan_to_dxf (FLOOR).
    dxf_scale: DXF единицы / Unity метры. 1000 = DXF в мм. 1 = DXF уже в метрах.
    Возвращает (unity_x_min, unity_x_max, unity_y_min, unity_y_max) в Unity метрах.
    """
    if layer is None:
        layer = "PLAN_FLOOR"  # export_unity_tracks_to_dxf
    if ezdxf is None:
        raise ImportError("Установите ezdxf: pip install ezdxf")
    path = Path(path_dxf).resolve()
    if not path.exists():
        raise FileNotFoundError(f"DXF не найден: {path}")
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    xs, ys = [], []
    for e in msp.query("LWPOLYLINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            pts = list(e.get_points("xy"))
        except Exception:
            continue
        for i in range(len(pts)):
            xs.append(float(pts[i][0]) / dxf_scale)
            ys.append(float(pts[i][1]) / dxf_scale)
    for e in msp.query("LINE"):
        if getattr(e.dxf, "layer", "") != layer:
            continue
        try:
            s, en = e.dxf.start, e.dxf.end
            xs.append(float(s.x) / dxf_scale)
            xs.append(float(en.x) / dxf_scale)
            ys.append(float(s.y) / dxf_scale)
            ys.append(float(en.y) / dxf_scale)
        except Exception:
            continue
    if not xs or not ys:
        if layer == "PLAN_FLOOR":
            return load_plan_floor_bbox_from_dxf(path_dxf, layer="FLOOR", dxf_scale=dxf_scale)
        raise ValueError(f"Слой {layer} пуст или не найден в {path}")
    x_min, x_max = float(np.min(xs)), float(np.max(xs))
    y_min, y_max = float(np.min(ys)), float(np.max(ys))
    span = max(x_max - x_min, y_max - y_min)
    if span < 1.0 and dxf_scale == 1000.0:
        return load_plan_floor_bbox_from_dxf(path_dxf, layer=layer, dxf_scale=1.0)
    return x_min, x_max, y_min, y_max


def compute_unity_to_bird_transform_from_floor_plan(
    x_edges, y_edges, unity_plan_dxf_path, layer="PLAN_FLOOR", dxf_scale=1000.0
):
    """
    Возвращает (scale_x, scale_y, offset_x, offset_y) для Unity -> BIRD метры.
    Референс Unity: bbox из PLAN_FLOOR в unity_tracks.dxf (не по трекам).
    Референс BIRD: x_edges, y_edges из density_floor0.json.
    """
    unity_x_min, unity_x_max, unity_y_min, unity_y_max = load_plan_floor_bbox_from_dxf(
        unity_plan_dxf_path, layer, dxf_scale
    )
    bird_x_min, bird_x_max = float(x_edges[0]), float(x_edges[-1])
    bird_y_min, bird_y_max = float(y_edges[0]), float(y_edges[-1])
    bird_center_x = (bird_x_min + bird_x_max) / 2
    bird_center_y = (bird_y_min + bird_y_max) / 2
    unity_center_x = (unity_x_min + unity_x_max) / 2
    unity_center_y = (unity_y_min + unity_y_max) / 2
    span_unity_x = unity_x_max - unity_x_min
    span_unity_y = unity_y_max - unity_y_min
    span_bird_x = bird_x_max - bird_x_min
    span_bird_y = bird_y_max - bird_y_min
    scale_x = span_bird_x / span_unity_x if span_unity_x > 1e-6 else 1.0
    scale_y = span_bird_y / span_unity_y if span_unity_y > 1e-6 else 1.0
    offset_x = bird_center_x - unity_center_x * scale_x
    offset_y = bird_center_y - unity_center_y * scale_y
    return scale_x, scale_y, offset_x, offset_y


def load_unity_floor_plan_segments_in_bird_coords(
    path_dxf, scale_x, scale_y, offset_x, offset_y, layers=None, dxf_scale=1000.0
):
    """
    Загружает план пола и стен из unity_tracks.dxf и преобразует в BIRD метры.
    layers: список слоёв (PLAN_FLOOR, PLAN_WALLS или FLOOR, WALLS). По умолчанию оба.
    Возвращает list of (x1, y1, x2, y2) для отрисовки.
    """
    if layers is None:
        layers = ["PLAN_FLOOR", "PLAN_WALLS", "FLOOR", "WALLS"]
    if ezdxf is None:
        return []
    path = Path(path_dxf).resolve()
    if not path.exists():
        return []
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    segments_raw = []
    for layer in layers:
        for e in msp.query("LWPOLYLINE"):
            if getattr(e.dxf, "layer", "") != layer:
                continue
            try:
                pts = list(e.get_points("xy"))
            except Exception:
                continue
            for i in range(len(pts) - 1):
                x1, y1 = float(pts[i][0]) / dxf_scale, float(pts[i][1]) / dxf_scale
                x2, y2 = float(pts[i + 1][0]) / dxf_scale, float(pts[i + 1][1]) / dxf_scale
                segments_raw.append((x1, y1, x2, y2))
        for e in msp.query("LINE"):
            if getattr(e.dxf, "layer", "") != layer:
                continue
            try:
                s, en = e.dxf.start, e.dxf.end
                x1, y1 = float(s.x) / dxf_scale, float(s.y) / dxf_scale
                x2, y2 = float(en.x) / dxf_scale, float(en.y) / dxf_scale
                segments_raw.append((x1, y1, x2, y2))
            except Exception:
                continue
    if not segments_raw:
        return []
    all_x = [s[0] for s in segments_raw] + [s[2] for s in segments_raw]
    all_y = [s[1] for s in segments_raw] + [s[3] for s in segments_raw]
    span = max(np.max(all_x) - np.min(all_x), np.max(all_y) - np.min(all_y))
    if span < 1.0 and dxf_scale == 1000.0:
        return load_unity_floor_plan_segments_in_bird_coords(
            path_dxf, scale_x, scale_y, offset_x, offset_y, layers=layers, dxf_scale=1.0
        )
    segments_bird = []
    for x1, y1, x2, y2 in segments_raw:
        x1m, y1m = _unity_to_bird(np.array([x1]), np.array([y1]), scale_x, scale_y, offset_x, offset_y)
        x2m, y2m = _unity_to_bird(np.array([x2]), np.array([y2]), scale_x, scale_y, offset_x, offset_y)
        segments_bird.append((float(x1m[0]), float(y1m[0]), float(x2m[0]), float(y2m[0])))
    return segments_bird


def load_trajectories(folder_path: Path, floor_number: int = 0):
    """Загружает все треки из CSV. Возвращает (list of DataFrame, all_x, all_y, n_traj)."""
    path = Path(folder_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Папка не найдена: {path}")
    csv_files = glob.glob(str(path / "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Нет CSV в {path}")
    trajectories = []
    all_x, all_y = [], []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            if "floorNumber" in df.columns:
                df_floor = df[df["floorNumber"] == floor_number].copy()
            else:
                df_floor = df.copy()
            if len(df_floor) > 0:
                if "timestamp" in df_floor.columns:
                    df_floor = df_floor.sort_values("timestamp").reset_index(drop=True)
                trajectories.append(df_floor)
                all_x.extend(df_floor["x"].astype(float).tolist())
                all_y.extend(df_floor["y"].astype(float).tolist())
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file}: {e}")
    if not trajectories:
        raise ValueError(f"Не найдено траекторий в {path}")
    return trajectories, np.array(all_x), np.array(all_y), len(trajectories)


def get_cell_indices(x_vals, y_vals, x_edges, y_edges):
    """Возвращает (ix, iy) для каждой точки. Bin i: edges[i] <= x < edges[i+1]."""
    ix = np.searchsorted(x_edges, x_vals, side="right") - 1
    iy = np.searchsorted(y_edges, y_vals, side="right") - 1
    nx, ny = len(x_edges) - 1, len(y_edges) - 1
    ix = np.clip(ix, 0, nx - 1)
    iy = np.clip(iy, 0, ny - 1)
    return ix, iy


def _unity_to_bird(x_vals, y_vals, scale_x, scale_y, offset_x, offset_y):
    """Преобразует Unity координаты в BIRD метры: x_m = x_u * scale_x + offset_x."""
    return x_vals * scale_x + offset_x, y_vals * scale_y + offset_y


def compute_time_of_presence(trajectories, x_edges, y_edges, nx, ny, scale_x=1.0, scale_y=1.0, offset_x=0.0, offset_y=0.0):
    """
    ToP(cell) = Σ (T_exit - T_entry) по всем пребываниям.
    Unity координаты преобразуются в BIRD: x_m = x_unity * scale_x + offset_x.
    Возвращает (top_matrix, stop_durations).
    """
    top_matrix = np.zeros((ny, nx))
    stop_durations = []
    for df in trajectories:
        xu = df["x"].astype(float).values
        yu = df["y"].astype(float).values
        x_vals, y_vals = _unity_to_bird(xu, yu, scale_x, scale_y, offset_x, offset_y)
        ts = df["timestamp"].astype(float).values
        ix, iy = get_cell_indices(x_vals, y_vals, x_edges, y_edges)
        i = 0
        while i < len(ix):
            cx, cy = ix[i], iy[i]
            j = i + 1
            while j < len(ix) and ix[j] == cx and iy[j] == cy:
                j += 1
            if j > i + 1:
                top_run = ts[j - 1] - ts[i]
                if top_run > 0:
                    top_matrix[cy, cx] += top_run
                    stop_durations.append(top_run)
            i = j
    return top_matrix, stop_durations


def compute_density_analysis(
    trajectories_folder,
    grid_json_path=None,
    cell_size=1.0,
    long_stop_threshold_sec=30.0,
    offset_x=None,
    offset_y=None,
    scale_x=None,
    scale_y=None,
    unity_plan_dxf_path=None,
):
    """
    Вычисляет density, ToP и Stop duration по трекам Unity на сетке BIRD.
    Возвращает dict с heatmap, top_matrix, x_edges, y_edges, stop_duration_stats, n_traj.
    Если unity_plan_dxf_path задан — референс берется из PLAN_FLOOR (plan и треки выровнены).
    Иначе — по bbox треков (устаревший вариант).
    """
    path = Path(trajectories_folder).resolve()
    trajectories, all_x, all_y, n_traj = load_trajectories(path, 0)
    x_edges, y_edges = load_common_grid(grid_json_path)
    nx, ny = len(x_edges) - 1, len(y_edges) - 1

    if scale_x is None or scale_y is None or offset_x is None or offset_y is None:
        plan_dxf = Path(unity_plan_dxf_path).resolve() if unity_plan_dxf_path else None
        if plan_dxf and plan_dxf.exists():
            sx, sy, ox, oy = compute_unity_to_bird_transform_from_floor_plan(
                x_edges, y_edges, str(plan_dxf)
            )
        else:
            sx, sy, ox, oy = compute_unity_to_bird_transform(x_edges, y_edges, all_x, all_y)
        scale_x = scale_x if scale_x is not None else sx
        scale_y = scale_y if scale_y is not None else sy
        offset_x = offset_x if offset_x is not None else ox
        offset_y = offset_y if offset_y is not None else oy

    x_m, y_m = _unity_to_bird(np.array(all_x), np.array(all_y), scale_x, scale_y, offset_x, offset_y)
    heatmap, x_edges, y_edges = np.histogram2d(x_m, y_m, bins=[x_edges, y_edges])
    heatmap = heatmap.T
    ny, nx = heatmap.shape
    top_matrix, stop_durations = compute_time_of_presence(
        trajectories, x_edges, y_edges, nx, ny, scale_x, scale_y, offset_x, offset_y
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
            "long_stop_threshold_sec": long_stop_threshold_sec,
            "proportion_long_stops": round(float(np.mean(arr >= long_stop_threshold_sec)), 4),
        }
    return {
        "heatmap": heatmap,
        "top_matrix": top_matrix,
        "x_edges": x_edges,
        "y_edges": y_edges,
        "stop_duration_stats": stop_duration_stats,
        "n_trajectories": n_traj,
        "n_points": len(all_x),
        "scale_x": scale_x,
        "scale_y": scale_y,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }


def main():
    parser = argparse.ArgumentParser(description="Density, ToP, Stop duration для треков Unity (сетка BIRD)")
    parser.add_argument(
        "--trajectories-folder",
        "-f",
        type=str,
        default=str(DEFAULT_TRAJECTORIES_FOLDER),
        help=f"Папка с CSV траекториями (по умолчанию: {DEFAULT_TRAJECTORIES_FOLDER})",
    )
    parser.add_argument(
        "--grid-from",
        type=str,
        default=str(DEFAULT_GRID_FILE),
        help=f"JSON с сеткой BIRD (x_edges_m, y_edges_m) (по умолчанию: {DEFAULT_GRID_FILE})",
    )
    parser.add_argument("--offset-x", type=float, default=None, help="Ручное смещение Unity->BIRD по X (м)")
    parser.add_argument("--offset-y", type=float, default=None, help="Ручное смещение Unity->BIRD по Y (м)")
    parser.add_argument("--scale-x", type=float, default=None, help="Ручной масштаб Unity->BIRD по X")
    parser.add_argument("--scale-y", type=float, default=None, help="Ручной масштаб Unity->BIRD по Y")
    parser.add_argument(
        "--unity-plan-dxf",
        type=str,
        default=str(DEFAULT_UNITY_PLAN_DXF),
        help=f"DXF с PLAN_FLOOR для референса (по умолчанию: {DEFAULT_UNITY_PLAN_DXF})",
    )
    parser.add_argument("--floor", type=int, default=0, help="Номер этажа (0)")
    args = parser.parse_args()
    trajectories_folder = Path(args.trajectories_folder)
    grid_path = Path(args.grid_from)

    print("Загрузка треков Unity...")
    trajectories, all_x, all_y, n_traj = load_trajectories(trajectories_folder, args.floor)
    print(f"  Траекторий: {n_traj}, точек: {len(all_x)}")

    # Загрузка сетки BIRD
    print(f"Загрузка сетки из {grid_path}...")
    x_edges, y_edges = load_common_grid(grid_path)
    nx, ny = len(x_edges) - 1, len(y_edges) - 1

    # Трансформация Unity -> BIRD (scale + offset). Референс: PLAN_FLOOR из DXF или bbox треков.
    plan_dxf = Path(args.unity_plan_dxf) if args.unity_plan_dxf else None
    if plan_dxf and plan_dxf.exists():
        auto_sx, auto_sy, auto_ox, auto_oy = compute_unity_to_bird_transform_from_floor_plan(
            x_edges, y_edges, str(plan_dxf.resolve())
        )
        print(f"  Референс: PLAN_FLOOR из {plan_dxf}")
    else:
        auto_sx, auto_sy, auto_ox, auto_oy = compute_unity_to_bird_transform(x_edges, y_edges, all_x, all_y)
        print(f"  Референс: bbox треков (unity-plan-dxf не найден)")
    scale_x = args.scale_x if args.scale_x is not None else auto_sx
    scale_y = args.scale_y if args.scale_y is not None else auto_sy
    offset_x = args.offset_x if args.offset_x is not None else auto_ox
    offset_y = args.offset_y if args.offset_y is not None else auto_oy
    print(f"  Unity->BIRD: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}, offset_x={offset_x:.3f}, offset_y={offset_y:.3f} m")

    # Преобразование Unity → BIRD (метры)
    x_m, y_m = _unity_to_bird(np.array(all_x), np.array(all_y), scale_x, scale_y, offset_x, offset_y)

    heatmap, x_edges, y_edges = np.histogram2d(x_m, y_m, bins=[x_edges, y_edges])
    heatmap = heatmap.T

    ny, nx = heatmap.shape
    print(f"\nСетка BIRD: {nx} x {ny} ячеек (размер ячейки: {CELL_SIZE} м)")
    print(f"  Ячеек с density > 0: {np.sum(heatmap > 0)}")

    print("\nВычисление Time of Presence...")
    top_matrix, stop_durations = compute_time_of_presence(
        trajectories, x_edges, y_edges, nx, ny, scale_x, scale_y, offset_x, offset_y
    )
    top_sum = top_matrix.sum()
    print(f"  ToP sum: {top_sum:.1f} сек ({top_sum / 60:.1f} мин)")

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

    rows = []
    for iy in range(ny):
        for ix in range(nx):
            d = int(heatmap[iy, ix])
            top = float(top_matrix[iy, ix])
            if d > 0 or top > 0:
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

    out_json = {
        "matrix": heatmap.astype(int).tolist(),
        "matrix_time_of_presence": [[round(float(v), 2) for v in row] for row in top_matrix],
        "x_edges_m": [round(float(x), 4) for x in x_edges],
        "y_edges_m": [round(float(y), 4) for y in y_edges],
        "cell_size_m": CELL_SIZE,
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
            "trajectories_folder": str(trajectories_folder.resolve()),
            "source": "Unity_simulation",
            "grid_source": str(grid_path.resolve()),
            "unity_plan_dxf": str(plan_dxf.resolve()) if plan_dxf and plan_dxf.exists() else None,
            "unity_to_bird_scale_x": round(scale_x, 6),
            "unity_to_bird_scale_y": round(scale_y, 6),
            "unity_to_bird_offset_x": round(offset_x, 4),
            "unity_to_bird_offset_y": round(offset_y, 4),
        },
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
