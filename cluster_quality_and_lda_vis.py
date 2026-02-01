"""
Практические рекомендации: проверка качества кластеров и визуализации

1. Проверка качества кластеров в полном пространстве признаков (silhouette)
2. Визуализация в осях 2–3 наиболее интерпретируемых признаков
3. Визуализация тех же кластеров в осях LDA (линейный дискриминантный анализ)

Результаты сохраняются в analysis_results_merged/
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings('ignore')

# Пути
MERGED_DIR = Path("analysis_results_merged")
OUTPUT_DIR = Path("analysis_results_merged")
OUTPUT_DIR.mkdir(exist_ok=True)

CLUSTERED_FILE = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"


def load_data():
    """Загружает данные с кластерами и готовит матрицу признаков."""
    df = pd.read_csv(CLUSTERED_FILE)
    df['trajectory_id'] = df['trajectory_id'].astype(str)

    norm_cols = [c for c in df.columns if c.endswith('_norm')]
    feat_cols = [c.replace('_norm', '') for c in norm_cols if c.replace('_norm', '') in df.columns]
    # используем именно нормализованные для согласованности с кластеризацией
    norm_cols = [c for c in norm_cols if c in df.columns]

    X = df[norm_cols].fillna(0).values
    labels = df['behavior_type'].values
    return df, X, labels, norm_cols, feat_cols


def check_cluster_quality(X, labels):
    """Оценка качества кластеров в полном пространстве: silhouette."""
    print("=" * 60)
    print("1. КАЧЕСТВО КЛАСТЕРОВ В ПОЛНОМ ПРОСТРАНСТВЕ")
    print("=" * 60)

    sil_global = silhouette_score(X, labels)
    sil_per_sample = silhouette_samples(X, labels)
    unique_labels = np.unique(labels)

    print(f"\nSilhouette score (общий): {sil_global:.4f}")
    print("\nSilhouette по кластерам (среднее по объектам кластера):")
    res = []
    for lb in unique_labels:
        mask = labels == lb
        s = sil_per_sample[mask].mean()
        n = mask.sum()
        res.append({"behavior_type": lb, "silhouette_mean": s, "n": n})
        print(f"  {lb}: {s:.4f}  (n={n})")

    df_sil = pd.DataFrame(res)
    out = OUTPUT_DIR / "cluster_quality_silhouette.csv"
    df_sil.to_csv(out, index=False)
    print(f"\nСохранено: {out}")
    return sil_global, df_sil


def plot_interpretable_features(df, behavior_type_col='behavior_type'):
    """Визуализация кластеров в осях 2–3 интерпретируемых признаков."""
    print("\n" + "=" * 60)
    print("2. ВИЗУАЛИЗАЦИЯ ПО ИНТЕРПРЕТИРУЕМЫМ ПРИЗНАКАМ")
    print("=" * 60)

    pairs = [
        ('speed', 'duration', 'Скорость vs Длительность'),
        ('nb_stops', 'nb_items', 'Остановки vs Экспонаты'),
        ('speed', 'nb_items', 'Скорость vs Экспонаты'),
        ('duration', 'nb_stops', 'Длительность vs Остановки'),
    ]
    pairs = [(x, y, t) for x, y, t in pairs if x in df.columns and y in df.columns]

    n_plots = len(pairs)
    n_cols = 2
    n_rows = (n_plots + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 5 * n_rows))
    axes = np.atleast_2d(axes)

    types = sorted(df[behavior_type_col].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(types)))
    color_map = dict(zip(types, colors))

    for idx, (x_col, y_col, title) in enumerate(pairs):
        ax = axes.flat[idx]
        for bt in types:
            m = df[behavior_type_col] == bt
            ax.scatter(
                df.loc[m, x_col], df.loc[m, y_col],
                c=[color_map[bt]], label=bt, alpha=0.7, s=60, edgecolors='black', linewidths=0.5
            )
        ax.set_xlabel(x_col, fontsize=11)
        ax.set_ylabel(y_col, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)

    for j in range(n_plots, axes.size):
        axes.flat[j].set_visible(False)

    plt.tight_layout()
    out = OUTPUT_DIR / "clusters_interpretable_features.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Сохранено: {out}")


def plot_lda(X, labels, df):
    """Визуализация кластеров в осях LDA (максимизация разделения по известным классам)."""
    print("\n" + "=" * 60)
    print("3. ВИЗУАЛИЗАЦИЯ В ОСЯХ LDA")
    print("=" * 60)

    le = LabelEncoder()
    y = le.fit_transform(labels)

    n_classes = len(le.classes_)
    n_comp = min(2, n_classes - 1, X.shape[1])
    if n_comp < 2:
        print("LDA: для 2D нужны минимум 2 класса и 2 компоненты. Пропуск.")
        return

    lda = LinearDiscriminantAnalysis(n_components=n_comp)
    X_lda = lda.fit_transform(X, y)

    fig, ax = plt.subplots(figsize=(10, 8))
    types = list(le.classes_)
    colors = plt.cm.Set3(np.linspace(0, 1, len(types)))

    for i, bt in enumerate(types):
        mask = labels == bt
        ax.scatter(
            X_lda[mask, 0], X_lda[mask, 1],
            c=[colors[i]], label=bt, s=100, alpha=0.7, edgecolors='black', linewidths=1
        )

    ax.set_xlabel(f'LD1 ({lda.explained_variance_ratio_[0]*100:.1f}% variance)' if hasattr(lda, 'explained_variance_ratio_') and len(lda.explained_variance_ratio_) > 0 else 'LD1', fontsize=12)
    if n_comp > 1 and hasattr(lda, 'explained_variance_ratio_') and len(lda.explained_variance_ratio_) > 1:
        ax.set_ylabel(f'LD2 ({lda.explained_variance_ratio_[1]*100:.1f}% variance)', fontsize=12)
    else:
        ax.set_ylabel('LD2', fontsize=12)
    ax.set_title('Кластеры в осях LDA (линейный дискриминантный анализ)', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = OUTPUT_DIR / "clusters_lda_visualization.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Сохранено: {out}")

    # пояснение по дисперсии LDA (если есть)
    if hasattr(lda, 'explained_variance_ratio_'):
        evr = lda.explained_variance_ratio_
        print(f"Доля межклассовой дисперсии: LD1={evr[0]*100:.1f}%", end="")
        if len(evr) > 1:
            print(f", LD2={evr[1]*100:.1f}%")
        else:
            print()


def main():
    print("Практические рекомендации: качество кластеров и визуализации\n")

    df, X, labels, norm_cols, feat_cols = load_data()
    print(f"Объектов: {len(df)}, признаков: {X.shape[1]}, кластеров: {len(np.unique(labels))}")

    check_cluster_quality(X, labels)
    plot_interpretable_features(df, behavior_type_col='behavior_type')
    plot_lda(X, labels, df)

    print("\n" + "=" * 60)
    print("Готово. Результаты в каталоге:", OUTPUT_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
