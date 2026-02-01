"""
Этап 7: Оформление результатов для диплома

7.1 Формальные гипотезы — формулировка и проверка (Kruskal-Wallis по кластерам).
7.2 Визуализации — распределения признаков по кластерам, heatmap посещаемости по типам,
    примеры траекторий по типам (ссылки на существующие + одна диаграмма для гипотез).
7.3 Связь с дальнейшими этапами — архетипы для агентной модели, база для анализа
    влияния архитектуры и демографии.

Вход: analysis_results_merged/floor0_trajectories_clustered_merged.csv
Выход: analysis_results_merged/ (таблицы тестов, диаграмма, отчёт stage7_report_diploma.md)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import kruskal
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

BASE = Path(__file__).resolve().parent
MERGED_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR.mkdir(exist_ok=True)

CLUSTERED_FILE = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"

# Признаки для проверки гипотез (исходные, не _norm)
FEATURES_FOR_HYPOTHESES = ['speed', 'length', 'nb_stops', 'duration', 'nb_items']
FEATURE_LABELS_RU = {
    'speed': 'Скорость',
    'length': 'Длина маршрута',
    'nb_stops': 'Количество остановок',
    'duration': 'Длительность визита',
    'nb_items': 'Число просмотренных экспонатов',
}


def load_data():
    df = pd.read_csv(CLUSTERED_FILE)
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    # одна строка на траекторию
    df = df.drop_duplicates(subset=['trajectory_id'], keep='first')
    return df


def run_kruskal_wallis(df, feature_col, group_col='behavior_type'):
    """Kruskal-Wallis: различаются ли группы (типы) по признаку."""
    groups = [df[df[group_col] == g][feature_col].dropna().values for g in df[group_col].unique()]
    groups = [g for g in groups if len(g) >= 2]
    if len(groups) < 2:
        return np.nan, np.nan
    stat, p = kruskal(*groups)
    return stat, p


def test_hypotheses(df):
    """Проверка гипотез: типы различаются по скорости, длине маршрута, числу остановок и др."""
    results = []
    for feat in FEATURES_FOR_HYPOTHESES:
        if feat not in df.columns:
            continue
        stat, p = run_kruskal_wallis(df, feat)
        results.append({
            'feature': feat,
            'feature_ru': FEATURE_LABELS_RU.get(feat, feat),
            'kruskal_statistic': round(stat, 4) if not np.isnan(stat) else None,
            'p_value': round(p, 6) if not np.isnan(p) else None,
            'reject_H0_005': p < 0.05 if not np.isnan(p) else False,
        })
    return pd.DataFrame(results)


def plot_hypothesis_features(df, output_path):
    """Диаграммы распределения ключевых признаков по типам (для проверки гипотез)."""
    plot_feats = [f for f in FEATURES_FOR_HYPOTHESES if f in df.columns][:5]
    if not plot_feats:
        return
    types = sorted(df['behavior_type'].unique())
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    axes = axes.flatten()
    for i, feat in enumerate(plot_feats):
        ax = axes[i]
        data = [df[df['behavior_type'] == t][feat].dropna().values for t in types]
        bp = ax.boxplot(data, labels=types, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        ax.set_title(FEATURE_LABELS_RU.get(feat, feat))
        ax.set_xlabel('Тип поведения')
        ax.tick_params(axis='x', rotation=15)
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
    fig.suptitle('Распределение признаков по типам поведения (этаж 0)\nПроверка гипотез о различии типов', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def write_report(df, results_df):
    """Пишет отчёт этапа 7: гипотезы, результаты тестов, визуализации, связь с этапами."""
    path = OUTPUT_DIR / "stage7_report_diploma.md"

    # 7.1 Гипотезы и тесты
    lines = [
        "# Этап 7: Оформление результатов для диплома",
        "",
        "## 7.1 Формальные гипотезы и их проверка",
        "",
        "**Гипотезы:**",
        "",
        "1. *H1:* Существуют статистически различимые типы поведения посетителей на этаже 0 по **скорости** перемещения.",
        "2. *H2:* Типы различаются по **длине маршрута** (length).",
        "3. *H3:* Типы различаются по **количеству остановок** (nb_stops).",
        "4. *H4:* Типы различаются по **длительности визита** (duration) и по **числу просмотренных экспонатов** (nb_items).",
        "",
        "**Метод проверки:** непараметрический тест Kruskal–Wallis (сравнение распределений признака между 4 группами — типами поведения). Нулевая гипотеза: распределения одинаковы. Уровень значимости α = 0,05.",
        "",
        "**Результаты:**",
        "",
        "| Признак | Статистика Kruskal-Wallis | p-value | Вывод (α=0,05) |",
        "|---------|---------------------------|---------|----------------|",
    ]
    for _, r in results_df.iterrows():
        pv = r['p_value'] if r['p_value'] is not None else '—'
        dec = "отвергаем H0, типы различаются" if r.get('reject_H0_005') else "нет оснований отвергать H0"
        lines.append(f"| {r['feature_ru']} | {r['kruskal_statistic']} | {pv} | {dec} |")

    lines += [
        "",
        "Файл с численными результатами: `hypothesis_test_results.csv`.",
        "",
        "---",
        "## 7.2 Визуализации",
        "",
        "Для оформления результатов использованы:",
        "",
        "1. **Распределение признаков по кластерам:**",
        "   - `clusters_interpretable_features.png` — проекция кластеров в осях интерпретируемых признаков;",
        "   - `clusters_feature_distributions_merged.png` — распределения признаков по типам;",
        "   - `stage7_hypothesis_features.png` — боксипы ключевых признаков по типам (для проверки гипотез).",
        "",
        "2. **Карты посещаемости (heatmap) по типам поведения на плане этажа 0:**",
        "   - `spatial_heatmaps_by_type.png` — тепловые карты плотности траекторий по типам;",
        "   - `spatial_walls_heatmap_by_type.png` — наблюдаемость экспонатов по стенам по типам.",
        "",
        "3. **Примеры траекторий по типам:**",
        "   - `trajectories_by_behavior_type.png` — траектории, отнесённые к каждому из 4 типов поведения.",
        "",
        "---",
        "## 7.3 Связь с дальнейшими этапами",
        "",
        "Выявленные типы поведения (Активный обходчик, Быстрый, Исследователь, Медленный) используются:",
        "",
        "1. **Как поведенческие архетипы для агентной модели:** параметры агентов (скорость, длительность визита, число осматриваемых экспонатов, предпочтения по зонам и фазам визита) задаются на основе описаний типов из `behavior_types_summary_merged.csv`, пространственного анализа (`spatial_preferences_by_type.csv`, `spatial_observations_by_room_type.csv`, `spatial_observations_by_wall_type.csv`) и временного анализа (`temporal_patterns_by_type.csv`, `temporal_by_quadrant_phase.csv`). Мёртвые и перегруженные зоны (`deadzones_overuse_walls.csv`, `deadzones_overuse_rooms.csv`) задают ограничения по пропускной способности и привлечению внимания.",
        "",
        "2. **Как база для анализа влияния архитектурных и демографических факторов:** типы привязаны к комнатам, стенам и экспонатам (`spatial_observations_by_room_type.csv`, `spatial_observations_by_wall_type.csv`, `spatial_top_exhibits_by_type.csv`); при наличии данных о демографии или об архитектурных изменениях можно оценивать, как меняется доля типов или их пространственно-временные паттерны.",
        "",
        "---",
        "",
        "*Отчёт этапа 7 сформирован скриптом `step7_diploma_report.py`. Исходные данные: этаж 0, 4 типа поведения (после объединения «Быстрый» и «Быстрый краткий»).*",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("=" * 70)
    print("ЭТАП 7: ОФОРМЛЕНИЕ РЕЗУЛЬТАТОВ ДЛЯ ДИПЛОМА")
    print("=" * 70)

    df = load_data()
    print(f"\nЗагружено траекторий: {len(df)}")
    print(f"Типы: {sorted(df['behavior_type'].unique())}")

    # 7.1 Проверка гипотез
    print("\n--- 7.1 Проверка гипотез (Kruskal-Wallis) ---")
    results_df = test_hypotheses(df)
    results_df.to_csv(OUTPUT_DIR / "hypothesis_test_results.csv", index=False)
    for _, r in results_df.iterrows():
        pv = r['p_value']
        dec = "различаются" if r.get('reject_H0_005') else "не различаются"
        print(f"  {r['feature_ru']}: p = {pv}, типы {dec}")

    # 7.2 Визуализация для гипотез
    print("\n--- 7.2 Визуализация признаков по типам ---")
    plot_hypothesis_features(df, OUTPUT_DIR / "stage7_hypothesis_features.png")
    print("  Сохранено: stage7_hypothesis_features.png")

    # 7.3 Отчёт
    write_report(df, results_df)
    print("\nОтчёт: stage7_report_diploma.md")

    print("\n" + "=" * 70)
    print("ЭТАП 7 ЗАВЕРШЁН")
    print("=" * 70)
    print("Результаты в каталоге:", OUTPUT_DIR)
    print("  - hypothesis_test_results.csv")
    print("  - stage7_hypothesis_features.png")
    print("  - stage7_report_diploma.md")


if __name__ == "__main__":
    main()
