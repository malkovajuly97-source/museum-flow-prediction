"""
Анализ результатов кластеризации типов поведения

Этот скрипт:
1. Загружает результаты кластеризации
2. Анализирует характеристики каждого типа поведения
3. Сравнивает типы между собой
4. Создает детальные визуализации
5. Генерирует отчет с выводами
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Опциональный импорт seaborn
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    print("Внимание: seaborn не установлен, будет использован matplotlib для визуализации")

# Пути к данным
INPUT_DIR = Path("analysis_results")
OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

# Файлы
CLUSTERED_FILE = INPUT_DIR / "floor0_trajectories_clustered.csv"
CLUSTER_STATS_FILE = INPUT_DIR / "cluster_statistics.csv"
SUMMARY_FILE = INPUT_DIR / "behavior_types_summary.csv"


def load_clustering_results():
    """Загружает результаты кластеризации."""
    df_clustered = pd.read_csv(CLUSTERED_FILE)
    df_stats = pd.read_csv(CLUSTER_STATS_FILE)
    df_summary = pd.read_csv(SUMMARY_FILE)
    
    # Преобразуем trajectory_id в строку
    df_clustered['trajectory_id'] = df_clustered['trajectory_id'].astype(str)
    
    print(f"Загружено данных:")
    print(f"  Траекторий с метками: {len(df_clustered)}")
    print(f"  Уникальных траекторий: {df_clustered['trajectory_id'].nunique()}")
    print(f"  Типов поведения: {df_clustered['behavior_type'].nunique()}")
    
    return df_clustered, df_stats, df_summary


def analyze_cluster_characteristics(df_clustered, df_stats):
    """
    Анализирует характеристики каждого кластера.
    
    Returns:
        pd.DataFrame: Детальная характеристика каждого типа
    """
    print("\n" + "=" * 60)
    print("АНАЛИЗ ХАРАКТЕРИСТИК ТИПОВ ПОВЕДЕНИЯ")
    print("=" * 60)
    
    # Ключевые признаки для анализа
    key_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length', 
                    'curvature', 'stop_intensity', 'item_time_density', 
                    'avg_observation_time', 'path_efficiency']
    
    # Фильтруем только существующие признаки
    available_features = [f for f in key_features if f in df_clustered.columns]
    
    # Группируем по типам поведения
    cluster_analysis = []
    
    for behavior_type in sorted(df_clustered['behavior_type'].unique()):
        cluster_data = df_clustered[df_clustered['behavior_type'] == behavior_type]
        
        analysis = {
            'behavior_type': behavior_type,
            'n_trajectories': len(cluster_data),
            'percentage': len(cluster_data) / len(df_clustered) * 100
        }
        
        # Статистика по каждому признаку
        for feature in available_features:
            values = cluster_data[feature].dropna()
            if len(values) > 0:
                analysis[f'{feature}_mean'] = values.mean()
                analysis[f'{feature}_median'] = values.median()
                analysis[f'{feature}_std'] = values.std()
                analysis[f'{feature}_min'] = values.min()
                analysis[f'{feature}_max'] = values.max()
        
        cluster_analysis.append(analysis)
    
    df_analysis = pd.DataFrame(cluster_analysis)
    
    # Выводим основные характеристики
    print("\nОсновные характеристики типов поведения:")
    print("-" * 60)
    
    for _, row in df_analysis.iterrows():
        behavior_type = row['behavior_type']
        cluster_data_for_type = df_clustered[df_clustered['behavior_type'] == behavior_type]
        
        print(f"\n{behavior_type} ({row['n_trajectories']} траекторий, {row['percentage']:.1f}%):")
        print(f"  Скорость: {row.get('speed_mean', 0):.2f} (медиана: {row.get('speed_median', 0):.2f})")
        print(f"  Длительность: {row.get('duration_mean', 0):.0f} сек ({row.get('duration_mean', 0)/60:.1f} мин)")
        print(f"  Остановки: {row.get('nb_stops_mean', 0):.1f} (медиана: {cluster_data_for_type['nb_stops'].median():.0f})")
        print(f"  Экспонаты: {row.get('nb_items_mean', 0):.1f} (медиана: {cluster_data_for_type['nb_items'].median():.0f})")
        print(f"  Длина пути: {row.get('length_mean', 0):.0f} единиц")
        if 'avg_observation_time' in available_features:
            obs_time = row.get('avg_observation_time_mean', np.nan)
            if not np.isnan(obs_time):
                print(f"  Среднее время просмотра: {obs_time:.2f} сек")
    
    return df_analysis


def compare_clusters(df_clustered, df_stats):
    """
    Сравнивает кластеры между собой.
    """
    print("\n" + "=" * 60)
    print("СРАВНИТЕЛЬНЫЙ АНАЛИЗ ТИПОВ ПОВЕДЕНИЯ")
    print("=" * 60)
    
    # Вычисляем средние значения по всем траекториям для сравнения
    overall_means = df_clustered[['speed', 'duration', 'nb_stops', 'nb_items', 'length']].mean()
    
    print("\nСредние значения по всем траекториям:")
    print(f"  Скорость: {overall_means['speed']:.2f}")
    print(f"  Длительность: {overall_means['duration']:.0f} сек")
    print(f"  Остановки: {overall_means['nb_stops']:.1f}")
    print(f"  Экспонаты: {overall_means['nb_items']:.1f}")
    print(f"  Длина пути: {overall_means['length']:.0f}")
    
    print("\nОтклонения от среднего по типам:")
    print("-" * 60)
    
    for behavior_type in sorted(df_clustered['behavior_type'].unique()):
        cluster_data = df_clustered[df_clustered['behavior_type'] == behavior_type]
        cluster_means = cluster_data[['speed', 'duration', 'nb_stops', 'nb_items', 'length']].mean()
        
        print(f"\n{behavior_type}:")
        for feature in ['speed', 'duration', 'nb_stops', 'nb_items', 'length']:
            diff = cluster_means[feature] - overall_means[feature]
            diff_pct = (diff / overall_means[feature]) * 100
            symbol = "+" if diff > 0 else ""
            print(f"  {feature}: {symbol}{diff_pct:+.1f}% ({symbol}{diff:.2f})")


def create_detailed_visualizations(df_clustered, df_stats):
    """
    Создает детальные визуализации для анализа кластеров.
    """
    print("\nСоздание детальных визуализаций...")
    
    # 1. Радарная диаграмма характеристик (spider chart)
    key_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length']
    key_features = [f for f in key_features if f in df_clustered.columns]
    
    # Нормализуем значения для радарной диаграммы (0-1)
    fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(projection='polar'))
    
    # Углы для каждого признака
    angles = np.linspace(0, 2 * np.pi, len(key_features), endpoint=False).tolist()
    angles += angles[:1]  # Замыкаем круг
    
    # Цвета для каждого типа
    behavior_types = sorted(df_clustered['behavior_type'].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(behavior_types)))
    
    for idx, behavior_type in enumerate(behavior_types):
        cluster_data = df_clustered[df_clustered['behavior_type'] == behavior_type]
        
        # Средние значения
        values = []
        for feature in key_features:
            mean_val = cluster_data[feature].mean()
            # Нормализуем к [0, 1] относительно всех данных
            min_val = df_clustered[feature].min()
            max_val = df_clustered[feature].max()
            if max_val > min_val:
                normalized = (mean_val - min_val) / (max_val - min_val)
            else:
                normalized = 0.5
            values.append(normalized)
        
        values += values[:1]  # Замыкаем круг
        
        ax.plot(angles, values, 'o-', linewidth=2, label=behavior_type, color=colors[idx])
        ax.fill(angles, values, alpha=0.25, color=colors[idx])
    
    # Настройка осей
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(key_features, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=8)
    ax.grid(True)
    
    plt.title('Сравнение типов поведения (радарная диаграмма)', 
              fontsize=14, fontweight='bold', pad=20)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "behavior_types_radar_chart.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Радарная диаграмма сохранена в: {output_file}")
    
    # 2. Сравнительная таблица с heatmap
    comparison_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length', 
                          'stop_intensity', 'item_time_density']
    comparison_features = [f for f in comparison_features if f in df_clustered.columns]
    
    # Создаем матрицу сравнения
    comparison_data = []
    for behavior_type in sorted(df_clustered['behavior_type'].unique()):
        cluster_data = df_clustered[df_clustered['behavior_type'] == behavior_type]
        row = {'behavior_type': behavior_type}
        for feature in comparison_features:
            row[feature] = cluster_data[feature].mean()
        comparison_data.append(row)
    
    df_comparison = pd.DataFrame(comparison_data).set_index('behavior_type')
    
    # Нормализуем для heatmap (z-score по столбцам)
    df_comparison_norm = df_comparison.apply(lambda x: (x - x.mean()) / x.std(), axis=0)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    if HAS_SEABORN:
        sns.heatmap(df_comparison_norm.T, annot=True, fmt='.2f', cmap='RdYlGn', 
                    center=0, cbar_kws={'label': 'Z-score (нормализованное отклонение)'},
                    linewidths=0.5, linecolor='black', ax=ax)
    else:
        # Используем matplotlib если seaborn недоступен
        im = ax.imshow(df_comparison_norm.T.values, cmap='RdYlGn', aspect='auto', 
                      vmin=-2, vmax=2, interpolation='nearest')
        plt.colorbar(im, ax=ax, label='Z-score (нормализованное отклонение)')
        
        # Добавляем аннотации
        for i in range(len(df_comparison_norm.T.index)):
            for j in range(len(df_comparison_norm.T.columns)):
                text = ax.text(j, i, f'{df_comparison_norm.T.iloc[i, j]:.2f}',
                              ha="center", va="center", color="black", fontsize=9)
        
        ax.set_xticks(range(len(df_comparison_norm.T.columns)))
        ax.set_xticklabels(df_comparison_norm.T.columns, rotation=45, ha='right')
        ax.set_yticks(range(len(df_comparison_norm.T.index)))
        ax.set_yticklabels(df_comparison_norm.T.index)
    
    plt.title('Сравнение типов поведения по признакам\n(нормализованные значения)', 
              fontsize=14, fontweight='bold')
    plt.xlabel('Тип поведения', fontsize=12)
    plt.ylabel('Признак', fontsize=12)
    plt.tight_layout()
    
    output_file = OUTPUT_DIR / "behavior_types_comparison_heatmap.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Сравнительная heatmap сохранена в: {output_file}")
    
    # 3. Распределение траекторий по типам (pie chart)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Pie chart
    counts = df_clustered['behavior_type'].value_counts()
    colors_pie = plt.cm.Set3(np.linspace(0, 1, len(counts)))
    
    ax1.pie(counts.values, labels=counts.index, autopct='%1.1f%%', 
            colors=colors_pie, startangle=90)
    ax1.set_title('Распределение траекторий по типам поведения', 
                  fontsize=12, fontweight='bold')
    
    # Bar chart
    ax2.bar(range(len(counts)), counts.values, color=colors_pie)
    ax2.set_xticks(range(len(counts)))
    ax2.set_xticklabels(counts.index, rotation=45, ha='right')
    ax2.set_ylabel('Количество траекторий', fontsize=11)
    ax2.set_title('Количество траекторий по типам', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Добавляем значения на столбцы
    for i, v in enumerate(counts.values):
        ax2.text(i, v + 0.5, str(v), ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "behavior_types_distribution.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Распределение типов сохранено в: {output_file}")


def generate_insights(df_clustered, df_stats):
    """
    Генерирует выводы и инсайты из анализа.
    """
    print("\n" + "=" * 60)
    print("ВЫВОДЫ И ИНСАЙТЫ")
    print("=" * 60)
    
    # Вычисляем общие статистики
    overall_stats = {
        'speed': df_clustered['speed'].mean(),
        'duration': df_clustered['duration'].mean(),
        'nb_stops': df_clustered['nb_stops'].mean(),
        'nb_items': df_clustered['nb_items'].mean(),
    }
    
    insights = []
    
    for behavior_type in sorted(df_clustered['behavior_type'].unique()):
        cluster_data = df_clustered[df_clustered['behavior_type'] == behavior_type]
        n = len(cluster_data)
        
        speed = cluster_data['speed'].mean()
        duration = cluster_data['duration'].mean()
        stops = cluster_data['nb_stops'].mean()
        items = cluster_data['nb_items'].mean()
        
        insight = f"\n{behavior_type} ({n} траекторий):"
        
        # Анализ скорости
        if speed > overall_stats['speed'] * 1.2:
            insight += f"\n  • Высокая скорость ({speed:.2f} vs среднее {overall_stats['speed']:.2f})"
        elif speed < overall_stats['speed'] * 0.8:
            insight += f"\n  • Низкая скорость ({speed:.2f} vs среднее {overall_stats['speed']:.2f})"
        
        # Анализ длительности
        if duration > overall_stats['duration'] * 1.2:
            insight += f"\n  • Долгий визит ({duration/60:.1f} мин vs среднее {overall_stats['duration']/60:.1f} мин)"
        elif duration < overall_stats['duration'] * 0.8:
            insight += f"\n  • Короткий визит ({duration/60:.1f} мин vs среднее {overall_stats['duration']/60:.1f} мин)"
        
        # Анализ остановок
        if stops > overall_stats['nb_stops'] * 1.2:
            insight += f"\n  • Много остановок ({stops:.1f} vs среднее {overall_stats['nb_stops']:.1f})"
        elif stops < overall_stats['nb_stops'] * 0.8:
            insight += f"\n  • Мало остановок ({stops:.1f} vs среднее {overall_stats['nb_stops']:.1f})"
        
        # Анализ экспонатов
        if items > overall_stats['nb_items'] * 1.2:
            insight += f"\n  • Много экспонатов ({items:.1f} vs среднее {overall_stats['nb_items']:.1f})"
        elif items < overall_stats['nb_items'] * 0.8:
            insight += f"\n  • Мало экспонатов ({items:.1f} vs среднее {overall_stats['nb_items']:.1f})"
        
        # Интенсивность
        if 'stop_intensity' in cluster_data.columns:
            intensity = cluster_data['stop_intensity'].mean()
            avg_intensity = df_clustered['stop_intensity'].mean()
            if intensity > avg_intensity * 1.2:
                insight += f"\n  • Высокая интенсивность остановок ({intensity:.2f} остановок/мин)"
        
        insights.append(insight)
    
    for insight in insights:
        print(insight)
    
    # Общие выводы
    print("\n" + "-" * 60)
    print("ОБЩИЕ ВЫВОДЫ:")
    print("-" * 60)
    
    # Самый распространенный тип
    most_common = df_clustered['behavior_type'].value_counts().index[0]
    most_common_pct = df_clustered['behavior_type'].value_counts().iloc[0] / len(df_clustered) * 100
    print(f"\n1. Самый распространенный тип: {most_common} ({most_common_pct:.1f}% траекторий)")
    
    # Самый быстрый и самый медленный
    speed_by_type = df_clustered.groupby('behavior_type')['speed'].mean().sort_values(ascending=False)
    fastest = speed_by_type.index[0]
    slowest = speed_by_type.index[-1]
    print(f"\n2. Самый быстрый тип: {fastest} (скорость: {speed_by_type[fastest]:.2f})")
    print(f"   Самый медленный тип: {slowest} (скорость: {speed_by_type[slowest]:.2f})")
    
    # Больше всего экспонатов
    items_by_type = df_clustered.groupby('behavior_type')['nb_items'].mean().sort_values(ascending=False)
    most_items = items_by_type.index[0]
    print(f"\n3. Больше всего экспонатов просматривает: {most_items} ({items_by_type[most_items]:.1f} экспонатов)")
    
    # Больше всего остановок
    stops_by_type = df_clustered.groupby('behavior_type')['nb_stops'].mean().sort_values(ascending=False)
    most_stops = stops_by_type.index[0]
    print(f"\n4. Больше всего останавливается: {most_stops} ({stops_by_type[most_stops]:.1f} остановок)")


def main():
    """Основная функция для анализа результатов кластеризации."""
    print("=" * 60)
    print("АНАЛИЗ РЕЗУЛЬТАТОВ КЛАСТЕРИЗАЦИИ ТИПОВ ПОВЕДЕНИЯ")
    print("=" * 60)
    
    # Загружаем данные
    print("\n[1] Загрузка результатов кластеризации...")
    df_clustered, df_stats, df_summary = load_clustering_results()
    
    # Анализируем характеристики
    print("\n[2] Анализ характеристик типов поведения...")
    df_analysis = analyze_cluster_characteristics(df_clustered, df_stats)
    
    # Сравниваем кластеры
    print("\n[3] Сравнительный анализ...")
    compare_clusters(df_clustered, df_stats)
    
    # Создаем визуализации
    print("\n[4] Создание детальных визуализаций...")
    create_detailed_visualizations(df_clustered, df_stats)
    
    # Генерируем выводы
    print("\n[5] Генерация выводов...")
    generate_insights(df_clustered, df_stats)
    
    # Сохраняем детальный анализ
    output_analysis = OUTPUT_DIR / "detailed_cluster_analysis.csv"
    df_analysis.to_csv(output_analysis, index=False)
    print(f"\n[6] Детальный анализ сохранен в: {output_analysis}")
    
    print("\n" + "=" * 60)
    print("Анализ результатов кластеризации завершен!")
    print("=" * 60)
    
    return df_analysis


if __name__ == "__main__":
    df_analysis = main()
