"""
Объединение кластеров "Быстрый" и "Быстрый краткий"

Этот скрипт:
1. Загружает результаты кластеризации
2. Объединяет "Быстрый" и "Быстрый краткий" в один кластер "Быстрый"
3. Пересоздает все визуализации и таблицы
4. Сохраняет результаты в отдельную папку
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.decomposition import PCA
import warnings
warnings.filterwarnings('ignore')

# Опциональный импорт seaborn
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# Пути к данным
INPUT_DIR = Path("analysis_results")
OUTPUT_DIR = Path("analysis_results_merged")
OUTPUT_DIR.mkdir(exist_ok=True)

# Файлы
CLUSTERED_FILE = INPUT_DIR / "floor0_trajectories_clustered.csv"


def load_and_merge_clusters():
    """Загружает данные и объединяет кластеры."""
    print("=" * 70)
    print("ОБЪЕДИНЕНИЕ КЛАСТЕРОВ 'Быстрый' И 'Быстрый краткий'")
    print("=" * 70)
    
    # Загружаем данные
    df = pd.read_csv(CLUSTERED_FILE)
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    
    # Загружаем соответствие cluster_id -> behavior_type из cluster_statistics.csv
    cluster_stats_file = INPUT_DIR / "cluster_statistics.csv"
    cluster_stats = pd.read_csv(cluster_stats_file)
    cluster_to_type = dict(zip(cluster_stats['cluster_id'], cluster_stats['behavior_type']))
    
    # Добавляем названия типов поведения в DataFrame
    df['behavior_type_name'] = df['behavior_type'].map(cluster_to_type)
    
    print(f"\nИсходные данные:")
    print(f"  Всего траекторий: {len(df)}")
    print(f"  Типов поведения: {df['behavior_type_name'].nunique()}")
    print(f"  Распределение:")
    for behavior_type, count in df['behavior_type_name'].value_counts().items():
        print(f"    {behavior_type}: {count} траекторий")
    
    # Объединяем кластеры: "Быстрый краткий" -> "Быстрый"
    df_merged = df.copy()
    
    # Находим индексы кластеров для "Быстрый" и "Быстрый краткий"
    fast_cluster_id = cluster_stats[cluster_stats['behavior_type'] == 'Быстрый']['cluster_id'].values
    fast_brief_cluster_id = cluster_stats[cluster_stats['behavior_type'] == 'Быстрый краткий']['cluster_id'].values
    
    if len(fast_cluster_id) > 0 and len(fast_brief_cluster_id) > 0:
        target_cluster_id = fast_cluster_id[0]
        source_cluster_id = fast_brief_cluster_id[0]
        
        # Объединяем: все траектории из "Быстрый краткий" получают индекс "Быстрый"
        df_merged.loc[df_merged['behavior_type'] == source_cluster_id, 'behavior_type'] = target_cluster_id
        df_merged.loc[df_merged['behavior_type_name'] == 'Быстрый краткий', 'behavior_type_name'] = 'Быстрый'
    
    print(f"\nПосле объединения:")
    print(f"  Всего траекторий: {len(df_merged)}")
    print(f"  Типов поведения: {df_merged['behavior_type_name'].nunique()}")
    print(f"  Распределение:")
    for behavior_type, count in df_merged['behavior_type_name'].value_counts().items():
        print(f"    {behavior_type}: {count} траекторий")
    
    # Используем behavior_type_name как основной столбец для дальнейшей работы
    df_merged['behavior_type'] = df_merged['behavior_type_name']
    df_merged = df_merged.drop(columns=['behavior_type_name'], errors='ignore')
    
    return df_merged


def create_cluster_statistics(df_merged):
    """Создает статистику по объединенным кластерам."""
    print("\n" + "=" * 70)
    print("СОЗДАНИЕ СТАТИСТИКИ ПО КЛАСТЕРАМ")
    print("=" * 70)
    
    # Получаем исходные имена признаков (без _norm)
    feature_cols = [col for col in df_merged.columns 
                   if not col.endswith('_norm') and 
                   col not in ['trajectory_id', 'behavior_type']]
    
    cluster_stats = []
    
    for behavior_type in sorted(df_merged['behavior_type'].unique()):
        cluster_data = df_merged[df_merged['behavior_type'] == behavior_type]
        
        stats = {
            'behavior_type': behavior_type,
            'n_trajectories': len(cluster_data)
        }
        
        # Средние значения по каждому признаку
        for feature in feature_cols:
            if feature in cluster_data.columns:
                values = cluster_data[feature].dropna()
                if len(values) > 0:
                    stats[feature] = values.mean()
        
        cluster_stats.append(stats)
    
    df_cluster_stats = pd.DataFrame(cluster_stats)
    
    print("\nСтатистика по кластерам:")
    print(df_cluster_stats[['behavior_type', 'n_trajectories', 
                           'speed', 'duration', 'nb_stops', 'nb_items']].to_string(index=False))
    
    # Сохраняем
    output_file = OUTPUT_DIR / "cluster_statistics_merged.csv"
    df_cluster_stats.to_csv(output_file, index=False)
    print(f"\nСтатистика сохранена в: {output_file}")
    
    return df_cluster_stats


def create_summary_table(df_merged):
    """Создает сводную таблицу."""
    summary = df_merged.groupby('behavior_type').agg({
        'trajectory_id': 'count',
        'speed': 'mean',
        'duration': 'mean',
        'nb_stops': 'mean',
        'nb_items': 'mean',
        'length': 'mean'
    }).round(2)
    summary.columns = ['n_trajectories', 'avg_speed', 'avg_duration', 'avg_stops', 'avg_items', 'avg_length']
    summary = summary.reset_index()
    
    output_file = OUTPUT_DIR / "behavior_types_summary_merged.csv"
    summary.to_csv(output_file, index=False)
    print(f"Сводная таблица сохранена в: {output_file}")
    
    return summary


def create_visualizations(df_merged):
    """Создает все визуализации для объединенных кластеров."""
    print("\n" + "=" * 70)
    print("СОЗДАНИЕ ВИЗУАЛИЗАЦИЙ")
    print("=" * 70)
    
    # 1. PCA визуализация
    print("\n[1] PCA визуализация...")
    norm_columns = [col for col in df_merged.columns if col.endswith('_norm')]
    
    if len(norm_columns) > 0:
        X_norm = df_merged[norm_columns].fillna(0).values
        
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_norm)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        behavior_types = sorted(df_merged['behavior_type'].unique())
        colors = plt.cm.Set3(np.linspace(0, 1, len(behavior_types)))
        
        for i, behavior_type in enumerate(behavior_types):
            mask = df_merged['behavior_type'] == behavior_type
            ax.scatter(X_pca[mask, 0], X_pca[mask, 1], 
                      c=[colors[i]], label=behavior_type, 
                      s=100, alpha=0.7, edgecolors='black', linewidth=1)
        
        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)', fontsize=12)
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)', fontsize=12)
        ax.set_title('Кластеризация траекторий (PCA проекция)\nПосле объединения кластеров', 
                     fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_file = OUTPUT_DIR / "clusters_pca_visualization_merged.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  PCA визуализация сохранена в: {output_file}")
    
    # 2. Распределения признаков по кластерам (boxplot)
    print("\n[2] Распределения признаков...")
    key_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length', 'curvature']
    key_features = [f for f in key_features if f in df_merged.columns]
    
    n_features = len(key_features)
    n_cols = 3
    n_rows = (n_features + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 5*n_rows))
    axes = axes.flatten() if n_features > 1 else [axes]
    
    behavior_types = sorted(df_merged['behavior_type'].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(behavior_types)))
    
    for idx, feature in enumerate(key_features):
        ax = axes[idx]
        
        data_by_cluster = [df_merged[df_merged['behavior_type'] == bt][feature].values 
                          for bt in behavior_types]
        
        bp = ax.boxplot(data_by_cluster, labels=behavior_types,
                       patch_artist=True)
        
        # Раскрашиваем boxplot
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_ylabel(feature, fontsize=11)
        ax.set_title(f'Распределение {feature} по кластерам', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Скрываем лишние subplots
    for idx in range(n_features, len(axes)):
        axes[idx].set_visible(False)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "clusters_feature_distributions_merged.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Распределения признаков сохранены в: {output_file}")
    
    # 3. Радарная диаграмма
    print("\n[3] Радарная диаграмма...")
    radar_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length']
    radar_features = [f for f in radar_features if f in df_merged.columns]
    
    fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(projection='polar'))
    
    angles = np.linspace(0, 2 * np.pi, len(radar_features), endpoint=False).tolist()
    angles += angles[:1]
    
    for idx, behavior_type in enumerate(behavior_types):
        cluster_data = df_merged[df_merged['behavior_type'] == behavior_type]
        
        values = []
        for feature in radar_features:
            mean_val = cluster_data[feature].mean()
            min_val = df_merged[feature].min()
            max_val = df_merged[feature].max()
            if max_val > min_val:
                normalized = (mean_val - min_val) / (max_val - min_val)
            else:
                normalized = 0.5
            values.append(normalized)
        
        values += values[:1]
        
        ax.plot(angles, values, 'o-', linewidth=2, label=behavior_type, color=colors[idx])
        ax.fill(angles, values, alpha=0.25, color=colors[idx])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_features, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=8)
    ax.grid(True)
    
    plt.title('Сравнение типов поведения (радарная диаграмма)\nПосле объединения кластеров', 
              fontsize=14, fontweight='bold', pad=20)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "behavior_types_radar_chart_merged.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Радарная диаграмма сохранена в: {output_file}")
    
    # 4. Сравнительная heatmap
    print("\n[4] Сравнительная heatmap...")
    comparison_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length', 
                          'stop_intensity', 'item_time_density']
    comparison_features = [f for f in comparison_features if f in df_merged.columns]
    
    comparison_data = []
    for behavior_type in sorted(behavior_types):
        cluster_data = df_merged[df_merged['behavior_type'] == behavior_type]
        row = {'behavior_type': behavior_type}
        for feature in comparison_features:
            row[feature] = cluster_data[feature].mean()
        comparison_data.append(row)
    
    df_comparison = pd.DataFrame(comparison_data).set_index('behavior_type')
    df_comparison_norm = df_comparison.apply(lambda x: (x - x.mean()) / x.std(), axis=0)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    if HAS_SEABORN:
        sns.heatmap(df_comparison_norm.T, annot=True, fmt='.2f', cmap='RdYlGn', 
                    center=0, cbar_kws={'label': 'Z-score (нормализованное отклонение)'},
                    linewidths=0.5, linecolor='black', ax=ax)
    else:
        im = ax.imshow(df_comparison_norm.T.values, cmap='RdYlGn', aspect='auto', 
                      vmin=-2, vmax=2, interpolation='nearest')
        plt.colorbar(im, ax=ax, label='Z-score (нормализованное отклонение)')
        
        for i in range(len(df_comparison_norm.T.index)):
            for j in range(len(df_comparison_norm.T.columns)):
                text = ax.text(j, i, f'{df_comparison_norm.T.iloc[i, j]:.2f}',
                              ha="center", va="center", color="black", fontsize=9)
        
        ax.set_xticks(range(len(df_comparison_norm.T.columns)))
        ax.set_xticklabels(df_comparison_norm.T.columns, rotation=45, ha='right')
        ax.set_yticks(range(len(df_comparison_norm.T.index)))
        ax.set_yticklabels(df_comparison_norm.T.index)
    
    plt.title('Сравнение типов поведения по признакам\n(нормализованные значения, после объединения)', 
              fontsize=14, fontweight='bold')
    plt.xlabel('Тип поведения', fontsize=12)
    plt.ylabel('Признак', fontsize=12)
    plt.tight_layout()
    
    output_file = OUTPUT_DIR / "behavior_types_comparison_heatmap_merged.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Сравнительная heatmap сохранена в: {output_file}")
    
    # 5. Распределение траекторий
    print("\n[5] Распределение траекторий...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    counts = df_merged['behavior_type'].value_counts()
    colors_pie = plt.cm.Set3(np.linspace(0, 1, len(counts)))
    
    ax1.pie(counts.values, labels=counts.index, autopct='%1.1f%%', 
            colors=colors_pie, startangle=90)
    ax1.set_title('Распределение траекторий по типам поведения\n(после объединения)', 
                  fontsize=12, fontweight='bold')
    
    ax2.bar(range(len(counts)), counts.values, color=colors_pie)
    ax2.set_xticks(range(len(counts)))
    ax2.set_xticklabels(counts.index, rotation=45, ha='right')
    ax2.set_ylabel('Количество траекторий', fontsize=11)
    ax2.set_title('Количество траекторий по типам', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    for i, v in enumerate(counts.values):
        ax2.text(i, v + 0.5, str(v), ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "behavior_types_distribution_merged.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Распределение типов сохранено в: {output_file}")


def main():
    """Основная функция."""
    print("=" * 70)
    print("ОБЪЕДИНЕНИЕ КЛАСТЕРОВ И СОЗДАНИЕ НОВЫХ ФАЙЛОВ")
    print("=" * 70)
    
    # Загружаем и объединяем
    df_merged = load_and_merge_clusters()
    
    # Сохраняем объединенные данные
    output_file = OUTPUT_DIR / "floor0_trajectories_clustered_merged.csv"
    df_merged.to_csv(output_file, index=False)
    print(f"\nОбъединенные данные сохранены в: {output_file}")
    
    # Создаем статистику
    df_cluster_stats = create_cluster_statistics(df_merged)
    
    # Создаем сводную таблицу
    summary = create_summary_table(df_merged)
    
    # Создаем визуализации
    create_visualizations(df_merged)
    
    # Итоговая информация
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ ОБЪЕДИНЕНИЯ")
    print("=" * 70)
    print(f"\nТипы поведения (после объединения):")
    for _, row in summary.iterrows():
        print(f"  {row['behavior_type']}: {row['n_trajectories']} траекторий")
        print(f"    Средняя скорость: {row['avg_speed']:.2f}")
        print(f"    Средняя длительность: {row['avg_duration']:.0f} сек")
        print(f"    Среднее количество остановок: {row['avg_stops']:.1f}")
        print(f"    Среднее количество экспонатов: {row['avg_items']:.1f}")
    
    print(f"\n" + "=" * 70)
    print("Все файлы сохранены в папку: analysis_results_merged/")
    print("=" * 70)
    
    return df_merged, df_cluster_stats, summary


if __name__ == "__main__":
    df_merged, df_stats, summary = main()
