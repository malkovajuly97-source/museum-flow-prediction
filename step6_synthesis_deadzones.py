"""
Этап 6: Сводный анализ и выявление мёртвых зон / перегруженных зон (этаж 0, 4 типа)

Скрипт:
1. Загружает результаты этапов 4–5 по экспонатам (наблюдаемость по стенам/комнатам)
2. Классифицирует стены и комнаты: мёртвые зоны (низкая наблюдаемость), перегруженные (высокая), норма
3. Строит план этажа 0 с выделением dead/overuse
4. Пишет сводный отчёт (типология, пространство, время, экспонаты, мёртвые/перегруженные зоны)
5. Сохраняет таблицы и графики в analysis_results_merged
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

BASE = Path(__file__).resolve().parent
MERGED_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR = BASE / "analysis_results_merged"
DATA_DIR = BASE / "bird-dataset-main" / "data"
PLAN_JSON = DATA_DIR / "NMFA_3floors_plan.json"

OUTPUT_DIR.mkdir(exist_ok=True)

# Пороги по квартилям: нижний 25% = dead_zone, верхний 25% = overuse
LOWER_QUANTILE = 0.25
UPPER_QUANTILE = 0.75


def load_plan_floor0():
    """Стены этажа 0: [{id, position: [(x,y),(x,y)]}, ...]."""
    if not PLAN_JSON.exists():
        return []
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


def load_and_aggregate():
    """Загружает наблюдения по стенам/комнатам, считает суммы по стенам и комнатам."""
    by_wall = pd.read_csv(MERGED_DIR / "spatial_observations_by_wall_type.csv")
    by_room = pd.read_csv(MERGED_DIR / "spatial_observations_by_room_type.csv")

    wall_totals = by_wall.groupby('wall_id')['n_observations'].sum().reset_index()
    wall_totals.columns = ['wall_id', 'n_observations_total']
    room_totals = by_room.groupby('room_id')['n_observations'].sum().reset_index()
    room_totals.columns = ['room_id', 'n_observations_total']

    return by_wall, by_room, wall_totals, room_totals


def classify_zones(wall_totals, room_totals):
    """Классификация: dead_zone (нижний квартиль), overuse (верхний), normal."""
    def _classify(series, low_q, high_q):
        q1 = series.quantile(low_q)
        q3 = series.quantile(high_q)
        def f(v):
            if v <= q1:
                return 'dead_zone'
            if v >= q3:
                return 'overuse'
            return 'normal'
        return f

    wall_totals = wall_totals.copy()
    room_totals = room_totals.copy()
    w_vals = wall_totals['n_observations_total']
    r_vals = room_totals['n_observations_total']

    f_w = _classify(w_vals, LOWER_QUANTILE, UPPER_QUANTILE)
    f_r = _classify(r_vals, LOWER_QUANTILE, UPPER_QUANTILE)
    wall_totals['zone_type'] = w_vals.apply(f_w)
    room_totals['zone_type'] = r_vals.apply(f_r)
    return wall_totals, room_totals


def save_deadzones_tables(wall_totals, room_totals, by_wall):
    """Сохраняет таблицы мёртвых/перегруженных зон."""
    w = wall_totals.copy()
    traj_max = by_wall.groupby('wall_id')['n_trajectories'].max()
    w['n_trajectories_max'] = w['wall_id'].map(traj_max)
    w.to_csv(OUTPUT_DIR / "deadzones_overuse_walls.csv", index=False)
    room_totals.to_csv(OUTPUT_DIR / "deadzones_overuse_rooms.csv", index=False)
    print("  deadzones_overuse_walls.csv, deadzones_overuse_rooms.csv")


def plot_deadzones_overuse(wall_totals, walls_geom, output_path):
    """План этажа 0: стены окрашены по типу зоны (dead_zone / normal / overuse)."""
    from matplotlib.lines import Line2D
    zone_map = wall_totals.set_index('wall_id')['zone_type'].to_dict()
    all_ids = {w['id'] for w in walls_geom}
    for wid in all_ids:
        if wid not in zone_map:
            zone_map[wid] = 'dead_zone'

    colors = {'dead_zone': (0.6, 0.6, 0.7), 'normal': (0.85, 0.9, 0.7), 'overuse': (0.9, 0.35, 0.2)}
    labels = {'dead_zone': 'Мёртвая зона', 'normal': 'Норма', 'overuse': 'Перегруженная'}

    fig, ax = plt.subplots(figsize=(14, 10))
    for w in walls_geom:
        pos = w['position']
        if len(pos) < 2:
            continue
        z = zone_map.get(w['id'], 'dead_zone')
        ax.plot([pos[0][0], pos[1][0]], [pos[0][1], pos[1][1]], color=colors[z], lw=3, solid_capstyle='round')
    leg = [Line2D([0], [0], color=colors[z], lw=4, label=labels[z]) for z in ['dead_zone', 'normal', 'overuse']]
    ax.legend(handles=leg, loc='upper left')
    ax.set_aspect('equal')
    ax.set_xlabel('X (план этажа)')
    ax.set_ylabel('Y (план этажа)')
    ax.set_title('Этаж 0: мёртвые зоны и перегруженные зоны по наблюдаемости экспонатов\n(нижний/верхний квартиль по числу наблюдений на стену)')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  {output_path.name}")


def write_synthesis_report(wall_totals, room_totals):
    """Пишет сводный отчёт: типология, пространство, время, экспонаты, мёртвые/перегруженные зоны."""
    path = OUTPUT_DIR / "synthesis_report_4types.md"
    n_dead_w = (wall_totals['zone_type'] == 'dead_zone').sum()
    n_over_w = (wall_totals['zone_type'] == 'overuse').sum()
    n_dead_r = (room_totals['zone_type'] == 'dead_zone').sum()
    n_over_r = (room_totals['zone_type'] == 'overuse').sum()

    overuse_rooms = room_totals[room_totals['zone_type'] == 'overuse'].sort_values('n_observations_total', ascending=False)
    dead_rooms = room_totals[room_totals['zone_type'] == 'dead_zone'].sort_values('n_observations_total')
    overuse_walls = wall_totals[wall_totals['zone_type'] == 'overuse'].sort_values('n_observations_total', ascending=False)
    dead_walls = wall_totals[wall_totals['zone_type'] == 'dead_zone'].sort_values('n_observations_total')

    lines = [
        "# Сводный отчёт (этапы 1–6): типология, пространство, время, экспонаты, мёртвые и перегруженные зоны",
        "",
        "## 1. Типология поведения (4 типа, этаж 0)",
        "",
        "Источник: `behavior_types_summary_merged.csv`, `floor0_trajectories_clustered_merged.csv`.",
        "",
        "| Тип | Траекторий | Скорость (средн.) | Длительность (средн.) | Экспонатов (средн.) | Остановок (средн.) |",
        "|-----|------------|-------------------|------------------------|----------------------|---------------------|",
    ]
    bt = pd.read_csv(MERGED_DIR / "behavior_types_summary_merged.csv")
    for _, r in bt.iterrows():
        lines.append(f"| {r['behavior_type']} | {int(r['n_trajectories'])} | {r['avg_speed']:.2f} | {r['avg_duration']:.0f} | {r['avg_items']:.0f} | {r['avg_stops']:.0f} |")

    lines += [
        "",
        "---",
        "## 2. Пространство: квадранты и зоны",
        "",
        "Источник: `spatial_preferences_by_type.csv`. Квадранты SW/SE/NW/NE по медиане координат.",
        "",
        "- **SE (юго-восток):** Исследователь, Активный обходчик — интенсивное использование.",
        "- **NW (северо-запад):** Быстрый, Медленный — менее плотный просмотр, транзит/созерцание.",
        "",
        "---",
        "## 3. Время визита: фазы",
        "",
        "Источник: `temporal_patterns_by_type.csv`. Фазы: начало [0–0.33), середина [0.33–0.67), конец [0.67–1.0].",
        "",
        "- **Активный обходчик, Медленный:** сильный перекос в начало визита, мало активности в конце.",
        "- **Быстрый, Исследователь:** заметная доля в конце визита (финальный обход, движение к выходу).",
        "",
        "---",
        "## 4. Экспонаты и стены",
        "",
        "Источник: `spatial_observations_by_room_type.csv`, `spatial_observations_by_wall_type.csv`, `spatial_top_exhibits_by_type.csv`.",
        "",
        "- Комнаты-лидеры по наблюдаемости: **Room_7, Room_12, Room_13, Room_10**.",
        "- Топ экспонаты по типам: Les Voluptueux, La douleur, La Toussaint и др. (см. `spatial_top_exhibits_by_type.csv`).",
        "",
        "---",
        "## 5. Мёртвые зоны и перегруженные зоны (этап 6)",
        "",
        f"Классификация по квартилям числа наблюдений: нижние 25% — **мёртвая зона**, верхние 25% — **перегруженная зона**.",
        "",
        f"- **Стены:** мёртвых зон — {n_dead_w}, перегруженных — {n_over_w}, норма — {len(wall_totals) - n_dead_w - n_over_w}.",
        f"- **Комнаты:** мёртвых зон — {n_dead_r}, перегруженных — {n_over_r}, норма — {len(room_totals) - n_dead_r - n_over_r}.",
        "",
        "### 5.1. Перегруженные комнаты (кандидаты в узкие места)",
        "",
    ]
    if len(overuse_rooms) > 0:
        lines.append("| room_id | n_observations_total |")
        lines.append("|---------|----------------------|")
        for _, r in overuse_rooms.head(15).iterrows():
            lines.append(f"| {r['room_id']} | {int(r['n_observations_total'])} |")
    else:
        lines.append("(нет при заданных порогах)")
    lines += [
        "",
        "### 5.2. Мёртвые комнаты (низкая наблюдаемость)",
        "",
    ]
    if len(dead_rooms) > 0:
        lines.append("| room_id | n_observations_total |")
        lines.append("|---------|----------------------|")
        for _, r in dead_rooms.head(15).iterrows():
            lines.append(f"| {r['room_id']} | {int(r['n_observations_total'])} |")
    else:
        lines.append("(нет при заданных порогах)")
    lines += [
        "",
        "### 5.3. Перегруженные стены (фрагмент)",
        "",
    ]
    if len(overuse_walls) > 0:
        lines.append("| wall_id | n_observations_total |")
        lines.append("|---------|----------------------|")
        for _, r in overuse_walls.head(15).iterrows():
            lines.append(f"| {r['wall_id']} | {int(r['n_observations_total'])} |")
    else:
        lines.append("(нет при заданных порогах)")
    lines += [
        "",
        "---",
        "## 6. Выводы для агентной модели и проектирования",
        "",
        "1. **Типы агентов:** задавать доли 4 типов (Активный обходчик, Быстрый, Исследователь, Медленный) и их параметры по `behavior_types_summary_merged.csv`.",
        "2. **Пространство:** правила «когда–где» по `temporal_by_quadrant_phase.csv`, `spatial_preferences_by_type.csv` и `spatial_observations_by_room_type.csv` / `spatial_observations_by_wall_type.csv`.",
        "3. **Мёртвые зоны:** стены/комнаты из `deadzones_overuse_walls.csv`, `deadzones_overuse_rooms.csv` с zone_type=dead_zone — низкая вероятность остановки или особые сценарии привлечения.",
        "4. **Перегруженные зоны:** zone_type=overuse — кандидаты в узкие места; при симуляции учитывать ограничение пропускной способности и возможные очереди.",
        "",
        "---",
        "",
        "*Сводный отчёт сформирован скриптом `step6_synthesis_deadzones.py` по результатам этапов 1–5 и классификации мёртвых/перегруженных зон (этаж 0, 4 типа поведения).*",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {path.name}")


def main():
    print("=" * 70)
    print("ЭТАП 6: СВОДНЫЙ АНАЛИЗ И МЁРТВЫЕ / ПЕРЕГРУЖЕННЫЕ ЗОНЫ")
    print("=" * 70)

    by_wall, by_room, wall_totals, room_totals = load_and_aggregate()
    wall_totals, room_totals = classify_zones(wall_totals, room_totals)
    save_deadzones_tables(wall_totals, room_totals, by_wall)

    walls_geom = load_plan_floor0()
    if walls_geom:
        plot_deadzones_overuse(wall_totals, walls_geom, OUTPUT_DIR / "spatial_deadzones_overuse.png")
    else:
        print("  План этажа не найден, график по стенам пропущен.")

    write_synthesis_report(wall_totals, room_totals)

    print("\n" + "=" * 70)
    print("ЭТАП 6 ЗАВЕРШЁН")
    print("=" * 70)
    print("Результаты в каталоге:", OUTPUT_DIR)
    print("  - deadzones_overuse_walls.csv, deadzones_overuse_rooms.csv")
    print("  - spatial_deadzones_overuse.png")
    print("  - synthesis_report_4types.md")


if __name__ == "__main__":
    main()
