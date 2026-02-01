"""
Расширение этапа 4: пространственный анализ с привязкой к экспонатам и стенам

Скрипт:
1. Загружает типы поведения (4 типа) и наблюдения экспонатов (start_obs_artworks)
2. Объединяет с artworks_dataset (room_id, wall_id, image id)
3. Агрегирует по (тип поведения, комната), (тип, стена), топ экспонатов по типам
4. Строит heatmap наблюдаемости по стенам на плане этажа 0 (NMFA_3floors_plan.json)
5. Сохраняет таблицы и графики в analysis_results_merged
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Пути
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "bird-dataset-main" / "data"
MERGED_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR.mkdir(exist_ok=True)

CLUSTERED_MERGED = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"
START_OBS_DIR = DATA_DIR / "start_obs_artworks"
ARTWORKS_CSV = DATA_DIR / "artworks_dataset.csv"
PLAN_JSON = DATA_DIR / "NMFA_3floors_plan.json"


def load_behavior_types():
    """Загружает trajectory_id -> behavior_type."""
    df = pd.read_csv(CLUSTERED_MERGED)
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    return df[['trajectory_id', 'behavior_type']]


def load_observations(trajectory_ids):
    """Загружает наблюдения из start_obs_artworks для заданных trajectory_id."""
    trajectory_ids = set(str(t) for t in trajectory_ids)
    rows = []
    for tid in trajectory_ids:
        path = START_OBS_DIR / f"items_{tid}.csv"
        if not path.exists():
            continue
        try:
            t = pd.read_csv(path)
            t['trajectory_id'] = str(tid)
            rows.append(t)
        except Exception as e:
            continue
    if not rows:
        return pd.DataFrame(columns=['timestamp', 'floorNumber', 'paintingId', 'trajectory_id'])
    out = pd.concat(rows, ignore_index=True)
    out['paintingId'] = out['paintingId'].astype(str)
    return out


def load_artworks_floor0():
    """Загружает каталог экспонатов этажа 0 (image id -> room_id, wall_id)."""
    df = pd.read_csv(ARTWORKS_CSV)
    # колонка с пробелом в имени
    id_col = 'image id' if 'image id' in df.columns else 'image_id'
    df = df[df['floor'] == 0].copy()
    df[id_col] = df[id_col].astype(str)
    return df[[id_col, 'wall_id', 'room_id', 'painting name']].rename(columns={id_col: 'paintingId'})


def load_plan_floor0():
    """Возвращает список стен этажа 0: [{id, position: [(x,y),(x,y)]}, ...]."""
    with open(PLAN_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for floor in data.get('floors', []):
        if floor.get('number') == 0:
            walls = []
            for w in floor.get('walls', []):
                pos = w.get('position', [])
                pts = [(p['x'], p['y']) for p in pos]
                walls.append({'id': w['id'], 'position': pts})
            return walls
    return []


def merge_obs_with_artworks_and_types(obs, artworks, types):
    """Объединяет наблюдения с комнатами/стенами и типами поведения."""
    obs = obs.merge(types, on='trajectory_id', how='inner')
    obs = obs.merge(artworks, on='paintingId', how='inner')
    obs = obs[obs['floorNumber'] == 0]
    return obs


def aggregate_by_room_and_wall(df):
    """Агрегация по (behavior_type, room_id) и (behavior_type, wall_id)."""
    by_room = df.groupby(['behavior_type', 'room_id']).agg(
        n_observations=('paintingId', 'count'),
        n_trajectories=('trajectory_id', 'nunique'),
    ).reset_index()
    total = by_room.groupby('behavior_type')['n_observations'].transform('sum')
    by_room['pct_obs'] = (100.0 * by_room['n_observations'] / total).round(2)

    by_wall = df.groupby(['behavior_type', 'wall_id']).agg(
        n_observations=('paintingId', 'count'),
        n_trajectories=('trajectory_id', 'nunique'),
    ).reset_index()
    total_w = by_wall.groupby('behavior_type')['n_observations'].transform('sum')
    by_wall['pct_obs'] = (100.0 * by_wall['n_observations'] / total_w).round(2)

    return by_room, by_wall


def aggregate_top_exhibits(df, top_n=15):
    """Топ экспонатов по числу наблюдений для каждого типа."""
    by_ex = df.groupby(['behavior_type', 'paintingId', 'painting name', 'room_id', 'wall_id']).agg(
        n_observations=('paintingId', 'count'),
        n_trajectories=('trajectory_id', 'nunique'),
    ).reset_index()
    top = by_ex.sort_values(['behavior_type', 'n_observations'], ascending=[True, False])
    top = top.groupby('behavior_type').head(top_n).reset_index(drop=True)
    return top


def plot_walls_heatmap(by_wall, walls_geom, output_path):
    """Рисует стены этажа 0, окрашенные по суммарной наблюдаемости (все типы)."""
    wall_totals = by_wall.groupby('wall_id')['n_observations'].sum().to_dict()
    all_wall_ids = {w['id'] for w in walls_geom}
    for wid in all_wall_ids:
        if wid not in wall_totals:
            wall_totals[wid] = 0
    vals = list(wall_totals.values())
    vmin, vmax = (min(vals), max(vals)) if vals else (0, 1)

    fig, ax = plt.subplots(figsize=(14, 10))
    for w in walls_geom:
        pid = w['id']
        pos = w['position']
        if len(pos) < 2:
            continue
        x = [pos[0][0], pos[1][0]]
        y = [pos[0][1], pos[1][1]]
        v = wall_totals.get(pid, 0)
        norm = (v - vmin) / (vmax - vmin + 1e-9)
        color = plt.cm.YlOrRd(norm)
        ax.plot(x, y, color=color, lw=4, solid_capstyle='round')

    ax.set_aspect('equal')
    ax.set_xlabel('X (план этажа)')
    ax.set_ylabel('Y (план этажа)')
    ax.set_title('Наблюдаемость по стенам (сумма по всем типам поведения, этаж 0)')
    sm = plt.cm.ScalarMappable(cmap=plt.cm.YlOrRd, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.6)
    cbar.set_label('Число наблюдений экспонатов на стене')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_walls_by_type(by_wall, walls_geom, output_path):
    """Четыре маленьких плана: наблюдаемость по стенам для каждого типа."""
    types = sorted(by_wall['behavior_type'].unique())
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()
    for idx, bt in enumerate(types):
        if idx >= len(axes):
            break
        ax = axes[idx]
        sub = by_wall[by_wall['behavior_type'] == bt]
        wall_totals = sub.set_index('wall_id')['n_observations'].to_dict()
        all_wall_ids = {w['id'] for w in walls_geom}
        for wid in all_wall_ids:
            if wid not in wall_totals:
                wall_totals[wid] = 0
        vals = [wall_totals.get(w['id'], 0) for w in walls_geom]
        vmin, vmax = 0, max(vals) if vals else 1
        for w in walls_geom:
            pid = w['id']
            pos = w['position']
            if len(pos) < 2:
                continue
            x = [pos[0][0], pos[1][0]]
            y = [pos[0][1], pos[1][1]]
            v = wall_totals.get(pid, 0)
            norm = (v - vmin) / (vmax - vmin + 1e-9)
            color = plt.cm.YlOrRd(norm)
            ax.plot(x, y, color=color, lw=2, solid_capstyle='round')
        ax.set_aspect('equal')
        ax.set_title(bt)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
    fig.suptitle('Наблюдаемость по стенам по типам поведения (этаж 0)', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    print("=" * 70)
    print("ПРОСТРАНСТВЕННЫЙ АНАЛИЗ С ПРИВЯЗКОЙ К ЭКСПОНАТАМ И СТЕНАМ")
    print("=" * 70)

    types = load_behavior_types()
    tids = types['trajectory_id'].tolist()
    print(f"\nТраекторий с типами: {len(tids)}")

    obs = load_observations(tids)
    print(f"Наблюдений загружено: {len(obs)}")
    if obs.shape[0] == 0:
        print("Нет файлов obs или пустые. Проверьте путь:", START_OBS_DIR)
        return
    print(f"Траекторий с наблюдениями: {obs['trajectory_id'].nunique()}")

    artworks = load_artworks_floor0()
    print(f"Экспонатов этажа 0 в каталоге: {len(artworks)}")

    df = merge_obs_with_artworks_and_types(obs, artworks, types)
    print(f"После объединения (тип + комната/стена): {len(df)} записей, {df['trajectory_id'].nunique()} траекторий")

    by_room, by_wall = aggregate_by_room_and_wall(df)
    top_ex = aggregate_top_exhibits(df, top_n=15)

    by_room.to_csv(OUTPUT_DIR / "spatial_observations_by_room_type.csv", index=False)
    by_wall.to_csv(OUTPUT_DIR / "spatial_observations_by_wall_type.csv", index=False)
    top_ex.to_csv(OUTPUT_DIR / "spatial_top_exhibits_by_type.csv", index=False)
    print(f"\nТаблицы сохранены:")
    print(f"  - spatial_observations_by_room_type.csv")
    print(f"  - spatial_observations_by_wall_type.csv")
    print(f"  - spatial_top_exhibits_by_type.csv")

    walls_geom = load_plan_floor0()
    print(f"Стен на плане этажа 0: {len(walls_geom)}")

    plot_walls_heatmap(by_wall, walls_geom, OUTPUT_DIR / "spatial_walls_heatmap_all_types.png")
    plot_walls_by_type(by_wall, walls_geom, OUTPUT_DIR / "spatial_walls_heatmap_by_type.png")
    print(f"Графики сохранены: spatial_walls_heatmap_all_types.png, spatial_walls_heatmap_by_type.png")

    print("\n" + "=" * 70)
    print("ГОТОВО")
    print("=" * 70)


if __name__ == "__main__":
    main()
