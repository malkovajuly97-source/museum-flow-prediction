import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Чтение данных из CSV
file_path = 'bird-dataset-main/data/normalized_trajectories/201902181020_traj_normalized.csv'
df = pd.read_csv(file_path)

# Создание фигуры с подграфиками для каждого этажа
floors = sorted(df['floorNumber'].unique())
n_floors = len(floors)

fig, axes = plt.subplots(1, n_floors, figsize=(15, 5))
if n_floors == 1:
    axes = [axes]

for idx, floor in enumerate(floors):
    ax = axes[idx]
    
    # Фильтрация данных по этажу
    floor_data = df[df['floorNumber'] == floor]
    
    # Построение траектории
    ax.plot(floor_data['x'], floor_data['y'], 'b-', linewidth=1.5, alpha=0.7, label='Траектория')
    
    # Отметка начальной точки
    ax.plot(floor_data['x'].iloc[0], floor_data['y'].iloc[0], 'go', 
            markersize=10, label='Начало', zorder=5)
    
    # Отметка конечной точки
    ax.plot(floor_data['x'].iloc[-1], floor_data['y'].iloc[-1], 'ro', 
            markersize=10, label='Конец', zorder=5)
    
    # Настройка осей
    ax.set_xlabel('X координата', fontsize=12)
    ax.set_ylabel('Y координата', fontsize=12)
    ax.set_title(f'Этаж {floor}', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.invert_yaxis()  # Инвертируем Y-ось для правильной ориентации
    
    # Добавление стрелок для показа направления движения
    # Показываем каждую 50-ю точку для читаемости
    step = max(1, len(floor_data) // 20)
    for i in range(0, len(floor_data) - 1, step):
        dx = floor_data['x'].iloc[i+1] - floor_data['x'].iloc[i]
        dy = floor_data['y'].iloc[i+1] - floor_data['y'].iloc[i]
        if abs(dx) > 0.1 or abs(dy) > 0.1:  # Показываем только если есть движение
            ax.arrow(floor_data['x'].iloc[i], floor_data['y'].iloc[i], 
                    dx*0.3, dy*0.3, head_width=50, head_length=50, 
                    fc='red', ec='red', alpha=0.3, length_includes_head=True)

plt.tight_layout()
plt.suptitle('Визуализация траектории посетителя 201902181020', 
             fontsize=16, fontweight='bold', y=1.02)
plt.savefig('trajectory_visualization.png', dpi=300, bbox_inches='tight')
print("\nГрафик сохранен в файл: trajectory_visualization.png")
plt.show()

# Дополнительная информация
print(f"\nИнформация о траектории:")
print(f"Общее количество точек: {len(df)}")
print(f"Длительность: {df['timestamp'].max() - df['timestamp'].min():.2f} секунд")
print(f"Этажи: {sorted(df['floorNumber'].unique())}")
print(f"\nСтатистика по координатам:")
print(f"X: мин={df['x'].min():.2f}, макс={df['x'].max():.2f}, среднее={df['x'].mean():.2f}")
print(f"Y: мин={df['y'].min():.2f}, макс={df['y'].max():.2f}, среднее={df['y'].mean():.2f}")
