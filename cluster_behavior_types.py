"""
Этап 3: Кластеризация типов поведения

Этот скрипт:
1. Загружает нормализованные поведенческие признаки из этапа 2
2. Выбирает оптимальное число кластеров (elbow method, silhouette score)
3. Выполняет кластеризацию KMeans
4. Интерпретирует кластеры (называет типы поведения)
5. Визуализирует распределения признаков по кластерам
6. Сохраняет результаты кластеризации
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.decomposition import PCA
import warnings
warnings.filterwarnings('ignore')

# Пути к данным
INPUT_DIR = Path("analysis_results")
OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

# Файлы
NORMALIZED_FILE = INPUT_DIR / "floor0_behavioral_features_normalized.csv"
FEATURES_LIST_FILE = INPUT_DIR / "features_for_clustering.csv"


def load_normalized_data():
    """
    Загружает нормализованные данные для кластеризации.
    
    Returns:
        tuple: (DataFrame с данными, список нормализованных колонок)
    """
    if not NORMALIZED_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {NORMALIZED_FILE}. Сначала запустите define_behavioral_features.py")
    
    df = pd.read_csv(NORMALIZED_FILE)
    
    # Преобразуем trajectory_id в строку
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    
    # Загружаем список признаков для кластеризации
    if FEATURES_LIST_FILE.exists():
        features_df = pd.read_csv(FEATURES_LIST_FILE)
        norm_columns = features_df['normalized_column'].tolist()
    else:
        # Если файла нет, находим все колонки с _norm
        norm_columns = [col for col in df.columns if col.endswith('_norm')]
    
    # Фильтруем только существующие колонки
    norm_columns = [col for col in norm_columns if col in df.columns]
    
    print(f"Загружено данных для {len(df)} траекторий")
    print(f"Признаков для кластеризации: {len(norm_columns)}")
    print(f"Признаки: {norm_columns}")
    
    return df, norm_columns


def find_optimal_clusters(X, k_range=range(2, 8)):
    """
    Находит оптимальное число кластеров используя elbow method и silhouette score.
    
    Args:
        X: матрица признаков для кластеризации
        k_range: диапазон чисел кластеров для проверки
    
    Returns:
        tuple: (оптимальное k, результаты для всех k)
    """
    print(f"\nПоиск оптимального числа кластеров (проверяем k от {min(k_range)} до {max(k_range)})...")
    
    inertias = []
    silhouette_scores = []
    
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = kmeans.fit_predict(X)
        
        inertias.append(kmeans.inertia_)
        sil_score = silhouette_score(X, labels)
        silhouette_scores.append(sil_score)
        
        print(f"  k={k}: inertia={kmeans.inertia_:.2f}, silhouette={sil_score:.3f}")
    
    # Визуализация
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Elbow method
    ax1.plot(k_range, inertias, marker='o', linewidth=2, markersize=8)
    ax1.set_xlabel('Число кластеров (k)', fontsize=12)
    ax1.set_ylabel('Within-cluster sum of squares (WCSS)', fontsize=12)
    ax1.set_title('Elbow Method', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(list(k_range))
    
    # Silhouette score
    ax2.plot(k_range, silhouette_scores, marker='o', linewidth=2, markersize=8, color='green')
    ax2.set_xlabel('Число кластеров (k)', fontsize=12)
    ax2.set_ylabel('Silhouette Score', fontsize=12)
    ax2.set_title('Silhouette Score', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(list(k_range))
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "optimal_clusters_analysis.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nГрафики анализа сохранены в: {output_file}")
    
    # Выбираем оптимальное k
    # Предпочитаем более высокий silhouette score, но учитываем и elbow
    best_sil_idx = np.argmax(silhouette_scores)
    optimal_k = list(k_range)[best_sil_idx]
    
    print(f"\nОптимальное число кластеров: k={optimal_k} (silhouette={silhouette_scores[best_sil_idx]:.3f})")
    
    results = {
        'k_range': list(k_range),
        'inertias': inertias,
        'silhouette_scores': silhouette_scores,
        'optimal_k': optimal_k
    }
    
    return optimal_k, results


def perform_clustering(X, n_clusters, random_state=42):
    """
    Выполняет кластеризацию KMeans.
    
    Args:
        X: матрица признаков
        n_clusters: число кластеров
        random_state: seed для воспроизводимости
    
    Returns:
        tuple: (KMeans модель, метки кластеров)
    """
    print(f"\nВыполнение кластеризации KMeans с k={n_clusters}...")
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=20)
    labels = kmeans.fit_predict(X)
    
    print(f"Кластеризация завершена")
    print(f"Распределение по кластерам:")
    unique, counts = np.unique(labels, return_counts=True)
    for cluster_id, count in zip(unique, counts):
        print(f"  Кластер {cluster_id}: {count} траекторий ({count/len(labels)*100:.1f}%)")
    
    return kmeans, labels


def interpret_clusters(df, labels, norm_columns, feature_names):
    """
    Интерпретирует кластеры на основе средних значений признаков.
    
    Args:
        df: DataFrame с исходными (ненормализованными) признаками
        labels: метки кластеров
        norm_columns: список нормализованных колонок
        feature_names: словарь соответствия нормализованных и исходных имен признаков
    
    Returns:
        pd.DataFrame: DataFrame с интерпретацией кластеров
    """
    print("\nИнтерпретация кластеров...")
    
    df_clustered = df.copy()
    df_clustered['behavior_type'] = labels
    
    # Получаем исходные имена признаков (без _norm)
    original_features = [col.replace('_norm', '') for col in norm_columns if col in df.columns]
    
    # Вычисляем средние значения для каждого кластера
    cluster_stats = []
    
    for cluster_id in sorted(np.unique(labels)):
        cluster_data = df_clustered[df_clustered['behavior_type'] == cluster_id]
        
        stats = {'cluster_id': cluster_id, 'n_trajectories': len(cluster_data)}
        
        # Средние значения по каждому признаку
        for feature in original_features:
            if feature in cluster_data.columns:
                stats[feature] = cluster_data[feature].mean()
        
        cluster_stats.append(stats)
    
    df_cluster_stats = pd.DataFrame(cluster_stats)
    
    # Называем типы поведения на основе характеристик
    behavior_names = []
    
    for cluster_id in sorted(np.unique(labels)):
        stats = df_cluster_stats[df_cluster_stats['cluster_id'] == cluster_id].iloc[0]
        
        # Определяем характеристики
        speed = stats.get('speed', 0)
        duration = stats.get('duration', 0)
        nb_stops = stats.get('nb_stops', 0)
        nb_items = stats.get('nb_items', 0)
        avg_obs_time = stats.get('avg_observation_time', np.nan)
        
        # Средние значения для сравнения
        avg_speed = df_clustered['speed'].mean()
        avg_duration = df_clustered['duration'].mean()
        avg_stops = df_clustered['nb_stops'].mean()
        avg_items = df_clustered['nb_items'].mean()
        
        # Определяем тип поведения на основе комбинации признаков
        avg_obs_time_mean = df_clustered['avg_observation_time'].mean() if 'avg_observation_time' in df_clustered.columns else np.nan
        
        # Критерии для определения типов
        is_fast = speed > avg_speed * 1.15
        is_slow = speed < avg_speed * 0.85
        is_short = duration < avg_duration * 0.85
        is_long = duration > avg_duration * 1.15
        has_many_stops = nb_stops > avg_stops * 1.15
        has_few_stops = nb_stops < avg_stops * 0.85
        has_many_items = nb_items > avg_items * 1.15
        has_few_items = nb_items < avg_items * 0.85
        is_attentive = not np.isnan(avg_obs_time) and avg_obs_time > avg_obs_time_mean * 1.1
        
        # Определяем тип поведения
        if is_fast and is_short and has_few_stops:
            behavior_type = "Быстрый краткий"
        elif is_slow and is_long and has_many_stops:
            behavior_type = "Медленный долгий"
        elif has_many_stops and has_many_items and (is_attentive or is_long):
            behavior_type = "Внимательный исследователь"
        elif is_fast and has_many_items and not has_few_stops:
            behavior_type = "Активный обходчик"
        elif is_fast and has_few_stops and is_short:
            behavior_type = "Транзитный"
        elif is_slow and has_many_stops and has_many_items:
            behavior_type = "Глубокий исследователь"
        elif is_fast and has_many_items:
            behavior_type = "Эффективный обходчик"
        else:
            # Дополнительная логика для оставшихся случаев
            if has_many_items and has_many_stops:
                behavior_type = "Исследователь"
            elif is_fast:
                behavior_type = "Быстрый"
            elif is_slow:
                behavior_type = "Медленный"
            else:
                behavior_type = f"Смешанный тип {cluster_id}"
        
        behavior_names.append({
            'cluster_id': cluster_id,
            'behavior_type': behavior_type
        })
    
    df_behavior_names = pd.DataFrame(behavior_names)
    df_cluster_stats = df_cluster_stats.merge(df_behavior_names, on='cluster_id')
    
    print("\nХарактеристики кластеров:")
    print(df_cluster_stats[['cluster_id', 'behavior_type', 'n_trajectories', 
                           'speed', 'duration', 'nb_stops', 'nb_items']].to_string(index=False))
    
    return df_cluster_stats, df_clustered


def visualize_clusters(df_clustered, norm_columns, kmeans, labels):
    """
    Визуализирует кластеры и распределения признаков.
    
    Args:
        df_clustered: DataFrame с метками кластеров
        norm_columns: список нормализованных колонок
        kmeans: обученная модель KMeans
        labels: метки кластеров
    """
    print("\nСоздание визуализаций...")
    
    # 1. PCA визуализация (2D проекция)
    X_norm = df_clustered[norm_columns].values
    
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_norm)
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    unique_labels = sorted(np.unique(labels))
    colors = plt.cm.Set3(np.linspace(0, 1, len(unique_labels)))
    
    for i, label in enumerate(unique_labels):
        mask = labels == label
        ax.scatter(X_pca[mask, 0], X_pca[mask, 1], 
                  c=[colors[i]], label=f'Кластер {label}', 
                  s=100, alpha=0.7, edgecolors='black', linewidth=1)
    
    # Центры кластеров в PCA пространстве
    centers_pca = pca.transform(kmeans.cluster_centers_)
    ax.scatter(centers_pca[:, 0], centers_pca[:, 1], 
              c='red', marker='x', s=200, linewidths=3, 
              label='Центры кластеров', zorder=10)
    
    ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)', fontsize=12)
    ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)', fontsize=12)
    ax.set_title('Кластеризация траекторий (PCA проекция)', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "clusters_pca_visualization.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  PCA визуализация сохранена в: {output_file}")
    
    # 2. Распределения признаков по кластерам (boxplot)
    key_features = ['speed', 'duration', 'nb_stops', 'nb_items', 'length', 'curvature']
    key_features = [f for f in key_features if f in df_clustered.columns]
    
    n_features = len(key_features)
    n_cols = 3
    n_rows = (n_features + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 5*n_rows))
    axes = axes.flatten() if n_features > 1 else [axes]
    
    for idx, feature in enumerate(key_features):
        ax = axes[idx]
        
        data_by_cluster = [df_clustered[df_clustered['behavior_type'] == label][feature].values 
                          for label in sorted(np.unique(labels))]
        
        bp = ax.boxplot(data_by_cluster, labels=[f'Кл.{i}' for i in sorted(np.unique(labels))],
                       patch_artist=True)
        
        # Раскрашиваем boxplot
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_ylabel(feature, fontsize=11)
        ax.set_title(f'Распределение {feature} по кластерам', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
    
    # Скрываем лишние subplots
    for idx in range(n_features, len(axes)):
        axes[idx].set_visible(False)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "clusters_feature_distributions.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Распределения признаков сохранены в: {output_file}")


def main():
    """Основная функция для кластеризации типов поведения."""
    print("=" * 60)
    print("ЭТАП 3: Кластеризация типов поведения")
    print("=" * 60)
    
    # 3.1. Загружаем нормализованные данные
    print("\n[3.1] Загрузка нормализованных данных...")
    df, norm_columns = load_normalized_data()
    
    # Подготовка матрицы признаков
    X = df[norm_columns].fillna(0).values
    
    # 3.2. Находим оптимальное число кластеров
    print("\n[3.2] Поиск оптимального числа кластеров...")
    optimal_k, cluster_results = find_optimal_clusters(X, k_range=range(2, 7))
    
    # 3.3. Выполняем кластеризацию
    print(f"\n[3.3] Кластеризация с k={optimal_k}...")
    kmeans, labels = perform_clustering(X, optimal_k)
    
    # 3.4. Интерпретируем кластеры
    print("\n[3.4] Интерпретация кластеров...")
    df_cluster_stats, df_clustered = interpret_clusters(df, labels, norm_columns, {})
    
    # 3.5. Визуализируем результаты
    print("\n[3.5] Визуализация кластеров...")
    visualize_clusters(df_clustered, norm_columns, kmeans, labels)
    
    # Сохраняем результаты
    # Данные с метками кластеров
    output_clustered = OUTPUT_DIR / "floor0_trajectories_clustered.csv"
    df_clustered.to_csv(output_clustered, index=False)
    print(f"\n[3.6] Данные с метками кластеров сохранены в: {output_clustered}")
    
    # Статистика по кластерам
    output_stats = OUTPUT_DIR / "cluster_statistics.csv"
    df_cluster_stats.to_csv(output_stats, index=False)
    print(f"Статистика по кластерам сохранена в: {output_stats}")
    
    # Сводная таблица
    summary = df_clustered.groupby('behavior_type').agg({
        'trajectory_id': 'count',
        'speed': 'mean',
        'duration': 'mean',
        'nb_stops': 'mean',
        'nb_items': 'mean',
        'length': 'mean'
    }).round(2)
    summary.columns = ['n_trajectories', 'avg_speed', 'avg_duration', 'avg_stops', 'avg_items', 'avg_length']
    summary = summary.reset_index()
    
    output_summary = OUTPUT_DIR / "behavior_types_summary.csv"
    summary.to_csv(output_summary, index=False)
    print(f"Сводная таблица типов поведения сохранена в: {output_summary}")
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ КЛАСТЕРИЗАЦИИ:")
    print("=" * 60)
    print(f"Оптимальное число кластеров: {optimal_k}")
    print(f"Silhouette score: {cluster_results['silhouette_scores'][optimal_k-2]:.3f}")
    print(f"\nТипы поведения:")
    for _, row in summary.iterrows():
        print(f"  {row['behavior_type']}: {row['n_trajectories']} траекторий")
        print(f"    Средняя скорость: {row['avg_speed']:.2f}")
        print(f"    Средняя длительность: {row['avg_duration']:.2f} сек")
        print(f"    Среднее количество остановок: {row['avg_stops']:.2f}")
        print(f"    Среднее количество экспонатов: {row['avg_items']:.2f}")
    
    print("\n" + "=" * 60)
    print("Кластеризация завершена успешно!")
    print("=" * 60)
    
    return df_clustered, df_cluster_stats, kmeans


if __name__ == "__main__":
    df_clustered, df_stats, kmeans_model = main()
