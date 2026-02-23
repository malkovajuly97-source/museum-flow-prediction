"""
Проверка различий признаков планировки и изовиста по типам поведения.

Объединяет типы поведения (из кластеризации) с признаками планировки и изовиста,
проверяет по каждому признаку наличие различий между типами (Kruskal-Wallis)
и формирует вывод: тип-специфичные настройки или общая модель.

Входы:
  - analysis_results_merged/floor0_trajectories_clustered_merged.csv (trajectory_id, behavior_type)
  - model_search/Openness and size of the space/layout_and_movement.csv
  - model_search/Isovist/isovist_and_movement.csv (опционально)

Выходы (model_search/Openness and size of the space/openness_analysis/):
  - layout_by_behavior_type_kruskal.csv
  - layout_by_behavior_type_means.csv
  - layout_by_behavior_type_report.md
  - layout_by_behavior_type_boxplot.png
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import kruskal

BASE = Path(__file__).resolve().parent
MERGED_DIR = BASE / "analysis_results_merged"
OPENNESS_DIR = BASE / "model_search" / "Openness and size of the space"
ISOVIST_DIR = BASE / "model_search" / "Isovist"
OUTPUT_DIR = OPENNESS_DIR / "openness_analysis"

CLUSTERED_CSV = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"
LAYOUT_CSV = OPENNESS_DIR / "layout_and_movement.csv"
ISOVIST_CSV = ISOVIST_DIR / "isovist_and_movement.csv"

# Признаки движения — не проверяем (типы по ним определены)
MOVEMENT_COLS = {"speed", "duration", "nb_stops", "nb_items", "length", "stop_intensity"}

# Доп. колонки, которые не являются признаками планировки/изовиста
SKIP_COLS = {
    "trajectory_id", "behavior_type", "curvature", "avg_observation_time",
    "n_points", "n_points_x", "n_points_y", "distwall",
}

# Ключевые признаки для boxplot (если есть в данных)
BOXPLOT_FEATURES = [
    "H3_pct_low_connectivity",
    "H8_pct_path_revisit",
    "passage_width_mean",
    "isovist_area_mean",
]


def run_kruskal_wallis(df: pd.DataFrame, feature_col: str, group_col: str = "behavior_type"):
    """Kruskal-Wallis: различаются ли группы (типы) по признаку."""
    groups = [
        df.loc[df[group_col] == g, feature_col].dropna().values
        for g in df[group_col].unique()
    ]
    groups = [g for g in groups if len(g) >= 2]
    if len(groups) < 2:
        return np.nan, np.nan
    stat, p = kruskal(*groups)
    return stat, p


def load_and_merge():
    """Загрузка кластеров, планировки и изовиста; слияние по trajectory_id."""
    if not CLUSTERED_CSV.exists():
        raise FileNotFoundError(f"Не найден: {CLUSTERED_CSV}. Запустите кластеризацию и merge.")
    df_clustered = pd.read_csv(CLUSTERED_CSV)
    df_clustered["trajectory_id"] = df_clustered["trajectory_id"].astype(str)
    df_clustered = df_clustered[["trajectory_id", "behavior_type"]].drop_duplicates(
        subset=["trajectory_id"], keep="first"
    )

    if not LAYOUT_CSV.exists():
        raise FileNotFoundError(f"Не найден: {LAYOUT_CSV}. Запустите layout_hypotheses.py.")
    df_layout = pd.read_csv(LAYOUT_CSV)
    df_layout["trajectory_id"] = df_layout["trajectory_id"].astype(str)

    df = df_clustered.merge(df_layout, on="trajectory_id", how="inner")
    print(f"  После merge с layout: {len(df)} траекторий")

    if ISOVIST_CSV.exists():
        df_iso = pd.read_csv(ISOVIST_CSV)
        df_iso["trajectory_id"] = df_iso["trajectory_id"].astype(str)
        iso_cols = [c for c in df_iso.columns if c != "trajectory_id" and c.startswith("isovist_")]
        if iso_cols:
            df_iso = df_iso[["trajectory_id"] + iso_cols].drop_duplicates(subset=["trajectory_id"], keep="first")
            df = df.merge(df_iso, on="trajectory_id", how="left")
            print(f"  Добавлен изовист: {len(iso_cols)} признаков")
    else:
        print("  Файл изовиста не найден — проверка только по признакам планировки.")

    return df


def get_features_to_test(df: pd.DataFrame):
    """Список признаков планировки и изовиста для теста (без движения и служебных)."""
    layout_prefixes = tuple(f"H{i}_" for i in range(2, 13))
    openness_extra = {"passage_width_mean", "zone_area_mean", "pct_small_zone", "pct_large_zone"}
    isovist_names = {
        "isovist_area_mean", "isovist_area_min", "isovist_area_max",
        "isovist_area_range", "isovist_perimeter_mean",
    }
    skip = MOVEMENT_COLS | SKIP_COLS
    features = []
    for c in df.columns:
        if c in skip or c == "trajectory_id" or c == "behavior_type":
            continue
        if c.startswith(layout_prefixes):
            features.append(c)
        elif c in openness_extra or c in isovist_names:
            features.append(c)
    return sorted(set(features))


def main():
    print("Проверка различий планировки/изовиста по типам поведения")
    print("Загрузка и слияние...")
    df = load_and_merge()
    features = get_features_to_test(df)
    print(f"  Признаков для проверки: {len(features)}")

    # Kruskal-Wallis по каждому признаку
    results = []
    for feat in features:
        if feat not in df.columns or df[feat].isna().all():
            continue
        stat, p = run_kruskal_wallis(df, feat)
        results.append({
            "feature": feat,
            "kruskal_statistic": round(stat, 6) if not np.isnan(stat) else None,
            "p_value": round(p, 6) if not np.isnan(p) else None,
            "significant_005": p < 0.05 if not np.isnan(p) else False,
        })
    df_kruskal = pd.DataFrame(results)

    # Средние и медианы по типам
    means_rows = []
    for feat in features:
        if feat not in df.columns:
            continue
        for bt in sorted(df["behavior_type"].unique()):
            vals = df.loc[df["behavior_type"] == bt, feat].dropna()
            means_rows.append({
                "feature": feat,
                "behavior_type": bt,
                "mean": round(vals.mean(), 6) if len(vals) else np.nan,
                "median": round(vals.median(), 6) if len(vals) else np.nan,
                "n": len(vals),
            })
    df_means = pd.DataFrame(means_rows)

    # Сохранение
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_kruskal.to_csv(OUTPUT_DIR / "layout_by_behavior_type_kruskal.csv", index=False)
    df_means.to_csv(OUTPUT_DIR / "layout_by_behavior_type_means.csv", index=False)
    print(f"  Сохранено: layout_by_behavior_type_kruskal.csv, layout_by_behavior_type_means.csv")

    # Отчёт
    n_sig = df_kruskal["significant_005"].sum()
    n_total = len(df_kruskal)
    sig_features = df_kruskal.loc[df_kruskal["significant_005"], "feature"].tolist()
    if n_sig > 0:
        recommendation = (
            "По данным есть достоверные отличия по признакам планировки/изовиста между типами поведения. "
            "Имеет смысл добавлять доп. настройки по типам (тип-специфичные параметры в агентной модели)."
        )
    else:
        recommendation = (
            "Достоверных отличий по проверенным признакам планировки/изовиста между типами не выявлено. "
            "Имеет смысл задавать общую модель поведения от планировки для всех агентов."
        )

    report_lines = [
        "# Различия признаков планировки и изовиста по типам поведения",
        "",
        f"Проверено признаков: **{n_total}**. Значимых при α = 0.05: **{n_sig}**.",
        "",
        "## Значимые признаки (p < 0.05)",
        "",
    ]
    if sig_features:
        for f in sig_features:
            row = df_kruskal[df_kruskal["feature"] == f].iloc[0]
            report_lines.append(f"- **{f}** (p = {row['p_value']})")
    else:
        report_lines.append("Нет.")
    report_lines.extend([
        "",
        "## Рекомендация",
        "",
        recommendation,
        "",
        "---",
        "",
        "Файлы: `layout_by_behavior_type_kruskal.csv`, `layout_by_behavior_type_means.csv`.",
    ])
    report_path = OUTPUT_DIR / "layout_by_behavior_type_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"  Сохранено: layout_by_behavior_type_report.md")

    # Boxplot по 2–4 ключевым признакам
    plot_features = [f for f in BOXPLOT_FEATURES if f in df.columns][:4]
    if plot_features:
        import matplotlib.pyplot as plt
        types = sorted(df["behavior_type"].unique())
        n_plots = len(plot_features)
        ncols = 2
        nrows = (n_plots + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(10, 4 * nrows))
        axes = np.atleast_2d(axes)
        for idx, feat in enumerate(plot_features):
            ax = axes[idx // ncols, idx % ncols]
            data = [df.loc[df["behavior_type"] == t, feat].dropna().values for t in types]
            bp = ax.boxplot(data, tick_labels=types, patch_artist=True)
            for patch in bp["boxes"]:
                patch.set_facecolor("lightblue")
            ax.set_title(feat)
            ax.tick_params(axis="x", rotation=15)
        for j in range(len(plot_features), axes.size):
            axes.flat[j].set_visible(False)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "layout_by_behavior_type_boxplot.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Сохранено: layout_by_behavior_type_boxplot.png")

    print("Готово.")


if __name__ == "__main__":
    main()
