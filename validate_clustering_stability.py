"""
Этап 6 (по плану): Валидация и устойчивость найденных типов

6.1 Устойчивость кластеров:
  - 6.1.1 Запуск KMeans несколько раз с разными random_state, проверка стабильности
    распределения траекторий по кластерам (ARI между запусками, согласованность).
  - 6.1.2 Альтернативный алгоритм (Agglomerative Clustering), сравнение структуры типов с KMeans.

6.2 Простая проверка обобщаемости:
  - Обучение кластеризации на подмножестве траекторий; проверка, разумно ли классифицируются
    оставшиеся (по распределениям признаков и согласию с эталонной разметкой).

Вход: analysis_results/floor0_behavioral_features_normalized.csv, features_for_clustering.csv.
Выход: analysis_results_merged/ (таблицы и отчёт по валидации).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

BASE = Path(__file__).resolve().parent
INPUT_DIR = BASE / "analysis_results"
MERGED_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR = BASE / "analysis_results_merged"
OUTPUT_DIR.mkdir(exist_ok=True)

NORMALIZED_FILE = INPUT_DIR / "floor0_behavioral_features_normalized.csv"
FEATURES_FILE = INPUT_DIR / "features_for_clustering.csv"
REFERENCE_CLUSTERED = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"

K_CLUSTERS = 4
N_STABILITY_RUNS = 20
TRAIN_FRACTION = 0.7
REFERENCE_RANDOM_STATE = 42


def load_data():
    """Загружает нормализованные признаки и список колонок для кластеризации."""
    df = pd.read_csv(NORMALIZED_FILE)
    df['trajectory_id'] = df['trajectory_id'].astype(str)
    if FEATURES_FILE.exists():
        f = pd.read_csv(FEATURES_FILE)
        cols = [c for c in f['normalized_column'].tolist() if c in df.columns]
    else:
        cols = [c for c in df.columns if c.endswith('_norm')]
    X = df[cols].values
    return df, cols, X


def stability_kmeans(X, n_runs=N_STABILITY_RUNS, k=K_CLUSTERS, ref_seed=REFERENCE_RANDOM_STATE):
    """6.1.1: Запуск KMeans с разными random_state, ARI относительно эталонного запуска."""
    kmeans_ref = KMeans(n_clusters=k, random_state=ref_seed, n_init=20)
    labels_ref = kmeans_ref.fit_predict(X)
    results = []
    for seed in range(n_runs):
        km = KMeans(n_clusters=k, random_state=seed, n_init=20)
        lab = km.fit_predict(X)
        ari = adjusted_rand_score(labels_ref, lab)
        sizes = [np.sum(lab == i) for i in range(k)]
        results.append({'random_state': seed, 'ari_vs_reference': round(ari, 4), 'cluster_sizes': tuple(sizes)})
    return pd.DataFrame(results), labels_ref


def agglomerative_vs_kmeans(X, k=K_CLUSTERS, kmeans_seed=REFERENCE_RANDOM_STATE):
    """6.1.2: AgglomerativeClustering n_clusters=k, сравнение с KMeans (ARI, таблица сопряжённости)."""
    km = KMeans(n_clusters=k, random_state=kmeans_seed, n_init=20)
    lab_km = km.fit_predict(X)
    ac = AgglomerativeClustering(n_clusters=k, linkage='ward')
    lab_ac = ac.fit_predict(X)
    ari = adjusted_rand_score(lab_km, lab_ac)
    # Таблица сопряжённости: строка = KMeans cluster, столбец = Agglomerative cluster
    cont = pd.crosstab(lab_km, lab_ac)
    return ari, cont, lab_km, lab_ac


def generalization_holdout(df, cols, X, k=K_CLUSTERS, train_frac=TRAIN_FRACTION, seed=REFERENCE_RANDOM_STATE):
    """6.2: Обучить KMeans на подмножестве траекторий; для остальных — назначить ближайший центр. Оценить по признакам."""
    n = len(df)
    np.random.seed(seed)
    idx = np.random.permutation(n)
    n_train = max(1, int(n * train_frac))
    train_idx, test_idx = idx[:n_train], idx[n_train:]
    X_train, X_test = X[train_idx], X[test_idx]
    ids_test = df['trajectory_id'].iloc[test_idx].values

    km = KMeans(n_clusters=k, random_state=seed, n_init=20)
    km.fit(X_train)
    # Назначение тестовых траекторий ближайшему центру
    dist = np.linalg.norm(X_test[:, np.newaxis] - km.cluster_centers_, axis=2)
    assigned = np.argmin(dist, axis=1)

    # Распределения признаков по назначенным кластерам для тестовых
    df_test = df.iloc[test_idx].copy()
    df_test['assigned_cluster'] = assigned
    # Ключевые признаки для отчёта
    key = [c for c in ['speed', 'duration', 'nb_items', 'nb_stops'] if c in df_test.columns]
    if not key:
        key = [c.replace('_norm', '') for c in cols if c.replace('_norm', '') in df_test.columns][:4]
    stats = df_test.groupby('assigned_cluster')[key].agg(['mean', 'std', 'count']).round(4)
    return df_test, stats, km, train_idx, test_idx


def run_and_save():
    print("=" * 70)
    print("ЭТАП 6: ВАЛИДАЦИЯ И УСТОЙЧИВОСТЬ НАЙДЕННЫХ ТИПОВ")
    print("=" * 70)

    df, cols, X = load_data()
    n, d = X.shape
    print(f"\nТраекторий: {n}, признаков для кластеризации: {d}")

    # ---- 6.1.1 Устойчивость по random_state ----
    print("\n--- 6.1.1 Устойчивость кластеров (несколько запусков KMeans, разные random_state) ---")
    stab_df, labels_ref = stability_kmeans(X, n_runs=N_STABILITY_RUNS, k=K_CLUSTERS)
    stab_df.to_csv(OUTPUT_DIR / "validation_kmeans_stability.csv", index=False)
    print(f"  ARI относительно эталона (random_state={REFERENCE_RANDOM_STATE}): mean={stab_df['ari_vs_reference'].mean():.4f}, std={stab_df['ari_vs_reference'].std():.4f}")
    print(f"  Сохранено: validation_kmeans_stability.csv")

    # ---- 6.1.2 Agglomerative vs KMeans ----
    print("\n--- 6.1.2 Альтернативный алгоритм (Agglomerative Clustering) vs KMeans ---")
    ari_ag, cont, lab_km, lab_ac = agglomerative_vs_kmeans(X, k=K_CLUSTERS)
    cont.to_csv(OUTPUT_DIR / "validation_agglomerative_vs_kmeans.csv")
    print(f"  ARI(KMeans, Agglomerative) = {ari_ag:.4f}")
    print(f"  Таблица сопряжённости сохранена: validation_agglomerative_vs_kmeans.csv")

    # ---- 6.2 Обобщаемость (обучение на подмножестве) ----
    print("\n--- 6.2 Проверка обобщаемости (обучение на подмножестве, классификация остальных) ---")
    df_holdout, stats_holdout, km_holdout, train_idx, test_idx = generalization_holdout(df, cols, X, k=K_CLUSTERS, train_frac=TRAIN_FRACTION)
    df_holdout[['trajectory_id', 'assigned_cluster']].to_csv(OUTPUT_DIR / "validation_holdout_assignments.csv", index=False)
    stats_holdout.to_csv(OUTPUT_DIR / "validation_holdout_feature_stats.csv")
    print(f"  Обучающая выборка: {len(train_idx)} траекторий, тестовая: {len(test_idx)}")
    print(f"  Распределения признаков по назначенным кластерам для тестовых сохранены: validation_holdout_feature_stats.csv")

    ari_holdout = None
    n_holdout_matched = 0
    if REFERENCE_CLUSTERED.exists():
        ref = pd.read_csv(REFERENCE_CLUSTERED)
        ref['trajectory_id'] = ref['trajectory_id'].astype(str)
        type_to_id = {t: i for i, t in enumerate(sorted(ref['behavior_type'].unique()))}
        ref['ref_label'] = ref['behavior_type'].map(type_to_id)
        ref_map = ref.set_index('trajectory_id')['ref_label'].to_dict()
        holdout_ids = df_holdout['trajectory_id'].tolist()
        ref_holdout = np.array([ref_map.get(tid, -1) for tid in holdout_ids])
        mask = ref_holdout >= 0
        n_holdout_matched = int(mask.sum())
        if n_holdout_matched > 0:
            ari_holdout = adjusted_rand_score(ref_holdout[mask], df_holdout['assigned_cluster'].values[mask])
            print(f"  ARI(эталон на тестовых, назначение по обучению на подмножестве) = {ari_holdout:.4f} (по {n_holdout_matched} траекториям)")

    # ---- Краткий отчёт ----
    report = [
        "# Валидация и устойчивость найденных типов (этап 6 по плану)",
        "",
        "## 6.1 Устойчивость кластеров",
        "",
        "### 6.1.1 Повторные запуски KMeans с разными random_state",
        f"- Выполнено {N_STABILITY_RUNS} запусков KMeans (k={K_CLUSTERS}) с random_state 0..{N_STABILITY_RUNS-1}.",
        f"- Эталон: random_state={REFERENCE_RANDOM_STATE}.",
        f"- ARI каждого запуска с эталоном: среднее {stab_df['ari_vs_reference'].mean():.4f}, ст. откл. {stab_df['ari_vs_reference'].std():.4f}.",
        "- Файл: `validation_kmeans_stability.csv` (столбцы: random_state, ari_vs_reference, cluster_sizes).",
        "",
        "### 6.1.2 Agglomerative Clustering vs KMeans",
        f"- AgglomerativeClustering(n_clusters={K_CLUSTERS}, linkage='ward').",
        f"- ARI с KMeans(random_state={REFERENCE_RANDOM_STATE}): {ari_ag:.4f}.",
        "- Таблица сопряжённости (строки — кластеры KMeans, столбцы — Agglomerative): `validation_agglomerative_vs_kmeans.csv`.",
        "",
        "## 6.2 Простая проверка обобщаемости",
        f"- Обучение KMeans на {TRAIN_FRACTION*100:.0f}% траекторий, назначение остальных — по ближайшему центру.",
        f"- Тестовых траекторий: {len(test_idx)}.",
    ]
    if ari_holdout is not None:
        report.append(f"- ARI(эталон на тестовых, назначение по подмножеству) = {ari_holdout:.4f} (по {n_holdout_matched} траекториям с эталонной разметкой).")
    report += [
        "- Распределения признаков по назначенным кластерам для тестовых: `validation_holdout_feature_stats.csv`.",
        "- Назначения по trajectory_id: `validation_holdout_assignments.csv`.",
        "",
        "---",
        "",
        "*Скрипт: `validate_clustering_stability.py`. Вход: этаж 0, нормализованные признаки, k=4.*",
    ]
    (OUTPUT_DIR / "validation_report_6.md").write_text("\n".join(report), encoding="utf-8")
    print("\nОтчёт: validation_report_6.md")

    print("\n" + "=" * 70)
    print("ВАЛИДАЦИЯ (ЭТАП 6) ЗАВЕРШЕНА")
    print("=" * 70)


if __name__ == "__main__":
    run_and_save()
