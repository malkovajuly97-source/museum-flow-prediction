"""
Разовый анализ: через какие зоны (входы) заходили и из каких (выходы) выходили
по реальным траекториям BIRD (этаж 0). Первая точка траектории = условный вход,
последняя = условный выход. Зоны из Floor_0.dxf, слой Area.

Запуск из корня проекта или из model_search: python model_search/analyze_entrance_exit_zones.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PATH_DXF = BASE / "Floor_0.dxf"
LAYER_AREA = "Area"
TRAJECTORIES_FOLDER = PROJECT_ROOT / "bird-dataset-main" / "data" / "normalized_trajectories"


def main():
    from room_popularity import parse_zones_from_dxf, load_trajectories_from_csv, assign_point_to_zone

    if not PATH_DXF.exists():
        print(f"Ошибка: не найден {PATH_DXF}")
        return
    if not TRAJECTORIES_FOLDER.exists():
        print(f"Ошибка: не найдена папка {TRAJECTORIES_FOLDER}")
        return

    polygons_with_zone, zone_labels = parse_zones_from_dxf(PATH_DXF, LAYER_AREA)
    trajectories = load_trajectories_from_csv(TRAJECTORIES_FOLDER, floor_number=0)

    entry_counts = {}
    exit_counts = {}
    entry_exit_pairs = {}

    for points in trajectories:
        if len(points) < 1:
            continue
        x_first, y_first = points[0]
        x_last, y_last = points[-1]
        entry_zone = assign_point_to_zone(x_first, y_first, polygons_with_zone, zone_labels)
        exit_zone = assign_point_to_zone(x_last, y_last, polygons_with_zone, zone_labels)

        entry_counts[entry_zone] = entry_counts.get(entry_zone, 0) + 1
        exit_counts[exit_zone] = exit_counts.get(exit_zone, 0) + 1
        key = (entry_zone, exit_zone)
        entry_exit_pairs[key] = entry_exit_pairs.get(key, 0) + 1

    n_traj = len(trajectories)
    n_entry_zones = len([z for z in entry_counts if z >= 0])
    n_exit_zones = len([z for z in exit_counts if z >= 0])

    lines = [
        "=" * 60,
        "ВХОДЫ И ВЫХОДЫ ПО РЕАЛЬНЫМ ТРАЕКТОРИЯМ (BIRD, этаж 0)",
        "Первая точка траектории = вход (зона), последняя = выход (зона).",
        "Зоны из Floor_0.dxf, слой Area. Лестницы в проекте: зоны 1, 2, 5 и между 12–13.",
        "=" * 60,
        f"Всего траекторий: {n_traj}",
        f"Уникальных зон входа (по первой точке): {n_entry_zones}",
        f"Уникальных зон выхода (по последней точке): {n_exit_zones}",
        "",
        "--- ВХОДЫ (зона первой точки) ---",
    ]
    for z in sorted(entry_counts.keys(), key=lambda x: (x if x >= 0 else 99)):
        label = f"зона {z}" if z >= 0 else "(вне зон)"
        lines.append(f"  {label}: {entry_counts[z]} траекторий ({100 * entry_counts[z] / n_traj:.1f}%)")
    lines.extend(["", "--- ВЫХОДЫ (зона последней точки) ---"])
    for z in sorted(exit_counts.keys(), key=lambda x: (x if x >= 0 else 99)):
        label = f"зона {z}" if z >= 0 else "(вне зон)"
        lines.append(f"  {label}: {exit_counts[z]} траекторий ({100 * exit_counts[z] / n_traj:.1f}%)")
    lines.extend(["", "--- ПАРЫ ВХОД -> ВЫХОД (топ-15) ---"])
    sorted_pairs = sorted(entry_exit_pairs.items(), key=lambda x: -x[1])[:15]
    for (ez, xz), count in sorted_pairs:
        e_label = f"зона {ez}" if ez >= 0 else "?"
        x_label = f"зона {xz}" if xz >= 0 else "?"
        lines.append(f"  {e_label} -> {x_label}: {count} траекторий")
    lines.append("=" * 60)

    report = "\n".join(lines)
    out_file = BASE / "entrance_exit_zones_report.txt"
    out_file.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nОтчёт сохранён: {out_file}")


if __name__ == "__main__":
    main()
