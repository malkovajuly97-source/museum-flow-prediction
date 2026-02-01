"""
Этап 4: Пространственный анализ типов поведения (только этаж 0)

Этот скрипт:
1. Загружает траектории с координатами и типами поведения
2. Анализирует пространственное распределение каждого типа
3. Создает heatmaps плотности для каждого типа
4. Выявляет предпочитаемые зоны для каждого типа
5. Сравнивает использование пространства между типами
6. Сохраняет результаты в папку analysis_results_merged
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pathlib import Path
from scipy.ndimage import gaussian_filter
import warnings
warnings.filterwarnings('ignore')

# Пути к данным
INPUT_DIR = Path("analysis_results")
MERGED_DIR = Path("analysis_results_merged")
OUTPUT_DIR = Path("analysis_results_merged")
OUTPUT_DIR.mkdir(exist_ok=True)

# Файлы
TRAJECTORIES_WITH_FEATURES = INPUT_DIR / "floor0_trajectories_with_features.csv"
CLUSTERED_MERGED = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"


def load_spatial_data():
    """Загружает траектории с координатами и типами поведения."""
    print("=" * 70)
    print("ЗАГРУЗКА ДАННЫХ ДЛЯ ПРОСТРАНСТВЕННОГО АНАЛИЗА")
    print("=" * 70)
    
    # Загружаем траектории с координатами
    print("\n[1] Загрузка траекторий с координатами...")
    df_traj = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_traj['trajectory_id'] = df_traj['trajectory_id'].astype(str)
    
    print(f"  Загружено точек траекторий: {len(df_traj)}")
    print(f"  Уникальных траекторий: {df_traj['trajectory_id'].nunique()}")
    print(f"  Диапазон X: {df_traj['x'].min():.2f} - {df_traj['x'].max():.2f}")
    print(f"  Диапазон Y: {df_traj['y'].min():.2f} - {df_traj['y'].max():.2f}")
    
    # Загружаем типы поведения
    print("\n[2] Загрузка типов поведения...")
    df_clustered = pd.read_csv(CLUSTERED_MERGED)
    df_clustered['trajectory_id'] = df_clustered['trajectory_id'].astype(str)
    
    # Оставляем только нужные колонки
    behavior_types = df_clustered[['trajectory_id', 'behavior_type']].copy()
    
    print(f"  Загружено траекторий с типами: {len(behavior_types)}")
    print(f"  Типы поведения:")
    for bt, count in behavior_types['behavior_type'].value_counts().items():
        print(f"    {bt}: {count} траекторий")
    
    # Объединяем данные
    print("\n[3] Объединение данных...")
    df_spatial = df_traj.merge(behavior_types, on='trajectory_id', how='inner')
    
    print(f"  После объединения: {len(df_spatial)} точек")
    print(f"  Уникальных траекторий: {df_spatial['trajectory_id'].nunique()}")
    
    return df_spatial


def compute_heatmaps_by_type(df_spatial, grid_size=100):
    """
    Вычисляет heatmaps плотности для каждого типа поведения.
    
    Args:
        df_spatial: DataFrame с координатами и типами поведения
        grid_size: размер сетки для heatmap
    
    Returns:
        dict: словарь с heatmaps для каждого типа
    """
    print("\n" + "=" * 70)
    print("ВЫЧИСЛЕНИЕ HEATMAPS ПО ТИПАМ ПОВЕДЕНИЯ")
    print("=" * 70)
    
    # Определяем границы пространства
    x_min, x_max = df_spatial['x'].min(), df_spatial['x'].max()
    y_min, y_max = df_spatial['y'].min(), df_spatial['y'].max()
    
    print(f"\nГраницы пространства:")
    print(f"  X: [{x_min:.2f}, {x_max:.2f}]")
    print(f"  Y: [{y_min:.2f}, {y_max:.2f}]")
    
    # Создаем сетку
    x_bins = np.linspace(x_min, x_max, grid_size)
    y_bins = np.linspace(y_min, y_max, grid_size)
    
    heatmaps = {}
    behavior_types = sorted(df_spatial['behavior_type'].unique())
    
    for behavior_type in behavior_types:
        print(f"\nОбработка типа: {behavior_type}")
        
        # Фильтруем данные для этого типа
        type_data = df_spatial[df_spatial['behavior_type'] == behavior_type]
        
        print(f"  Точек: {len(type_data)}")
        print(f"  Траекторий: {type_data['trajectory_id'].nunique()}")
        
        # Вычисляем 2D гистограмму
        heatmap, x_edges, y_edges = np.histogram2d(
            type_data['x'].values,
            type_data['y'].values,
            bins=[x_bins, y_bins]
        )
        
        # Транспонируем для правильной ориентации
        heatmap = heatmap.T
        
        # Применяем сглаживание
        heatmap_smooth = gaussian_filter(heatmap, sigma=1.5)
        
        heatmaps[behavior_type] = {
            'heatmap': heatmap_smooth,
            'x_edges': x_edges,
            'y_edges': y_edges,
            'n_points': len(type_data),
            'n_trajectories': type_data['trajectory_id'].nunique()
        }
        
        print(f"  Максимальная плотность: {heatmap_smooth.max():.2f}")
        print(f"  Средняя плотность: {heatmap_smooth.mean():.2f}")
    
    return heatmaps, x_min, x_max, y_min, y_max


def visualize_heatmaps(heatmaps, x_min, x_max, y_min, y_max):
    """Создает визуализации heatmaps для каждого типа."""
    print("\n" + "=" * 70)
    print("СОЗДАНИЕ ВИЗУАЛИЗАЦИЙ HEATMAPS")
    print("=" * 70)
    
    behavior_types = sorted(heatmaps.keys())
    n_types = len(behavior_types)
    
    # 1. Отдельные heatmaps для каждого типа
    print("\n[1] Создание отдельных heatmaps...")
    n_cols = 2
    n_rows = (n_types + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 8*n_rows))
    axes = axes.flatten() if n_types > 1 else [axes]
    
    for idx, behavior_type in enumerate(behavior_types):
        ax = axes[idx]
        data = heatmaps[behavior_type]
        
        # Создаем meshgrid для координат
        x_centers = (data['x_edges'][:-1] + data['x_edges'][1:]) / 2
        y_centers = (data['y_edges'][:-1] + data['y_edges'][1:]) / 2
        X, Y = np.meshgrid(x_centers, y_centers)
        
        # Визуализация
        im = ax.contourf(X, Y, data['heatmap'], levels=20, cmap='hot', alpha=0.8)
        ax.set_xlabel('X координата', fontsize=11)
        ax.set_ylabel('Y координата', fontsize=11)
        ax.set_title(f'{behavior_type}\n({data["n_trajectories"]} траекторий, {data["n_points"]} точек)', 
                     fontsize=12, fontweight='bold')
        ax.set_aspect('equal')
        plt.colorbar(im, ax=ax, label='Плотность')
        ax.grid(True, alpha=0.3)
    
    # Скрываем лишние subplots
    for idx in range(n_types, len(axes)):
        axes[idx].set_visible(False)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "spatial_heatmaps_by_type.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Отдельные heatmaps сохранены в: {output_file}")
    
    # 2. Сравнительная визуализация (все типы на одном графике)
    print("\n[2] Создание сравнительной визуализации...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 16))
    axes = axes.flatten()
    
    colors = ['Reds', 'Blues', 'Greens', 'Oranges']
    
    for idx, behavior_type in enumerate(behavior_types):
        if idx >= len(axes):
            break
            
        ax = axes[idx]
        data = heatmaps[behavior_type]
        
        x_centers = (data['x_edges'][:-1] + data['x_edges'][1:]) / 2
        y_centers = (data['y_edges'][:-1] + data['y_edges'][1:]) / 2
        X, Y = np.meshgrid(x_centers, y_centers)
        
        im = ax.contourf(X, Y, data['heatmap'], levels=20, cmap=colors[idx % len(colors)], alpha=0.8)
        ax.set_xlabel('X координата', fontsize=11)
        ax.set_ylabel('Y координата', fontsize=11)
        ax.set_title(f'{behavior_type}', fontsize=12, fontweight='bold')
        ax.set_aspect('equal')
        plt.colorbar(im, ax=ax, label='Плотность')
        ax.grid(True, alpha=0.3)
    
    # Скрываем лишние subplots
    for idx in range(len(behavior_types), len(axes)):
        axes[idx].set_visible(False)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "spatial_heatmaps_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Сравнительная визуализация сохранена в: {output_file}")


def analyze_spatial_preferences(df_spatial):
    """Анализирует пространственные предпочтения каждого типа."""
    print("\n" + "=" * 70)
    print("АНАЛИЗ ПРОСТРАНСТВЕННЫХ ПРЕДПОЧТЕНИЙ")
    print("=" * 70)
    
    # Разделяем пространство на квадранты
    x_median = df_spatial['x'].median()
    y_median = df_spatial['y'].median()
    
    print(f"\nЦентр пространства: X={x_median:.2f}, Y={y_median:.2f}")
    
    # Определяем квадранты
    df_spatial['quadrant'] = 'center'
    df_spatial.loc[(df_spatial['x'] < x_median) & (df_spatial['y'] < y_median), 'quadrant'] = 'SW'
    df_spatial.loc[(df_spatial['x'] >= x_median) & (df_spatial['y'] < y_median), 'quadrant'] = 'SE'
    df_spatial.loc[(df_spatial['x'] < x_median) & (df_spatial['y'] >= y_median), 'quadrant'] = 'NW'
    df_spatial.loc[(df_spatial['x'] >= x_median) & (df_spatial['y'] >= y_median), 'quadrant'] = 'NE'
    
    # Анализ по типам
    spatial_stats = []
    
    for behavior_type in sorted(df_spatial['behavior_type'].unique()):
        type_data = df_spatial[df_spatial['behavior_type'] == behavior_type]
        
        stats = {
            'behavior_type': behavior_type,
            'n_trajectories': type_data['trajectory_id'].nunique(),
            'n_points': len(type_data),
            'avg_x': type_data['x'].mean(),
            'avg_y': type_data['y'].mean(),
            'std_x': type_data['x'].std(),
            'std_y': type_data['y'].std(),
            'x_range': type_data['x'].max() - type_data['x'].min(),
            'y_range': type_data['y'].max() - type_data['y'].min(),
        }
        
        # Распределение по квадрантам
        quadrant_dist = type_data['quadrant'].value_counts(normalize=True) * 100
        for quad in ['SW', 'SE', 'NW', 'NE']:
            stats[f'quadrant_{quad}_pct'] = quadrant_dist.get(quad, 0)
        
        spatial_stats.append(stats)
        
        print(f"\n{behavior_type}:")
        print(f"  Центр активности: X={stats['avg_x']:.2f}, Y={stats['avg_y']:.2f}")
        print(f"  Разброс: X±{stats['std_x']:.2f}, Y±{stats['std_y']:.2f}")
        print(f"  Охват пространства: X={stats['x_range']:.2f}, Y={stats['y_range']:.2f}")
        print(f"  Распределение по квадрантам:")
        for quad in ['SW', 'SE', 'NW', 'NE']:
            pct = stats[f'quadrant_{quad}_pct']
            print(f"    {quad}: {pct:.1f}%")
    
    df_spatial_stats = pd.DataFrame(spatial_stats)
    
    # Сохраняем
    output_file = OUTPUT_DIR / "spatial_preferences_by_type.csv"
    df_spatial_stats.to_csv(output_file, index=False)
    print(f"\nСтатистика пространственных предпочтений сохранена в: {output_file}")
    
    return df_spatial_stats


def create_trajectory_visualizations(df_spatial):
    """Создает визуализации траекторий по типам."""
    print("\n" + "=" * 70)
    print("СОЗДАНИЕ ВИЗУАЛИЗАЦИЙ ТРАЕКТОРИЙ")
    print("=" * 70)
    
    behavior_types = sorted(df_spatial['behavior_type'].unique())
    n_types = len(behavior_types)
    
    # Создаем фигуру с subplots
    n_cols = 2
    n_rows = (n_types + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 8*n_rows))
    axes = axes.flatten() if n_types > 1 else [axes]
    
    colors = plt.cm.Set3(np.linspace(0, 1, n_types))
    
    for idx, behavior_type in enumerate(behavior_types):
        ax = axes[idx]
        type_data = df_spatial[df_spatial['behavior_type'] == behavior_type]
        
        # Рисуем траектории
        for traj_id in type_data['trajectory_id'].unique():
            traj = type_data[type_data['trajectory_id'] == traj_id]
            ax.plot(traj['x'].values, traj['y'].values, 
                   color=colors[idx], alpha=0.3, linewidth=0.5)
        
        ax.set_xlabel('X координата', fontsize=11)
        ax.set_ylabel('Y координата', fontsize=11)
        ax.set_title(f'{behavior_type}\n({type_data["trajectory_id"].nunique()} траекторий)', 
                     fontsize=12, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
    
    # Скрываем лишние subplots
    for idx in range(n_types, len(axes)):
        axes[idx].set_visible(False)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "trajectories_by_behavior_type.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Визуализация траекторий сохранена в: {output_file}")


def main():
    """Основная функция для пространственного анализа."""
    print("=" * 70)
    print("ЭТАП 4: ПРОСТРАНСТВЕННЫЙ АНАЛИЗ ТИПОВ ПОВЕДЕНИЯ")
    print("=" * 70)
    
    # Загружаем данные
    df_spatial = load_spatial_data()
    
    # Вычисляем heatmaps
    heatmaps, x_min, x_max, y_min, y_max = compute_heatmaps_by_type(df_spatial, grid_size=100)
    
    # Визуализируем heatmaps
    visualize_heatmaps(heatmaps, x_min, x_max, y_min, y_max)
    
    # Анализируем пространственные предпочтения
    df_spatial_stats = analyze_spatial_preferences(df_spatial)
    
    # Создаем визуализации траекторий
    create_trajectory_visualizations(df_spatial)
    
    # Итоговая информация
    print("\n" + "=" * 70)
    print("ПРОСТРАНСТВЕННЫЙ АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 70)
    print(f"\nВсе файлы сохранены в папку: {OUTPUT_DIR}/")
    print("\nСозданные файлы:")
    print("  - spatial_heatmaps_by_type.png")
    print("  - spatial_heatmaps_comparison.png")
    print("  - spatial_preferences_by_type.csv")
    print("  - trajectories_by_behavior_type.png")
    
    return df_spatial, heatmaps, df_spatial_stats


if __name__ == "__main__":
    df_spatial, heatmaps, df_spatial_stats = main()
