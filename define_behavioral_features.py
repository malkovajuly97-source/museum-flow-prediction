"""
Этап 2: Определение поведенческих признаков для кластеризации

Этот скрипт:
1. Загружает подготовленные данные из этапа 1
2. Определяет базовые признаки (из semantic_info)
3. Вычисляет дополнительные признаки (интенсивность остановок, плотность осмотров, извилистость, индекс исследовательности)
4. Нормализует признаки
5. Проверяет корреляции между признаками
6. Сохраняет подготовленные признаки для кластеризации
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import zscore
from sklearn.preprocessing import StandardScaler

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
SEMANTIC_FILE = INPUT_DIR / "floor0_semantic_features.csv"


def load_prepared_data():
    """
    Загружает подготовленные семантические признаки из этапа 1.
    
    Returns:
        pd.DataFrame: DataFrame с семантическими признаками
    """
    if not SEMANTIC_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {SEMANTIC_FILE}. Сначала запустите prepare_floor0_data.py")
    
    df = pd.read_csv(SEMANTIC_FILE)
    
    # Преобразуем trajectory_id в строку для совместимости
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    
    print(f"Загружено данных для {len(df)} траекторий")
    print(f"Колонки: {list(df.columns)}")
    
    return df


def compute_additional_features(df):
    """
    Вычисляет дополнительные поведенческие признаки.
    
    Args:
        df: DataFrame с базовыми семантическими признаками
    
    Returns:
        pd.DataFrame: DataFrame с добавленными признаками
    """
    print("\nВычисление дополнительных поведенческих признаков...")
    
    df_features = df.copy()
    
    # 1. Интенсивность остановок (количество остановок на единицу времени)
    df_features['stop_intensity'] = df_features['nb_stops'] / (df_features['duration'] / 60.0)  # остановок в минуту
    
    # 2. Плотность осмотров (количество экспонатов на единицу длины пути)
    df_features['item_density'] = df_features['nb_items'] / (df_features['length'] / 1000.0)  # экспонатов на 1000 единиц пути
    
    # 3. Плотность осмотров по времени (количество экспонатов на единицу времени)
    df_features['item_time_density'] = df_features['nb_items'] / (df_features['duration'] / 60.0)  # экспонатов в минуту
    
    # 4. Извилистость в относительных единицах (нормализованная кривизна)
    # Умножаем кривизну на длину пути для получения общей "извилистости"
    df_features['normalized_curvature'] = df_features['curvature'] * df_features['length'] / 1000.0
    
    # 5. Индекс "исследовательности" (отношение длины пути к прямому расстоянию)
    # Для этого нужно вычислить прямую линию от начала до конца траектории
    # Но у нас нет координат начала/конца в семантических данных
    # Используем альтернативу: отношение длины к длительности (эффективность использования времени)
    df_features['path_efficiency'] = df_features['length'] / df_features['duration']  # единиц пути в секунду
    
    # 6. Средняя скорость остановок (сколько времени между остановками)
    df_features['avg_time_between_stops'] = df_features['duration'] / (df_features['nb_stops'] + 1)  # +1 чтобы избежать деления на 0
    
    # 7. Соотношение времени просмотра к общему времени (если есть avg_observation_time)
    if 'avg_observation_time' in df_features.columns:
        # Оценка: среднее время просмотра * количество экспонатов / общее время
        df_features['observation_time_ratio'] = (
            df_features['avg_observation_time'] * df_features['nb_items'] / df_features['duration']
        )
        # Заменяем нереалистичные значения (>1) на NaN
        df_features.loc[df_features['observation_time_ratio'] > 1, 'observation_time_ratio'] = np.nan
    
    print(f"  Добавлено признаков: stop_intensity, item_density, item_time_density, normalized_curvature, path_efficiency, avg_time_between_stops")
    if 'avg_observation_time' in df_features.columns:
        print(f"  Также добавлен: observation_time_ratio")
    
    return df_features


def check_correlations(df_features):
    """
    Проверяет корреляции между признаками и визуализирует матрицу корреляций.
    
    Args:
        df_features: DataFrame с признаками
    """
    print("\nПроверка корреляций между признаками...")
    
    # Выбираем числовые колонки для корреляционного анализа
    feature_columns = [
        'duration', 'speed', 'nb_items', 'nb_stops', 'length', 
        'distwall', 'curvature', 'stop_intensity', 'item_density',
        'item_time_density', 'normalized_curvature', 'path_efficiency',
        'avg_time_between_stops'
    ]
    
    # Добавляем avg_observation_time и observation_time_ratio если есть
    if 'avg_observation_time' in df_features.columns:
        feature_columns.append('avg_observation_time')
    if 'observation_time_ratio' in df_features.columns:
        feature_columns.append('observation_time_ratio')
    
    # Фильтруем только существующие колонки
    available_columns = [col for col in feature_columns if col in df_features.columns]
    
    # Вычисляем корреляционную матрицу
    corr_matrix = df_features[available_columns].corr()
    
    # Выводим сильно коррелированные пары (|r| > 0.7)
    print("\nСильно коррелированные пары признаков (|r| > 0.7):")
    high_corr_pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            corr_value = corr_matrix.iloc[i, j]
            if abs(corr_value) > 0.7:
                high_corr_pairs.append((
                    corr_matrix.columns[i],
                    corr_matrix.columns[j],
                    corr_value
                ))
                print(f"  {corr_matrix.columns[i]} <-> {corr_matrix.columns[j]}: {corr_value:.3f}")
    
    if len(high_corr_pairs) == 0:
        print("  Сильно коррелированных пар не найдено")
    
    # Визуализация матрицы корреляций
    plt.figure(figsize=(14, 12))
    
    if HAS_SEABORN:
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            square=True,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8}
        )
    else:
        # Используем matplotlib если seaborn недоступен
        im = plt.imshow(corr_matrix.values, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
        plt.colorbar(im, shrink=0.8)
        plt.xticks(range(len(corr_matrix.columns)), corr_matrix.columns, rotation=45, ha='right')
        plt.yticks(range(len(corr_matrix.columns)), corr_matrix.columns)
        
        # Добавляем аннотации
        for i in range(len(corr_matrix.columns)):
            for j in range(len(corr_matrix.columns)):
                text = plt.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                              ha="center", va="center", color="black", fontsize=8)
    
    plt.title('Матрица корреляций поведенческих признаков', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    output_file = OUTPUT_DIR / "correlation_matrix.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\nМатрица корреляций сохранена в: {output_file}")
    
    return corr_matrix, high_corr_pairs


def normalize_features(df_features, method='standard'):
    """
    Нормализует признаки для кластеризации.
    
    Args:
        df_features: DataFrame с признаками
        method: метод нормализации ('standard' или 'minmax')
    
    Returns:
        tuple: (DataFrame с нормализованными признаками, StandardScaler для обратного преобразования)
    """
    print(f"\nНормализация признаков (метод: {method})...")
    
    # Выбираем признаки для нормализации (исключаем trajectory_id и нечисловые)
    feature_columns = [
        'duration', 'speed', 'nb_items', 'nb_stops', 'length', 
        'distwall', 'curvature', 'stop_intensity', 'item_density',
        'item_time_density', 'normalized_curvature', 'path_efficiency',
        'avg_time_between_stops'
    ]
    
    # Добавляем avg_observation_time и observation_time_ratio если есть
    if 'avg_observation_time' in df_features.columns:
        feature_columns.append('avg_observation_time')
    if 'observation_time_ratio' in df_features.columns:
        feature_columns.append('observation_time_ratio')
    
    # Фильтруем только существующие колонки
    available_columns = [col for col in feature_columns if col in df_features.columns]
    
    # Создаем копию для нормализации
    df_normalized = df_features.copy()
    
    if method == 'standard':
        # Стандартизация (z-score): среднее = 0, стандартное отклонение = 1
        scaler = StandardScaler()
        normalized_values = scaler.fit_transform(df_features[available_columns].fillna(0))
        
        # Создаем DataFrame с нормализованными значениями
        for i, col in enumerate(available_columns):
            df_normalized[f'{col}_norm'] = normalized_values[:, i]
        
        print(f"  Нормализовано {len(available_columns)} признаков (стандартизация)")
        
    elif method == 'minmax':
        # Min-Max нормализация: значения в диапазоне [0, 1]
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        normalized_values = scaler.fit_transform(df_features[available_columns].fillna(0))
        
        for i, col in enumerate(available_columns):
            df_normalized[f'{col}_norm'] = normalized_values[:, i]
        
        print(f"  Нормализовано {len(available_columns)} признаков (min-max)")
    
    return df_normalized, scaler, available_columns


def remove_outliers(df_features, z_threshold=3):
    """
    Удаляет выбросы на основе z-score.
    
    Args:
        df_features: DataFrame с признаками
        z_threshold: порог z-score для определения выбросов
    
    Returns:
        pd.DataFrame: DataFrame без выбросов
    """
    print(f"\nУдаление выбросов (z-score порог: {z_threshold})...")
    
    # Выбираем числовые колонки для проверки выбросов
    numeric_columns = df_features.select_dtypes(include=[np.number]).columns.tolist()
    numeric_columns = [col for col in numeric_columns if col != 'trajectory_id']
    
    # Вычисляем z-scores
    z_scores = np.abs(zscore(df_features[numeric_columns].fillna(0)))
    
    # Находим строки с выбросами (хотя бы один признак превышает порог)
    outlier_mask = (z_scores > z_threshold).any(axis=1)
    
    n_outliers = outlier_mask.sum()
    print(f"  Найдено выбросов: {n_outliers} траекторий из {len(df_features)}")
    
    if n_outliers > 0:
        print(f"  Выбросы (trajectory_id):")
        outliers_df = df_features[outlier_mask][['trajectory_id'] + numeric_columns[:5]]  # Показываем первые 5 признаков
        print(outliers_df.to_string(index=False))
        
        # Удаляем выбросы
        df_clean = df_features[~outlier_mask].copy()
        print(f"  Осталось траекторий после удаления выбросов: {len(df_clean)}")
    else:
        df_clean = df_features.copy()
        print(f"  Выбросы не найдены, все траектории сохранены")
    
    return df_clean


def main():
    """Основная функция для определения поведенческих признаков."""
    print("=" * 60)
    print("ЭТАП 2: Определение поведенческих признаков для кластеризации")
    print("=" * 60)
    
    # 2.1. Загружаем подготовленные данные
    print("\n[2.1] Загрузка подготовленных данных...")
    df_semantic = load_prepared_data()
    
    # 2.2. Вычисляем дополнительные признаки
    print("\n[2.2] Вычисление дополнительных признаков...")
    df_features = compute_additional_features(df_semantic)
    
    # 2.3. Проверяем корреляции
    print("\n[2.3] Проверка корреляций между признаками...")
    corr_matrix, high_corr_pairs = check_correlations(df_features)
    
    # 2.4. Удаляем выбросы (опционально, можно закомментировать)
    print("\n[2.4] Проверка и удаление выбросов...")
    df_clean = remove_outliers(df_features, z_threshold=3)
    
    # 2.5. Нормализуем признаки
    print("\n[2.5] Нормализация признаков...")
    df_normalized, scaler, feature_columns = normalize_features(df_clean, method='standard')
    
    # Сохраняем результаты
    # Полные данные с признаками
    output_file = OUTPUT_DIR / "floor0_behavioral_features.csv"
    df_features.to_csv(output_file, index=False)
    print(f"\n[2.6] Полные данные с признаками сохранены в: {output_file}")
    
    # Данные без выбросов
    output_clean = OUTPUT_DIR / "floor0_behavioral_features_clean.csv"
    df_clean.to_csv(output_clean, index=False)
    print(f"Данные без выбросов сохранены в: {output_clean}")
    
    # Нормализованные данные (только для кластеризации)
    output_norm = OUTPUT_DIR / "floor0_behavioral_features_normalized.csv"
    df_normalized.to_csv(output_norm, index=False)
    print(f"Нормализованные данные сохранены в: {output_norm}")
    
    # Список признаков для кластеризации
    norm_columns = [col for col in df_normalized.columns if col.endswith('_norm')]
    features_for_clustering = pd.DataFrame({
        'feature_name': [col.replace('_norm', '') for col in norm_columns],
        'normalized_column': norm_columns
    })
    features_list_file = OUTPUT_DIR / "features_for_clustering.csv"
    features_for_clustering.to_csv(features_list_file, index=False)
    print(f"Список признаков для кластеризации сохранен в: {features_list_file}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПРИЗНАКОВ:")
    print("=" * 60)
    print(f"Всего траекторий: {len(df_features)}")
    print(f"Траекторий без выбросов: {len(df_clean)}")
    print(f"Базовых признаков: 8 (duration, speed, nb_items, nb_stops, length, distwall, curvature, avg_observation_time)")
    print(f"Дополнительных признаков: {len(df_features.columns) - len(df_semantic.columns)}")
    print(f"Всего признаков: {len(df_features.columns) - 1}")  # -1 для trajectory_id
    print(f"Нормализованных признаков: {len(norm_columns)}")
    
    print("\n" + "=" * 60)
    print("Определение признаков завершено успешно!")
    print("=" * 60)
    
    return df_features, df_clean, df_normalized, feature_columns


if __name__ == "__main__":
    df_features, df_clean, df_normalized, feature_cols = main()
