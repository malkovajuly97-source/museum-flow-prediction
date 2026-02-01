import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import json
import os
from pathlib import Path

# Опциональный импорт scipy для KDE
try:
    from scipy.stats import gaussian_kde
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Внимание: scipy не установлен, KDE heatmap будет пропущена")

# Путь к папке с нормализованными траекториями
trajectories_dir = Path('bird-dataset-main/data/normalized_trajectories')

# Собираем все CSV файлы
csv_files = list(trajectories_dir.glob('*.csv'))

if not csv_files:
    raise ValueError(f"Не найдено CSV файлов в {trajectories_dir}")

print(f"Найдено {len(csv_files)} файлов с траекториями")

# Загружаем все траектории
all_x = []
all_y = []
all_floors = []

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        all_x.extend(df['x'].values)
        all_y.extend(df['y'].values)
        all_floors.extend(df['floorNumber'].values)
        print(f"Загружен {csv_file.name}: {len(df)} точек")
    except Exception as e:
        print(f"Ошибка при загрузке {csv_file.name}: {e}")

# Преобразуем в numpy массивы
all_x = np.array(all_x)
all_y = np.array(all_y)
all_floors = np.array(all_floors)

print(f"\nВсего точек до фильтрации: {len(all_x)}")
print(f"Этажи: {np.unique(all_floors)}")

# Фильтруем только этаж 0
floor_mask = all_floors == 0
all_x = all_x[floor_mask]
all_y = all_y[floor_mask]
all_floors = all_floors[floor_mask]

print(f"\nТочек на этаже 0: {len(all_x)}")
print(f"Диапазон X: {all_x.min():.2f} - {all_x.max():.2f}")
print(f"Диапазон Y: {all_y.min():.2f} - {all_y.max():.2f}")

# Коэффициент масштабирования: 5401 единиц = 55.07 метров
# 1 единица координат = 55.07 / 5401 ≈ 0.0102 метра
SCALE_FACTOR = 55.07 / 5401  # метра на единицу координат
print(f"\nКоэффициент масштабирования: {SCALE_FACTOR:.6f} м/единица")
print(f"(5401 единиц = 55.07 метров)")

# Конвертируем координаты в метры
all_x_meters = all_x * SCALE_FACTOR
all_y_meters = all_y * SCALE_FACTOR

print(f"Диапазон X (в метрах): {all_x_meters.min():.2f} - {all_x_meters.max():.2f} м")
print(f"Диапазон Y (в метрах): {all_y_meters.min():.2f} - {all_y_meters.max():.2f} м")

# Параметры для heatmap
# Возвращаем предыдущую сетку: фиксированный шаг в единицах координат (50 единиц)
cell_size_units = 50.0  # Размер ячейки в единицах координат
cell_size_meters = cell_size_units * SCALE_FACTOR  # Соответствие в метрах
print(f"Размер ячейки: {cell_size_units} единиц координат ({cell_size_meters:.2f} м)")

# Границы области в метрах
min_x, max_x = all_x_meters.min(), all_x_meters.max()
min_y, max_y = all_y_meters.min(), all_y_meters.max()

# Расширяем границы немного (в метрах)
padding_meters = 2.0  # 2 метра отступ
min_x -= padding_meters
max_x += padding_meters
min_y -= padding_meters
max_y += padding_meters

# Создаем сетку: сначала в единицах координат
x_bins_units = np.arange(all_x.min(), all_x.max() + cell_size_units, cell_size_units)
y_bins_units = np.arange(all_y.min(), all_y.max() + cell_size_units, cell_size_units)

# И соответствующие границы в метрах для отображения
x_bins = x_bins_units * SCALE_FACTOR
y_bins = y_bins_units * SCALE_FACTOR

# Создаем 2D гистограмму (heatmap) в исходных единицах, чтобы сохранить детализацию
heatmap, x_edges, y_edges = np.histogram2d(all_x, all_y, bins=[x_bins_units, y_bins_units])

# Конвертируем edges в метры для extent и сетки
x_edges_meters = x_edges * SCALE_FACTOR
y_edges_meters = y_edges * SCALE_FACTOR

# Транспонируем для правильной ориентации
heatmap = heatmap.T

# На основе количества точек считаем суммарное время в каждой ячейке
# В нормализованных траекториях интервал между точками = 2 секунды
TIME_STEP_SECONDS = 2.0
time_heatmap = heatmap.astype(float) * TIME_STEP_SECONDS

# Создаем градиент colormap (от синего к красному)
colors = ['#000080', '#0000FF', '#00FFFF', '#FFFF00', '#FF0000', '#800000']
n_bins = 256
cmap = LinearSegmentedColormap.from_list('trajectory_density', colors, N=n_bins)

# Создаем extent для правильных координат (в метрах)
extent = [x_edges_meters[0], x_edges_meters[-1], y_edges_meters[0], y_edges_meters[-1]]


# Функция для загрузки и отрисовки плана этажа (конвертирует в метры)
def draw_floor_plan(ax, plan_file, scale_factor):
    if plan_file.exists():
        try:
            with open(plan_file, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
            
            for floor in plan_data.get('floors', []):
                if floor.get('number', 0) == 0:
                    for wall in floor.get('walls', []):
                        if len(wall.get('position', [])) >= 2:
                            # Конвертируем координаты в метры
                            x_coords = [pos['x'] * scale_factor for pos in wall['position']]
                            y_coords = [pos['y'] * scale_factor for pos in wall['position']]
                            ax.plot(x_coords, y_coords, 'k-', linewidth=1.5, 
                                   alpha=0.6, zorder=10)
            return True
        except Exception as e:
            print(f"Не удалось загрузить план этажа: {e}")
            return False
    return False


# Функция для отрисовки сетки ячеек heatmap по границам бинов (в метрах)
def draw_cell_grid(ax, x_edges_m, y_edges_m, color='white', alpha=0.15, linewidth=0.5):
    # Вертикальные линии по X
    for x in x_edges_m:
        ax.axvline(x, color=color, alpha=alpha, linewidth=linewidth, zorder=5)
    # Горизонтальные линии по Y
    for y in y_edges_m:
        ax.axhline(y, color=color, alpha=alpha, linewidth=linewidth, zorder=5)

plan_file = Path('bird-dataset-main/data/NMFA_3floors_plan.json')

# ============================================================================
# ВИЗУАЛИЗАЦИЯ 1: Heatmap по времени (time density) с той же сеткой
# ============================================================================
print("\n" + "="*60)
print("Создание визуализации 1: Time Density (суммарное время в ячейке)")
print("="*60)

non_zero_time = time_heatmap[time_heatmap > 0]
if len(non_zero_time) > 0:
    # Возвращаемся к схеме с перцентилями: 5-й и 95-й.
    # Это аналогично тому, как мы делали по плотности точек,
    # но теперь для времени.
    vmin = np.percentile(non_zero_time, 5)   # нижняя граница
    vmax = np.percentile(non_zero_time, 95)  # верхняя граница
    time_to_show = time_heatmap.copy()
    # Обнуляем всё ниже vmin для уменьшения шума
    time_to_show[time_to_show < vmin] = 0
    print(f"Диапазон времени (сек): {non_zero_time.min():.1f} - {non_zero_time.max():.1f}")
    print(f"Отображаемый диапазон (сек): {vmin:.1f} - {vmax:.1f} (5–95 перцентили)")
else:
    vmin = 0
    vmax = 1
    time_to_show = time_heatmap

fig, ax = plt.subplots(figsize=(20, 16))
im = ax.imshow(time_to_show, 
               extent=extent,
               cmap=cmap,
               vmin=vmin,
               vmax=vmax,
               origin='lower',
               interpolation='bilinear',
               alpha=0.8)

draw_floor_plan(ax, plan_file, SCALE_FACTOR)
draw_cell_grid(ax, x_edges_meters, y_edges_meters)

ax.set_xlabel('X координата (м)', fontsize=14)
ax.set_ylabel('Y координата (м)', fontsize=14)
ax.set_title(f'Time Density Heatmap (суммарное время в ячейке)\nВсего точек: {len(all_x):,}, Файлов: {len(csv_files)}', 
             fontsize=16, fontweight='bold')
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--')

cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Суммарное время в ячейке (секунды)', fontsize=12, rotation=270, labelpad=20)

# Добавляем подписи на colorbar в минутах, чтобы было видно ~19 минут
if vmax > 0:
    tick_values = np.linspace(vmin, vmax, 5)
    cbar.set_ticks(tick_values)
    # Показываем метки и в секундах, и в минутах для понятности
    tick_labels = [f"{tv:.0f} с\n({tv/60:.1f} мин)" for tv in tick_values]
    cbar.set_ticklabels(tick_labels)

output_file1 = 'trajectories_time_heatmap.png'
plt.tight_layout()
plt.savefig(output_file1, dpi=300, bbox_inches='tight')
print(f"Heatmap сохранена в {output_file1}")
plt.close()

# ============================================================================
# ВИЗУАЛИЗАЦИЯ 2: Дискретные уровни (7 уровней)
# ============================================================================
print("\n" + "="*60)
print("Создание визуализации 2: Дискретные уровни (7)")
print("="*60)

non_zero_values = heatmap[heatmap > 0]
if len(non_zero_values) > 0:
    heatmap_log = np.log1p(heatmap)
    vmin = 0
    vmax = np.percentile(heatmap_log[heatmap_log > 0], 95)
    heatmap_to_show = heatmap_log
else:
    vmin = 0
    vmax = 1
    heatmap_to_show = heatmap

fig, ax = plt.subplots(figsize=(20, 16))

# Создаем дискретные уровни
levels = np.linspace(vmin, vmax, 8)  # 8 границ = 7 уровней
im = ax.contourf(heatmap_to_show, levels=levels, extent=extent, cmap=cmap, alpha=0.8)

draw_floor_plan(ax, plan_file, SCALE_FACTOR)
draw_cell_grid(ax, x_edges_meters, y_edges_meters)

ax.set_xlabel('X координата (м)', fontsize=14)
ax.set_ylabel('Y координата (м)', fontsize=14)
ax.set_title(f'Дискретные уровни (7 уровней)\nВсего точек: {len(all_x):,}, Файлов: {len(csv_files)}', 
             fontsize=16, fontweight='bold')
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--')

cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Количество точек на ячейку', fontsize=12, rotation=270, labelpad=20)

output_file2 = 'trajectories_heatmap_discrete.png'
plt.tight_layout()
plt.savefig(output_file2, dpi=300, bbox_inches='tight')
print(f"Heatmap сохранена в {output_file2}")
plt.close()

# ============================================================================
# ВИЗУАЛИЗАЦИЯ 3: Комбинированный подход
# ============================================================================
print("\n" + "="*60)
print("Создание визуализации 3: Комбинированный подход")
print("="*60)

non_zero_values = heatmap[heatmap > 0]
if len(non_zero_values) > 0:
    # Комбинированный подход: пороговая фильтрация + агрессивная нормализация
    threshold_percentile = 85
    
    threshold = np.percentile(non_zero_values, threshold_percentile)
    heatmap_filtered = heatmap.copy()
    heatmap_filtered[heatmap_filtered < threshold] = 0
    
    # Используем исходные значения (без логарифма) для более понятной интерпретации
    # Используем перцентили отфильтрованных значений для масштабирования
    filtered_values = heatmap_filtered[heatmap_filtered > 0]
    if len(filtered_values) > 0:
        vmin = np.percentile(filtered_values, 10)  # 10-й перцентиль
        vmax = np.percentile(filtered_values, 90)  # 90-й перцентиль
    else:
        vmin = 0
        vmax = 1
    
    heatmap_to_show = heatmap_filtered
    
    print(f"Порог фильтрации: {threshold:.1f} точек (перцентиль {threshold_percentile}%)")
    print(f"Диапазон отфильтрованных значений: {vmin:.1f} - {vmax:.1f} точек на ячейку")
    print(f"Показывается {np.sum(heatmap_filtered > 0)} из {len(non_zero_values)} ячеек")
else:
    vmin = 0
    vmax = 1
    heatmap_to_show = heatmap

fig, ax = plt.subplots(figsize=(20, 16))
im = ax.imshow(heatmap_to_show, 
               extent=extent,
               cmap=cmap,
               vmin=vmin,
               vmax=vmax,
               origin='lower',
               interpolation='bilinear',
               alpha=0.8)

draw_floor_plan(ax, plan_file, SCALE_FACTOR)
draw_cell_grid(ax, x_edges_meters, y_edges_meters)

ax.set_xlabel('X координата (м)', fontsize=14)
ax.set_ylabel('Y координата (м)', fontsize=14)
ax.set_title(f'Комбинированный подход (порог 85%, масштаб 10-90%)\nВсего точек: {len(all_x):,}, Файлов: {len(csv_files)}', 
             fontsize=16, fontweight='bold')
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--')

cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Количество точек на ячейку', fontsize=12, rotation=270, labelpad=20)

output_file3 = 'trajectories_heatmap_combined.png'
plt.tight_layout()
plt.savefig(output_file3, dpi=300, bbox_inches='tight')
print(f"Heatmap сохранена в {output_file3}")
plt.close()

print("\n" + "="*60)
print("Все три визуализации созданы!")
print("="*60)
print(f"1. Пороговая фильтрация: {output_file1}")
print(f"2. Дискретные уровни: {output_file2}")
print(f"3. Комбинированный подход: {output_file3}")
print(f"\nРазмер сетки: {len(x_bins_units)-1} x {len(y_bins_units)-1} ячеек")
print(f"Размер ячейки: {cell_size_units} единиц координат ({cell_size_meters:.2f} м)")

# Дополнительно: создаем heatmap с использованием KDE (более плавная)
if HAS_SCIPY:
    print("\nСоздание KDE heatmap (более плавная)...")
    
    # Создаем сетку для KDE (в метрах)
    x_grid = np.linspace(min_x, max_x, 200)
    y_grid = np.linspace(min_y, max_y, 200)
    X_grid, Y_grid = np.meshgrid(x_grid, y_grid)
    
    # Вычисляем KDE (используем координаты в метрах)
    try:
        positions = np.vstack([X_grid.ravel(), Y_grid.ravel()])
        values = np.vstack([all_x_meters, all_y_meters])
        kde = gaussian_kde(values)
        Z = np.reshape(kde(positions).T, X_grid.shape)
        
        # Создаем фигуру для KDE
        fig2, ax2 = plt.subplots(figsize=(20, 16))
        
        # Отображаем KDE heatmap (используем сетку в метрах для отображения)
        im2 = ax2.contourf(X_grid, Y_grid, Z, levels=50, cmap=cmap, alpha=0.8)
        
        # Пытаемся загрузить план этажа
        draw_floor_plan(ax2, plan_file, SCALE_FACTOR)
        
        ax2.set_xlabel('X координата (м)', fontsize=14)
        ax2.set_ylabel('Y координата (м)', fontsize=14)
        ax2.set_title(f'KDE Heatmap всех траекторий\n(Плавная интерполяция плотности)', 
                     fontsize=16, fontweight='bold')
        ax2.set_aspect('equal')
        ax2.grid(True, alpha=0.3, linestyle='--')
        
        cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
        cbar2.set_label('Плотность (KDE)', fontsize=12, rotation=270, labelpad=20)
        
        output_file_kde = 'trajectories_heatmap_kde.png'
        plt.tight_layout()
        plt.savefig(output_file_kde, dpi=300, bbox_inches='tight')
        print(f"KDE Heatmap сохранена в {output_file_kde}")
        plt.close()
        
    except Exception as e:
        print(f"Не удалось создать KDE heatmap: {e}")
else:
    print("\nKDE heatmap пропущена (scipy не установлен)")

print("\nГотово!")
