"""
Этап 1: Подготовка данных для анализа паттернов поведения на этаже 0

Этот скрипт:
1. Собирает все траектории этажа 0 из normalized_trajectories
2. Загружает семантические признаки траекторий
3. Объединяет данные (используются все траектории, у которых есть точки на этаже 0)
4. Сохраняет подготовленные данные для дальнейшего анализа
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Пути к данным
TRAJ_DIR = Path("bird-dataset-main/data/normalized_trajectories")
SEMANTIC_FILE = Path("bird-dataset-main/data/semantic_info_entire_trajectories.csv")
START_OBS_DIR = Path("bird-dataset-main/data/start_obs_artworks")
END_OBS_DIR = Path("bird-dataset-main/data/end_obs_artworks")
OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_trajectories_floor0():
    """
    Загружает все траектории и фильтрует только этаж 0.
    
    Returns:
        pd.DataFrame: DataFrame с колонками trajectory_id, timestamp, x, y, floorNumber
    """
    csv_files = list(TRAJ_DIR.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"Не найдено CSV файлов в {TRAJ_DIR}")

    print(f"Найдено {len(csv_files)} файлов с траекториями")
    
    all_trajectories = []
    
    for csv_file in csv_files:
        try:
            # Извлекаем trajectory_id из имени файла
            trajectory_id = Path(csv_file).stem.replace('_traj_normalized', '')
            
            # Загружаем траекторию
            df = pd.read_csv(csv_file)
            
            # Добавляем trajectory_id
            df['trajectory_id'] = trajectory_id
            
            # Фильтруем только этаж 0
            df_floor0 = df[df['floorNumber'] == 0].copy()
            
            if len(df_floor0) > 0:
                all_trajectories.append(df_floor0)
                print(f"Загружен {csv_file.name}: {len(df)} точек всего, {len(df_floor0)} на этаже 0")
            else:
                print(f"Пропущен {csv_file.name}: нет точек на этаже 0")
                
        except Exception as e:
            print(f"Ошибка при загрузке {csv_file.name}: {e}")
    
    if not all_trajectories:
        raise ValueError("Не удалось загрузить ни одной траектории для этажа 0")
    
    # Объединяем все траектории
    combined_df = pd.concat(all_trajectories, ignore_index=True)
    
    # Переупорядочиваем колонки для удобства
    column_order = ['trajectory_id', 'timestamp', 'x', 'y', 'floorNumber']
    combined_df = combined_df[column_order]
    
    print(f"\nВсего загружено траекторий: {combined_df['trajectory_id'].nunique()}")
    print(f"Всего точек на этаже 0: {len(combined_df)}")
    print(f"Диапазон X: {combined_df['x'].min():.2f} - {combined_df['x'].max():.2f}")
    print(f"Диапазон Y: {combined_df['y'].min():.2f} - {combined_df['y'].max():.2f}")
    
    return combined_df


def calculate_avg_observation_time(trajectory_id):
    """
    Вычисляет среднее время просмотра объекта для траектории.
    
    Args:
        trajectory_id: ID траектории (строка)
    
    Returns:
        float: Среднее время просмотра в секундах, или np.nan если данных нет
    """
    start_file = START_OBS_DIR / f"items_{trajectory_id}.csv"
    end_file = END_OBS_DIR / f"items_{trajectory_id}_end.csv"
    
    # Проверяем наличие файлов
    if not start_file.exists() or not end_file.exists():
        return np.nan
    
    try:
        # Загружаем данные о начале и конце наблюдений
        df_start = pd.read_csv(start_file)
        df_end = pd.read_csv(end_file)
        
        # Фильтруем только этаж 0
        df_start_floor0 = df_start[df_start['floorNumber'] == 0].copy()
        df_end_floor0 = df_end[df_end['floorNumber'] == 0].copy()
        
        if len(df_start_floor0) == 0 or len(df_end_floor0) == 0:
            return np.nan
        
        # Сопоставляем start и end по paintingId
        observation_times = []
        
        for _, start_row in df_start_floor0.iterrows():
            painting_id = start_row['paintingId']
            start_time = start_row['timestamp']
            
            # Ищем соответствующий end для этого paintingId
            end_rows = df_end_floor0[df_end_floor0['paintingId'] == painting_id]
            
            if len(end_rows) > 0:
                # Берем ближайший по времени end (может быть несколько наблюдений одного объекта)
                end_times = end_rows['timestamp'].values
                # Находим минимальный end_time, который больше start_time
                valid_ends = end_times[end_times > start_time]
                
                if len(valid_ends) > 0:
                    end_time = valid_ends.min()
                    observation_time = end_time - start_time
                    
                    # Фильтруем нереалистичные значения (отрицательные или слишком большие)
                    if observation_time > 0 and observation_time < 3600:  # меньше часа
                        observation_times.append(observation_time)
        
        if len(observation_times) == 0:
            return np.nan
        
        # Возвращаем среднее время просмотра
        return np.mean(observation_times)
        
    except Exception as e:
        print(f"  Ошибка при вычислении времени просмотра для {trajectory_id}: {e}")
        return np.nan


def compute_avg_observation_times(trajectory_ids):
    """
    Вычисляет среднее время просмотра для списка траекторий.
    
    Args:
        trajectory_ids: список или множество trajectory_id
    
    Returns:
        pd.DataFrame: DataFrame с колонками trajectory_id и avg_observation_time
    """
    print("\nВычисление среднего времени просмотра объектов...")
    
    results = []
    for i, traj_id in enumerate(trajectory_ids, 1):
        avg_time = calculate_avg_observation_time(str(traj_id))
        results.append({
            'trajectory_id': str(traj_id),
            'avg_observation_time': avg_time
        })
        
        if i % 10 == 0:
            print(f"  Обработано {i}/{len(trajectory_ids)} траекторий")
    
    df_obs_times = pd.DataFrame(results)
    
    # Статистика
    valid_times = df_obs_times['avg_observation_time'].dropna()
    print(f"  Вычислено для {len(valid_times)} из {len(trajectory_ids)} траекторий")
    if len(valid_times) > 0:
        print(f"  Среднее время просмотра: {valid_times.mean():.2f} сек (min: {valid_times.min():.2f}, max: {valid_times.max():.2f})")
    
    return df_obs_times


def load_semantic_features():
    """
    Загружает семантические признаки траекторий.
    
    Returns:
        pd.DataFrame: DataFrame с семантическими признаками
    """
    if not SEMANTIC_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {SEMANTIC_FILE}")
    
    df_semantic = pd.read_csv(SEMANTIC_FILE)
    
    # Проверяем наличие всех необходимых колонок
    required_columns = ['trajectory_id', 'duration', 'speed', 'nb_items', 
                        'nb_stops', 'length', 'distwall', 'curvature']
    
    missing_columns = [col for col in required_columns if col not in df_semantic.columns]
    if missing_columns:
        raise ValueError(f"Отсутствуют колонки: {missing_columns}")
    
    # Преобразуем trajectory_id в строку для совместимости
    df_semantic['trajectory_id'] = df_semantic['trajectory_id'].astype(str)
    
    print(f"\nЗагружено семантических признаков для {len(df_semantic)} траекторий")
    print(f"Колонки: {list(df_semantic.columns)}")
    
    return df_semantic


def merge_data(trajectories_df, semantic_df):
    """
    Объединяет траектории с семантическими признаками.
    
    Args:
        trajectories_df: DataFrame с траекториями
        semantic_df: DataFrame с семантическими признаками
    
    Returns:
        pd.DataFrame: Объединенный DataFrame
    """
    # Объединяем по trajectory_id
    merged_df = trajectories_df.merge(
        semantic_df,
        on='trajectory_id',
        how='inner'
    )
    
    print(f"\nОбъединено данных:")
    print(f"  Траекторий: {merged_df['trajectory_id'].nunique()}")
    print(f"  Точек: {len(merged_df)}")
    print(f"  Колонок: {len(merged_df.columns)}")
    
    return merged_df


def main():
    """Основная функция для подготовки данных."""
    print("=" * 60)
    print("ЭТАП 1: Подготовка данных для анализа паттернов поведения")
    print("=" * 60)
    
    # 1.1. Собираем траектории этажа 0
    print("\n[1.1] Загрузка траекторий этажа 0...")
    trajectories_df = load_trajectories_floor0()
    
    # 1.2. Загружаем семантические признаки
    print("\n[1.2] Загрузка семантических признаков...")
    semantic_df = load_semantic_features()
    
    # 1.3. Фильтруем семантические признаки только для траекторий, у которых есть точки на этаже 0
    trajectory_ids_floor0 = set(trajectories_df['trajectory_id'].unique())
    semantic_df_filtered = semantic_df[
        semantic_df['trajectory_id'].isin(trajectory_ids_floor0)
    ].copy()
    
    print(f"\n[1.3] Семантические признаки для траекторий этажа 0: {len(semantic_df_filtered)} из {len(semantic_df)}")
    
    # 1.4. Вычисляем среднее время просмотра объектов
    print("\n[1.4] Вычисление среднего времени просмотра объектов...")
    df_obs_times = compute_avg_observation_times(trajectory_ids_floor0)
    
    # Объединяем с семантическими признаками
    semantic_df_filtered = semantic_df_filtered.merge(
        df_obs_times,
        on='trajectory_id',
        how='left'
    )
    
    print(f"  Добавлен признак avg_observation_time к семантическим данным")
    
    # 1.5. Объединяем данные
    print("\n[1.5] Объединение траекторий с семантическими признаками...")
    merged_df = merge_data(trajectories_df, semantic_df_filtered)
    
    # Сохраняем результаты
    output_file = OUTPUT_DIR / "floor0_trajectories_with_features.csv"
    merged_df.to_csv(output_file, index=False)
    print(f"\n[1.6] Данные сохранены в: {output_file}")
    
    # Сохраняем также отдельно семантические признаки для удобства
    semantic_output = OUTPUT_DIR / "floor0_semantic_features.csv"
    semantic_df_filtered.to_csv(semantic_output, index=False)
    print(f"Семантические признаки сохранены в: {semantic_output}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПОДГОТОВЛЕННЫХ ДАННЫХ:")
    print("=" * 60)
    print(f"Уникальных траекторий: {merged_df['trajectory_id'].nunique()}")
    print(f"Всего точек: {len(merged_df):,}")
    print(f"\nСемантические признаки (средние значения):")
    semantic_cols = ['duration', 'speed', 'nb_items', 'nb_stops', 'length', 'distwall', 'curvature', 'avg_observation_time']
    for col in semantic_cols:
        if col in merged_df.columns:
            # Берем уникальные значения для каждой траектории
            unique_values = merged_df.groupby('trajectory_id')[col].first()
            # Для avg_observation_time могут быть NaN, поэтому фильтруем их
            if col == 'avg_observation_time':
                valid_values = unique_values.dropna()
                if len(valid_values) > 0:
                    print(f"  {col}: {valid_values.mean():.2f} сек (min: {valid_values.min():.2f}, max: {valid_values.max():.2f}, доступно для {len(valid_values)} траекторий)")
                else:
                    print(f"  {col}: нет данных")
            else:
                print(f"  {col}: {unique_values.mean():.2f} (min: {unique_values.min():.2f}, max: {unique_values.max():.2f})")
    
    print("\n" + "=" * 60)
    print("Подготовка данных завершена успешно!")
    print("=" * 60)
    
    return merged_df, semantic_df_filtered


if __name__ == "__main__":
    merged_data, semantic_data = main()
