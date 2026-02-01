import os
from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection


# Путь к папке с нормализованными траекториями
TRAJ_DIR = Path("bird-dataset-main/data/normalized_trajectories")

# Путь к файлу с планом музея
PLAN_FILE = Path("bird-dataset-main/data/NMFA_3floors_plan.json")

# Коэффициент масштабирования: 5401 единиц = 55.07 метров
# 1 единица координат = 55.07 / 5401 ≈ 0.0102 метра
SCALE_FACTOR = 55.07 / 5401  # метра на единицу координат

# Размер ячейки сетки в координатных единицах (как в create_trajectories_heatmap.py)
CELL_SIZE_UNITS = 50.0
CELL_SIZE_METERS = CELL_SIZE_UNITS * SCALE_FACTOR


def draw_floor_plan(ax, plan_file: Path, scale_factor: float) -> bool:
    """Отрисовка плана этажа (этаж 0) в метрах."""
    if not plan_file.exists():
        return False

    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            plan_data = json.load(f)

        for floor in plan_data.get("floors", []):
            if floor.get("number", 0) == 0:
                for wall in floor.get("walls", []):
                    if len(wall.get("position", [])) >= 2:
                        x_coords = [pos["x"] * scale_factor for pos in wall["position"]]
                        y_coords = [pos["y"] * scale_factor for pos in wall["position"]]
                        ax.plot(
                            x_coords,
                            y_coords,
                            "k-",
                            linewidth=1.5,
                            alpha=0.6,
                            zorder=10,
                        )
        return True
    except Exception as e:
        print(f"Не удалось загрузить план этажа: {e}")
        return False


def load_trajectories():
    """Загружаем все траектории (этаж 0) и конвертируем координаты в метры.

    Возвращает:
      trajectories_m: список траекторий, каждая траектория — список (x_m, y_m)
      all_x_m, all_y_m: объединённые координаты в метрах (для вычисления границ)
      csv_files: список обработанных файлов
    """
    csv_files = list(TRAJ_DIR.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"Не найдено CSV файлов в {TRAJ_DIR}")

    print(f"Найдено {len(csv_files)} файлов с траекториями")

    trajectories_m = []
    all_x_m = []
    all_y_m = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            # Фильтруем только этаж 0 (как в других скриптах)
            df = df[df["floorNumber"] == 0]

            if df.empty:
                print(f"{csv_file.name}: нет точек на этаже 0, пропускаем")
                continue

            x_units = df["x"].to_numpy()
            y_units = df["y"].to_numpy()

            x_m = x_units * SCALE_FACTOR
            y_m = y_units * SCALE_FACTOR

            traj = list(zip(x_m, y_m))
            trajectories_m.append(traj)

            all_x_m.extend(x_m)
            all_y_m.extend(y_m)

            print(f"Загружен {csv_file.name}: {len(df)} точек (этаж 0)")
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file.name}: {e}")

    if not trajectories_m:
        raise ValueError("Не удалось загрузить ни одной траектории для этажа 0")

    all_x_m = np.array(all_x_m, dtype=float)
    all_y_m = np.array(all_y_m, dtype=float)

    print(f"\nВсего траекторий: {len(trajectories_m)}")
    print(f"Всего точек (этаж 0): {len(all_x_m)}")
    print(
        f"Диапазон X (м): {all_x_m.min():.2f} - {all_x_m.max():.2f}, "
        f"Y (м): {all_y_m.min():.2f} - {all_y_m.max():.2f}"
    )

    return trajectories_m, all_x_m, all_y_m, csv_files


def create_overlay_image(trajectories_m, all_x_m, all_y_m):
    """Визуализация 1: простая накладка треков полупрозрачными линиями."""
    print("\n" + "=" * 60)
    print("Создание визуализации 1: Накладка треков (line overlay)")
    print("=" * 60)

    fig, ax = plt.subplots(figsize=(20, 16))

    # Чёрный фон
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    # Сначала рисуем все траектории базовым голубым цветом
    for traj in trajectories_m:
        xs = [p[0] for p in traj]
        ys = [p[1] for p in traj]
        ax.plot(xs, ys, color="#00FFFF", alpha=0.05, linewidth=1.0)

    # Затем считаем плотность и перекрашиваем только самые плотные сегменты
    padding = 2.0  # метра
    min_x = all_x_m.min() - padding
    max_x = all_x_m.max() + padding
    min_y = all_y_m.min() - padding
    max_y = all_y_m.max() + padding

    # Для оверлея делаем сетку чуть более частой, чем основная heatmap
    overlay_cell = CELL_SIZE_METERS / 2.0
    x_edges = np.arange(min_x, max_x + overlay_cell, overlay_cell)
    y_edges = np.arange(min_y, max_y + overlay_cell, overlay_cell)

    hist, x_edges_h, y_edges_h = np.histogram2d(all_x_m, all_y_m, bins=[x_edges, y_edges])
    hist = hist.T  # чтобы совпало с ориентацией осей

    non_zero = hist[hist > 0]
    if non_zero.size > 0:
        # Порог по верхним плотностям — только очень загруженные участки
        vmin_h = np.percentile(non_zero, 40)
        vmax_h = np.percentile(non_zero, 99)

        # Нормализация в [0, 1] и гамма‑усиление
        norm_hist = (hist - vmin_h) / (vmax_h - vmin_h + 1e-9)
        norm_hist[norm_hist < 0] = 0
        norm_hist[norm_hist > 1] = 1
        gamma = 0.6
        norm_hist = norm_hist**gamma

        # Палитра от голубого к зелёно‑жёлто‑оранжевому
        warm_colors = [
            "#00FFFF",  # как базовые линии
            "#00FF00",  # зелёный
            "#ADFF2F",  # yellow‑green
            "#FFFF00",  # жёлтый
            "#FFA500",  # оранжевый
            "#FF4500",  # оранжево‑красный
        ]
        warm_cmap = LinearSegmentedColormap.from_list(
            "trajectory_overlay_warm", warm_colors, N=256
        )

        # Готовим сегменты и цвета для LineCollection,
        # цвет каждого сегмента определяется по плотности в его середине
        segments = []
        colors = []

        def point_to_bin(x, y):
            ix = np.searchsorted(x_edges_h, x, side="right") - 1
            iy = np.searchsorted(y_edges_h, y, side="right") - 1
            if ix < 0 or ix >= len(x_edges_h) - 1 or iy < 0 or iy >= len(y_edges_h) - 1:
                return None
            return ix, iy

        for traj in trajectories_m:
            if len(traj) < 2:
                continue
            for (x1, y1), (x2, y2) in zip(traj[:-1], traj[1:]):
                mx = 0.5 * (x1 + x2)
                my = 0.5 * (y1 + y2)
                bin_idx = point_to_bin(mx, my)
                if bin_idx is None:
                    continue
                ix, iy = bin_idx
                d = norm_hist[iy, ix]
                if d <= 0:
                    # низкая плотность — оставляем только базовую голубую линию
                    continue
                color = warm_cmap(d)
                segments.append([(x1, y1), (x2, y2)])
                colors.append(color)

        if segments:
            lc = LineCollection(
                segments,
                colors=colors,
                linewidths=1.4,
                alpha=1.0,
                capstyle="round",
            )
            ax.add_collection(lc)

    # План этажа поверх
    draw_floor_plan(ax, PLAN_FILE, SCALE_FACTOR)

    ax.set_xlabel("X координата (м)", fontsize=14, color="white")
    ax.set_ylabel("Y координата (м)", fontsize=14, color="white")
    ax.set_title(
        "Накладка треков (line overlay)\n"
        f"Траекторий: {len(trajectories_m)}, точек: {len(all_x_m):,}",
        fontsize=16,
        fontweight="bold",
        color="white",
    )
    ax.tick_params(colors="white")
    ax.set_aspect("equal")
    ax.grid(False)

    # Немного отступов от границ
    padding = 2.0  # метра
    ax.set_xlim(all_x_m.min() - padding, all_x_m.max() + padding)
    ax.set_ylim(all_y_m.min() - padding, all_y_m.max() + padding)

    output_file = "trajectories_lines_overlay.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Визуализация накладки треков сохранена в {output_file}")


def create_line_density_heatmap(trajectories_m, all_x_m, all_y_m):
    """Визуализация 2: line density heatmap.

    Реализация без дополнительных библиотек: для каждого отрезка траектории
    равномерно дискретизируем его по длине и распределяем точки по ячейкам сетки.
    """
    print("\n" + "=" * 60)
    print("Создание визуализации 2: Line density heatmap")
    print("=" * 60)

    # Границы области
    padding = 2.0  # метра
    min_x = all_x_m.min() - padding
    max_x = all_x_m.max() + padding
    min_y = all_y_m.min() - padding
    max_y = all_y_m.max() + padding

    # Сетка по X и Y в метрах
    x_edges = np.arange(min_x, max_x + CELL_SIZE_METERS, CELL_SIZE_METERS)
    y_edges = np.arange(min_y, max_y + CELL_SIZE_METERS, CELL_SIZE_METERS)

    nx = len(x_edges) - 1
    ny = len(y_edges) - 1
    print(f"Размер сетки: {nx} x {ny} ячеек")
    print(f"Размер ячейки: {CELL_SIZE_METERS:.2f} м")

    density = np.zeros((ny, nx), dtype=float)

    # Шаг дискретизации вдоль отрезка — половина размера ячейки
    step = CELL_SIZE_METERS / 2.0

    for traj_idx, traj in enumerate(trajectories_m, start=1):
        if len(traj) < 2:
            continue

        for (x1, y1), (x2, y2) in zip(traj[:-1], traj[1:]):
            dx = x2 - x1
            dy = y2 - y1
            length = np.hypot(dx, dy)
            if length == 0:
                continue

            # Кол-во точек дискретизации вдоль отрезка
            n_samples = max(2, int(length / step) + 1)

            ts = np.linspace(0.0, 1.0, n_samples)
            xs = x1 + dx * ts
            ys = y1 + dy * ts

            # Индексы ячеек по X и Y
            ix = np.searchsorted(x_edges, xs, side="right") - 1
            iy = np.searchsorted(y_edges, ys, side="right") - 1

            # Отбрасываем точки вне области
            mask = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
            ix_valid = ix[mask]
            iy_valid = iy[mask]

            # Накапливаем плотность
            if ix_valid.size > 0:
                np.add.at(density, (iy_valid, ix_valid), 1.0)

        if traj_idx % 10 == 0:
            print(f"Обработано траекторий: {traj_idx}/{len(trajectories_m)}")

    # Подготавливаем данные для отображения
    non_zero = density[density > 0]
    if non_zero.size > 0:
        # Окно по верхним плотностям — хотим подчеркнуть пересечения
        vmin = np.percentile(non_zero, 30)
        vmax = np.percentile(non_zero, 99)
        density_to_show = density.copy()
        density_to_show[density_to_show < vmin] = 0
        print(
            f"Диапазон плотности (не нулевые): {non_zero.min():.1f} - {non_zero.max():.1f}"
        )
        print(f"Отображаемый диапазон: {vmin:.1f} - {vmax:.1f} (30–99 перцентили)")

        # Нелинейное усиление: поднимаем верхние значения ближе к 1,
        # чтобы пересечения уходили в самые тёплые цвета
        scaled = np.zeros_like(density_to_show, dtype=float)
        mask = density_to_show > 0
        scaled[mask] = (density_to_show[mask] - vmin) / (vmax - vmin + 1e-9)
        scaled[scaled < 0] = 0
        scaled[scaled > 1] = 1
        # гамма-коррекция (gamma < 1 усиливает яркие области)
        gamma = 0.6
        density_display = np.zeros_like(scaled)
        density_display[mask] = scaled[mask] ** gamma
    else:
        vmin = 0.0
        vmax = 1.0
        density_to_show = density
        density_display = density
        print("Все значения плотности равны 0")

    # Цветовая карта: зелёный -> жёлтый -> оранжевый -> красный (тёплые оттенки)
    colors = [
        "#00FF00",  # зелёный
        "#ADFF2F",  # yellow‑green
        "#FFFF00",  # жёлтый
        "#FFA500",  # оранжевый
        "#FF4500",  # оранжево‑красный
    ]
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list("trajectory_line_density", colors, N=n_bins)

    extent = [x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]]

    fig, ax = plt.subplots(figsize=(20, 16))
    # Тёмный фон, как в overlay
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    im = ax.imshow(
        density_display,
        extent=extent,
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
        origin="lower",
        interpolation="bilinear",
        alpha=0.85,
    )

    # План этажа поверх
    draw_floor_plan(ax, PLAN_FILE, SCALE_FACTOR)

    ax.set_xlabel("X координата (м)", fontsize=14)
    ax.set_ylabel("Y координата (м)", fontsize=14)
    ax.set_title(
        "Line density heatmap (плотность по линейным трекам)\n"
        f"Траекторий: {len(trajectories_m)}, точек: {len(all_x_m):,}",
        fontsize=16,
        fontweight="bold",
    )
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3, linestyle="--")

    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(
        "Line density (кол-во дискретизированных точек на ячейку)",
        fontsize=12,
        rotation=270,
        labelpad=20,
    )

    output_file = "trajectories_line_density_heatmap.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Line density heatmap сохранена в {output_file}")


def main():
    trajectories_m, all_x_m, all_y_m, csv_files = load_trajectories()
    print(f"Используем файлов с траекториями: {len(csv_files)}")

    create_overlay_image(trajectories_m, all_x_m, all_y_m)
    create_line_density_heatmap(trajectories_m, all_x_m, all_y_m)

    print("\nГотово!")
    print("1. Накладка треков: trajectories_lines_overlay.png")
    print("2. Line density heatmap: trajectories_line_density_heatmap.png")


if __name__ == "__main__":
    main()

