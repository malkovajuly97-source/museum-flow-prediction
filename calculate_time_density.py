import pandas as pd
import numpy as np
import json
import glob
import os
from pathlib import Path

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

print(f"Границы этажа 0:")
print(f"X: [{min_x:.2f}, {max_x:.2f}]")
print(f"Y: [{min_y:.2f}, {max_y:.2f}]")
print(f"Размер: {max_x - min_x:.2f} x {max_y - min_y:.2f} м")

# Загружаем все траектории для этажа 0
trajectories_folder = 'bird-dataset-main/data/normalized_trajectories/'
csv_files = glob.glob(os.path.join(trajectories_folder, '*.csv'))

print(f"\nЗагрузка траекторий...")
all_trajectories_floor0 = []

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        # Фильтруем только этаж 0
        df_floor0 = df[df['floorNumber'] == 0].copy()
        if len(df_floor0) > 0:
            trajectory_id = Path(csv_file).stem.replace('_traj_normalized', '')
            df_floor0['trajectory_id'] = trajectory_id
            all_trajectories_floor0.append(df_floor0)
    except Exception as e:
        print(f"Ошибка при загрузке {csv_file}: {e}")

if not all_trajectories_floor0:
    raise ValueError("Не найдено траекторий для этажа 0")

# Объединяем все траектории
combined_df = pd.concat(all_trajectories_floor0, ignore_index=True)
print(f"Загружено {len(all_trajectories_floor0)} траекторий")
print(f"Всего точек на этаже 0: {len(combined_df)}")

# Разбиваем на сетку 1x1 м
# Определяем количество ячеек
cell_size = 1.0  # 1 метр
x_cells = int(np.ceil((max_x - min_x) / cell_size))
y_cells = int(np.ceil((max_y - min_y) / cell_size))

print(f"\nСетка: {x_cells} x {y_cells} ячеек (размер ячейки: {cell_size} м)")

# Функция для определения номера ячейки
def get_cell_number(x, y):
    """Возвращает номер ячейки для координат (x, y)"""
    # Определяем индексы ячейки
    cell_x = int(np.floor((x - min_x) / cell_size))
    cell_y = int(np.floor((y - min_y) / cell_size))
    
    # Ограничиваем индексы границами сетки
    cell_x = max(0, min(cell_x, x_cells - 1))
    cell_y = max(0, min(cell_y, y_cells - 1))
    
    # Номер ячейки: cell_y * x_cells + cell_x (нумерация слева направо, сверху вниз)
    cell_number = cell_y * x_cells + cell_x
    return cell_number

# Добавляем номер ячейки для каждой точки
combined_df['cell_number'] = combined_df.apply(
    lambda row: get_cell_number(row['x'], row['y']), axis=1
)

# В нормализованных траекториях интервал между точками = 2 секунды
time_interval = 2.0  # секунды

# Группируем по ячейкам и считаем time density
# Time density = суммарное время всех агентов в ячейке
# = количество точек в ячейке * интервал времени
cell_time_density = combined_df.groupby('cell_number').size() * time_interval

# Создаем таблицу результатов
results = pd.DataFrame({
    'cell_number': cell_time_density.index,
    'time_density': cell_time_density.values
})

# Сортируем по номеру ячейки
results = results.sort_values('cell_number').reset_index(drop=True)

# Сохраняем в CSV
output_file = 'time_density_floor0.csv'
results.to_csv(output_file, index=False)

print(f"\nРезультаты сохранены в {output_file}")
print(f"\nСтатистика:")
print(f"Всего ячеек с данными: {len(results)}")
print(f"Максимальная time_density: {results['time_density'].max():.2f} секунд")
print(f"Минимальная time_density: {results['time_density'].min():.2f} секунд")
print(f"Средняя time_density: {results['time_density'].mean():.2f} секунд")
print(f"Суммарная time_density: {results['time_density'].sum():.2f} секунд")

print(f"\nПервые 20 строк таблицы:")
print(results.head(20).to_string(index=False))
