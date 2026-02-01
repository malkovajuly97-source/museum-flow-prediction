# Валидация и устойчивость найденных типов (этап 6 по плану)

## 6.1 Устойчивость кластеров

### 6.1.1 Повторные запуски KMeans с разными random_state
- Выполнено 20 запусков KMeans (k=4) с random_state 0..19.
- Эталон: random_state=42.
- ARI каждого запуска с эталоном: среднее 0.9174, ст. откл. 0.0896.
- Файл: `validation_kmeans_stability.csv` (столбцы: random_state, ari_vs_reference, cluster_sizes).

### 6.1.2 Agglomerative Clustering vs KMeans
- AgglomerativeClustering(n_clusters=4, linkage='ward').
- ARI с KMeans(random_state=42): 0.7109.
- Таблица сопряжённости (строки — кластеры KMeans, столбцы — Agglomerative): `validation_agglomerative_vs_kmeans.csv`.

## 6.2 Простая проверка обобщаемости
- Обучение KMeans на 70% траекторий, назначение остальных — по ближайшему центру.
- Тестовых траекторий: 14.
- ARI(эталон на тестовых, назначение по подмножеству) = 0.5051 (по 14 траекториям с эталонной разметкой).
- Распределения признаков по назначенным кластерам для тестовых: `validation_holdout_feature_stats.csv`.
- Назначения по trajectory_id: `validation_holdout_assignments.csv`.

---

*Скрипт: `validate_clustering_stability.py`. Вход: этаж 0, нормализованные признаки, k=4.*