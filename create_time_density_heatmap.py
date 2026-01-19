import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.cm as cm

# Загрузка плана этажа
plan_file = 'bird-dataset-main/data/NMFA_3floors_plan.json'
with open(plan_file, 'r', encoding='utf-8') as f:
    plan_data = json.load(f)

# Находим этаж 0
floor_0 = None
for floor in plan_data['floors']:
    if floor['number'] == 0:
        floor_0 = floor
        break

if floor_0 is None:
    raise ValueError("Этаж 0 не найден в плане")

# Определяем границы этажа из координат стен
all_x = []
all_y = []

for wall in floor_0['walls']:
    for pos in wall['position']:
        all_x.append(pos['x'])
        all_y.append(pos['y'])

min_x = min(all_x)
max_x = max(all_x)
min_y = min(all_y)
max_y = max(all_y)

# Загружаем данные time_density
time_density_df = pd.read_csv('time_density_floor0.csv')

# Параметры сетки
cell_size = 1.0
x_cells = int(np.ceil((max_x - min_x) / cell_size))
y_cells = int(np.ceil((max_y - min_y) / cell_size))

# Создаем матрицу для heatmap
heatmap_matrix = np.zeros((y_cells, x_cells))

# Функция для определения индексов ячейки
def get_cell_indices(x, y):
    cell_x = int(np.floor((x - min_x) / cell_size))
    cell_y = int(np.floor((y - min_y) / cell_size))
    cell_x = max(0, min(cell_x, x_cells - 1))
    cell_y = max(0, min(cell_y, y_cells - 1))
    return cell_x, cell_y

# Заполняем матрицу значениями time_density
for _, row in time_density_df.iterrows():
    cell_number = int(row['cell_number'])
    time_density = row['time_density']
    
    # Преобразуем номер ячейки обратно в индексы
    cell_y = int(cell_number // x_cells)
    cell_x = int(cell_number % x_cells)
    
    if 0 <= cell_y < y_cells and 0 <= cell_x < x_cells:
        heatmap_matrix[cell_y, cell_x] = time_density

# Создаем фигуру
fig, ax = plt.subplots(figsize=(20, 16))

# Создаем градиент от синего к красному
# Используем colormap 'coolwarm' или создаем свой
colors = ['#0000FF', '#FFFFFF', '#FF0000']  # Синий -> Белый -> Красный
n_bins = 256
cmap = LinearSegmentedColormap.from_list('blue_red', colors, N=n_bins)

# Находим min и max для нормализации (исключая нули)
non_zero_values = heatmap_matrix[heatmap_matrix > 0]
if len(non_zero_values) > 0:
    vmin = non_zero_values.min()
    vmax = non_zero_values.max()
else:
    vmin = 0
    vmax = 1

# Создаем heatmap
# Используем extent для правильных координат
extent = [min_x, max_x, min_y, max_y]
im = ax.imshow(heatmap_matrix, 
               extent=extent,
               cmap=cmap,
               vmin=vmin,
               vmax=vmax,
               origin='lower',
               interpolation='nearest',
               alpha=0.7)

# Рисуем стены плана
for wall in floor_0['walls']:
    if len(wall['position']) >= 2:
        x_coords = [pos['x'] for pos in wall['position']]
        y_coords = [pos['y'] for pos in wall['position']]
        ax.plot(x_coords, y_coords, 'k-', linewidth=2, alpha=0.8, zorder=10)

# Настройка осей
ax.set_xlabel('X координата (м)', fontsize=14)
ax.set_ylabel('Y координата (м)', fontsize=14)
ax.set_title('Time Density Heatmap - Этаж 0\n(Синий = минимум, Красный = максимум)', 
             fontsize=16, fontweight='bold')
ax.set_aspect('equal')

# Добавляем colorbar
cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Time Density (секунды)', fontsize=12, rotation=270, labelpad=20)

# Инвертируем Y-ось для правильной ориентации (если нужно)
ax.invert_yaxis()

# Сохраняем изображение
output_file = 'time_density_heatmap_floor0.png'
plt.tight_layout()
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Heatmap сохранена в {output_file}")
print(f"Размер изображения: {x_cells} x {y_cells} ячеек")
print(f"Диапазон значений: {vmin:.2f} - {vmax:.2f} секунд")

plt.close()
