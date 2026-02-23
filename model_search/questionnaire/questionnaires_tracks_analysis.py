"""
Проверка зависимостей «треки + анкеты»: объединение по visitor_id,
корреляции, scatter и boxplot, краткий отчёт.

Скрипт в model_search/questionnaire/.
Входы: layout_and_movement.csv, pre/post анкеты из data/questionnaires/.
Выходы: questionnaires_and_tracks.csv, correlation_matrix.csv, analysis/, interpretation_tracks_ru.md.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent

LAYOUT_AND_MOVEMENT = PROJECT_ROOT / "model_search/Openness and size of the space/layout_and_movement.csv"

def _questionnaire_paths():
    base = PROJECT_ROOT / "data" / "questionnaires"
    candidates = [
        PROJECT_ROOT / "bird-dataset-main" / "data" / "questionnaires",
        base,
        PROJECT_ROOT.parent / "bird-dataset-main" / "data" / "questionnaires",
        Path.cwd() / "data" / "questionnaires",
        Path.cwd() / "bird-dataset-main" / "data" / "questionnaires",
    ]
    for root in candidates:
        pre = root / "pre_questionnaire_formatted.csv"
        post = root / "post_questionnaire_formatted.csv"
        if pre.exists():
            return pre, post
    return base / "pre_questionnaire_formatted.csv", base / "post_questionnaire_formatted.csv"

PRE_QUESTIONNAIRE, POST_QUESTIONNAIRE = _questionnaire_paths()

OUTPUT_DIR = BASE
MERGED_CSV = OUTPUT_DIR / "questionnaires_and_tracks.csv"
CORR_CSV = OUTPUT_DIR / "correlation_matrix.csv"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"
ANALYSIS_DIR.mkdir(exist_ok=True)
INTERPRETATION_MD = OUTPUT_DIR / "interpretation_tracks_ru.md"

# Метрики треков для анализа (после merge: speed -> speed_track)
TRACK_COLS = ["speed", "nb_stops", "duration", "nb_items", "length", "stop_intensity"]
TRACK_COLS_MERGED = ["speed_track", "nb_stops", "duration", "nb_items", "length", "stop_intensity"]

# Числовые/ординальные колонки анкет (pre) — уже числа или легко привести
PRE_NUMERIC = [
    "age", "one_artwork_interest", "discovery_interest", "crowd_tolerance",
    "lose_interest_with_crowd", "distance_tolerance", "physical_sleepiness",
    "mental_sleepiness", "speed", "current_emotion",
]
# Post числовые
POST_NUMERIC = [
    "satisfaction", "goals_reached", "device_trouble", "crowd_trouble",
    "dist_sensation", "end_visit_physical_sleepiness", "end_visit_mental_sleepiness", "panel_interest",
]
# Категории для групповых сравнений (кодируем или оставляем как есть для boxplot)
PRE_CATEGORICAL = ["gender", "visit_duration", "group_or_alone"]


def load_and_merge():
    """Загрузка layout_and_movement, pre и post; объединение по visitor_id = trajectory_id."""
    df_tracks = pd.read_csv(LAYOUT_AND_MOVEMENT)
    df_tracks["trajectory_id"] = df_tracks["trajectory_id"].astype(str)

    df_pre = pd.read_csv(PRE_QUESTIONNAIRE)
    df_pre["visitor_id"] = df_pre["visitor_id"].astype(str)

    df_post = pd.read_csv(POST_QUESTIONNAIRE)
    df_post["visitor_id"] = df_post["visitor_id"].astype(str)

    # Треки + pre (inner)
    merged = df_tracks.merge(
        df_pre,
        left_on="trajectory_id",
        right_on="visitor_id",
        how="inner",
        suffixes=("_track", "_pre"),
    )
    # + post (left, чтобы не терять тех, у кого нет post)
    merged = merged.merge(
        df_post,
        on="visitor_id",
        how="left",
        suffixes=("", "_post"),
    )
    return merged


def ensure_numeric(merged):
    """Привести выбранные колонки анкет к числу; категории закодировать для корреляций."""
    df = merged.copy()
    for col in PRE_NUMERIC + POST_NUMERIC:
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # visit_duration: unlimited vs limited для групповых сравнений
    if "visit_duration" in df.columns:
        df["visit_duration_limited"] = (df["visit_duration"].astype(str).str.lower() != "unlimited").astype(int)
    # gender для корреляции: 0/1 (woman=0, man=1)
    if "gender" in df.columns:
        g = df["gender"].astype(str).str.strip().str.lower()
        df["gender_code"] = (g == "man").astype(int)
        df.loc[~g.isin(["man", "woman"]), "gender_code"] = np.nan
    return df


def run_correlations(df):
    """Корреляционная матрица: метрики треков + числовые/закодированные переменные анкет."""
    track_cols = [c for c in TRACK_COLS_MERGED if c in df.columns]
    if not track_cols and "speed" in df.columns:
        track_cols = [c for c in TRACK_COLS if c in df.columns]
    pre_cols = [c for c in PRE_NUMERIC if c in df.columns]
    if "speed_pre" in df.columns and "speed_pre" not in pre_cols:
        pre_cols = [c for c in pre_cols if c != "speed"] + ["speed_pre"]
    post_cols = [c for c in POST_NUMERIC if c in df.columns]
    extra = []
    if "visit_duration_limited" in df.columns:
        extra.append("visit_duration_limited")
    if "gender_code" in df.columns:
        extra.append("gender_code")
    analysis_cols = track_cols + [c for c in pre_cols if c in df.columns] + post_cols + extra
    analysis_cols = [c for c in analysis_cols if c in df.columns]
    num = df[analysis_cols].apply(pd.to_numeric, errors="coerce")
    corr = num.corr()
    return corr, num


def main():
    print("=" * 60)
    print("Questionnaires + Tracks: merge and analysis")
    print("=" * 60)

    if not LAYOUT_AND_MOVEMENT.exists():
        print(f"Not found: {LAYOUT_AND_MOVEMENT}")
        return
    if not PRE_QUESTIONNAIRE.exists():
        print(f"Not found: {PRE_QUESTIONNAIRE}")
        return

    # 1. Merge
    merged = load_and_merge()
    print(f"Merged rows (tracks + pre, with/without post): {len(merged)}")

    merged = ensure_numeric(merged)
    if "speed_track" not in merged.columns and "speed" in merged.columns:
        merged["speed_track"] = merged["speed"]
    if "speed_pre" not in merged.columns and "speed" in merged.columns:
        merged["speed_pre"] = merged["speed"]

    merged.to_csv(MERGED_CSV, index=False)
    print(f"Saved: {MERGED_CSV}")

    # 2. Correlations
    corr, num_df = run_correlations(merged)
    corr.to_csv(CORR_CSV)
    print(f"Saved: {CORR_CSV}")

    # Correlation heatmap
    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(corr.columns, fontsize=7)
    plt.colorbar(im, ax=ax, shrink=0.8)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=5)
    ax.set_title("Correlations: tracks vs questionnaires")
    plt.tight_layout()
    plt.savefig(ANALYSIS_DIR / "correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {ANALYSIS_DIR / 'correlation_heatmap.png'}")

    # 3. Scatter and boxplot
    track_cols = [c for c in TRACK_COLS if c in merged.columns]
    if "speed_track" in merged.columns:
        track_cols = ["speed_track"] + [c for c in track_cols if c != "speed_track" and c != "speed"]
    else:
        track_cols = [c for c in track_cols if c in merged.columns]

    if "speed_track" in merged.columns and "speed_pre" in merged.columns:
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.scatter(merged["speed_pre"], merged["speed_track"], alpha=0.7)
        ax.set_xlabel("Speed (pre, self-reported 1-5)")
        ax.set_ylabel("Speed (track)")
        ax.set_title("Track speed vs self-reported speed (pre)")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(ANALYSIS_DIR / "scatter_speed_track_vs_pre.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved: {ANALYSIS_DIR / 'scatter_speed_track_vs_pre.png'}")

    for y_col in ["nb_stops", "speed_track"]:
        if y_col not in merged.columns or "satisfaction" not in merged.columns:
            continue
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.scatter(merged["satisfaction"], merged[y_col], alpha=0.7)
        ax.set_xlabel("Satisfaction (post)")
        ax.set_ylabel(y_col)
        ax.set_title(f"Satisfaction vs {y_col}")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(ANALYSIS_DIR / f"scatter_satisfaction_vs_{y_col.replace(' ', '_')}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved: analysis/scatter_satisfaction_vs_{y_col}.png")

    if "discovery_interest" in merged.columns:
        for y_col in ["nb_items", "nb_stops"]:
            if y_col not in merged.columns:
                continue
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.scatter(merged["discovery_interest"], merged[y_col], alpha=0.7)
            ax.set_xlabel("Discovery interest (pre)")
            ax.set_ylabel(y_col)
            ax.set_title(f"Discovery interest vs {y_col}")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / f"scatter_discovery_interest_vs_{y_col}.png", dpi=150, bbox_inches="tight")
            plt.close()
        print("Saved: analysis/scatter_discovery_interest_vs_*.png")

    if "gender" in merged.columns and "speed_track" in merged.columns:
        df_g = merged.dropna(subset=["gender"])
        df_g = df_g[df_g["gender"].astype(str).str.lower().isin(["man", "woman"])]
        if len(df_g) > 0:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            for ax, var in zip(axes, ["speed_track", "nb_stops"]):
                if var not in merged.columns:
                    ax.set_visible(False)
                    continue
                df_g.boxplot(column=var, by="gender", ax=ax)
                ax.set_title(f"{var} by gender")
                ax.set_xlabel("Gender")
            plt.suptitle("")
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / "boxplot_track_metrics_by_gender.png", dpi=150, bbox_inches="tight")
            plt.close()
            print("Saved: analysis/boxplot_track_metrics_by_gender.png")

    if "satisfaction" in merged.columns and "speed_track" in merged.columns:
        m = merged["satisfaction"].median()
        merged_copy = merged.copy()
        merged_copy["satisfaction_hl"] = (merged_copy["satisfaction"] >= m).map({True: "high", False: "low"})
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for ax, var in zip(axes, ["speed_track", "nb_stops"]):
            if var not in merged_copy.columns:
                ax.set_visible(False)
                continue
            merged_copy.boxplot(column=var, by="satisfaction_hl", ax=ax)
            ax.set_title(f"{var} by satisfaction (median split)")
            ax.set_xlabel("Satisfaction")
        plt.suptitle("")
        plt.tight_layout()
        plt.savefig(ANALYSIS_DIR / "boxplot_track_metrics_by_satisfaction.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("Saved: analysis/boxplot_track_metrics_by_satisfaction.png")

    # 4. Interpretation report
    n = len(merged)
    lines = [
        "# Интерпретация: зависимости «треки + анкеты»",
        "",
        f"Объединённая выборка: **{n}** посетителей (есть трек и pre-анкета; post — где есть).",
        "",
        "## Основные артефакты",
        f"- `{MERGED_CSV.name}` — объединённая таблица (трек + pre + post).",
        f"- `{CORR_CSV.name}` — корреляционная матрица числовых переменных треков и анкет.",
        "- Папка `analysis/`: scatter (speed track vs pre, satisfaction vs nb_stops/speed, discovery_interest vs nb_items/nb_stops), boxplot по полу и по уровню satisfaction.",
        "",
        "## Ограничения",
        f"Малая выборка (N={n}): интерпретировать стоит только устойчивые по величине связи (|r| > 0.3).",
        "",
    ]
    Path(INTERPRETATION_MD).write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {INTERPRETATION_MD}")

    print("\nDone.")


if __name__ == "__main__":
    main()
