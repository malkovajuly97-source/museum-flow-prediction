"""
Анализ только по ответам анкет (без треков): pre–pre, post–post, pre–post.
Корреляции, scatter, boxplot по полу/возрасту, отчёт.

Скрипт в model_search/questionnaire/.
Входы: pre_questionnaire_formatted.csv, post_questionnaire_formatted.csv из data/questionnaires/.
Выходы: pre_post_merged.csv, answers_correlation_matrix.csv, analysis_answers/, interpretation_answers_ru.md.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent

def _questionnaire_paths():
    candidates = [
        PROJECT_ROOT / "bird-dataset-main" / "data" / "questionnaires",
        PROJECT_ROOT / "data" / "questionnaires",
        PROJECT_ROOT.parent / "bird-dataset-main" / "data" / "questionnaires",
        Path.cwd() / "data" / "questionnaires",
        Path.cwd() / "bird-dataset-main" / "data" / "questionnaires",
    ]
    for root in candidates:
        pre = root / "pre_questionnaire_formatted.csv"
        post = root / "post_questionnaire_formatted.csv"
        if pre.exists():
            return pre, post
    return PROJECT_ROOT / "data/questionnaires/pre_questionnaire_formatted.csv", PROJECT_ROOT / "data/questionnaires/post_questionnaire_formatted.csv"

PRE_QUESTIONNAIRE, POST_QUESTIONNAIRE = _questionnaire_paths()

OUTPUT_DIR = BASE
MERGED_CSV = OUTPUT_DIR / "pre_post_merged.csv"
CORR_CSV = OUTPUT_DIR / "answers_correlation_matrix.csv"
ANALYSIS_DIR = OUTPUT_DIR / "analysis_answers"
ANALYSIS_DIR.mkdir(exist_ok=True)
INTERPRETATION_MD = OUTPUT_DIR / "interpretation_answers_ru.md"

# Числовые/ординальные колонки анкет
PRE_NUMERIC = [
    "age", "one_artwork_interest", "discovery_interest", "crowd_tolerance",
    "lose_interest_with_crowd", "distance_tolerance", "physical_sleepiness",
    "mental_sleepiness", "speed", "current_emotion",
]
POST_NUMERIC = [
    "satisfaction", "goals_reached", "device_trouble", "crowd_trouble",
    "dist_sensation", "end_visit_physical_sleepiness", "end_visit_mental_sleepiness", "panel_interest",
]
PRE_CATEGORICAL = ["gender", "visit_duration", "group_or_alone"]


def load_and_merge():
    """Загрузка pre и post анкет, объединение по visitor_id (left, чтобы сохранить всех с pre)."""
    df_pre = pd.read_csv(PRE_QUESTIONNAIRE)
    df_pre["visitor_id"] = df_pre["visitor_id"].astype(str)
    df_post = pd.read_csv(POST_QUESTIONNAIRE)
    df_post["visitor_id"] = df_post["visitor_id"].astype(str)
    merged = df_pre.merge(df_post, on="visitor_id", how="left", suffixes=("_pre", "_post"))
    return merged


def ensure_numeric(df):
    """Привести выбранные колонки к числу; категории закодировать."""
    out = df.copy()
    for col in PRE_NUMERIC + POST_NUMERIC:
        if col not in out.columns:
            # после merge могут быть _pre/_post суффиксы у дубликатов
            for suffix in ["_pre", "_post", ""]:
                c = col + suffix if suffix else col
                if c in out.columns:
                    out[c] = pd.to_numeric(out[c], errors="coerce")
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "visit_duration" in out.columns:
        out["visit_duration_limited"] = (out["visit_duration"].astype(str).str.lower() != "unlimited").astype(int)
    if "gender" in out.columns:
        g = out["gender"].astype(str).str.strip().str.lower()
        out["gender_code"] = (g == "man").astype(int)
        out.loc[~g.isin(["man", "woman"]), "gender_code"] = np.nan
    return out


def get_analysis_columns(df):
    """Собрать список числовых колонок для корреляций (учитывая суффиксы после merge)."""
    pre_cols = [c for c in PRE_NUMERIC if c in df.columns]
    post_cols = [c for c in POST_NUMERIC if c in df.columns]
    extra = []
    if "visit_duration_limited" in df.columns:
        extra.append("visit_duration_limited")
    if "gender_code" in df.columns:
        extra.append("gender_code")
    return pre_cols + post_cols + extra


def main():
    print("=" * 60)
    print("Questionnaires: analysis by answers only (pre & post)")
    print("=" * 60)

    if not PRE_QUESTIONNAIRE.exists():
        print(f"Not found: {PRE_QUESTIONNAIRE}")
        return

    # 1. Load and merge pre + post
    merged = load_and_merge()
    print(f"Pre rows: {len(pd.read_csv(PRE_QUESTIONNAIRE))}, merged (pre+post left): {len(merged)}")
    merged = ensure_numeric(merged)

    # Унифицируем имена: если после merge есть дубликаты с _pre/_post, оставляем как есть
    merged.to_csv(MERGED_CSV, index=False)
    print(f"Saved: {MERGED_CSV}")

    # 2. Correlation matrix (все числовые переменные ответов)
    analysis_cols = get_analysis_columns(merged)
    if not analysis_cols:
        # fallback: все колонки, которые удаётся привести к числу
        numeric_df = merged.select_dtypes(include=[np.number])
        analysis_cols = list(numeric_df.columns)
    num_df = merged[analysis_cols].apply(pd.to_numeric, errors="coerce")
    corr = num_df.corr()
    corr.to_csv(CORR_CSV)
    print(f"Saved: {CORR_CSV}")

    # 3. Heatmap
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
    ax.set_title("Correlations: questionnaire answers only (pre & post)")
    plt.tight_layout()
    plt.savefig(ANALYSIS_DIR / "answers_correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {ANALYSIS_DIR / 'answers_correlation_heatmap.png'}")

    # 4. Scatter: pre vs post (ключевые пары)
    # satisfaction (post) vs discovery_interest, one_artwork_interest, current_emotion (pre)
    pre_for_satisfaction = ["discovery_interest", "one_artwork_interest", "current_emotion", "age"]
    if "satisfaction" in merged.columns:
        for x_col in pre_for_satisfaction:
            if x_col not in merged.columns:
                continue
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.scatter(merged[x_col], merged["satisfaction"], alpha=0.7)
            ax.set_xlabel(x_col + " (pre)")
            ax.set_ylabel("Satisfaction (post)")
            ax.set_title(f"Satisfaction vs {x_col}")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / f"scatter_satisfaction_vs_{x_col}.png", dpi=150, bbox_inches="tight")
            plt.close()
        print("Saved: analysis_answers/scatter_satisfaction_vs_*.png")

    # goals_reached vs pre
    if "goals_reached" in merged.columns:
        for x_col in ["discovery_interest", "one_artwork_interest"]:
            if x_col not in merged.columns:
                continue
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.scatter(merged[x_col], merged["goals_reached"], alpha=0.7)
            ax.set_xlabel(x_col + " (pre)")
            ax.set_ylabel("Goals reached (post)")
            ax.set_title(f"Goals reached vs {x_col}")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / f"scatter_goals_reached_vs_{x_col}.png", dpi=150, bbox_inches="tight")
            plt.close()

    # 5. Boxplot: satisfaction by gender
    if "gender" in merged.columns and "satisfaction" in merged.columns:
        df_g = merged.dropna(subset=["gender", "satisfaction"])
        df_g = df_g[df_g["gender"].astype(str).str.lower().isin(["man", "woman"])]
        if len(df_g) > 0:
            fig, ax = plt.subplots(figsize=(5, 4))
            df_g.boxplot(column="satisfaction", by="gender", ax=ax)
            ax.set_title("Satisfaction by gender")
            ax.set_xlabel("Gender")
            plt.suptitle("")
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / "boxplot_satisfaction_by_gender.png", dpi=150, bbox_inches="tight")
            plt.close()
            print("Saved: analysis_answers/boxplot_satisfaction_by_gender.png")

    # Boxplot: satisfaction by age group (median split)
    if "age" in merged.columns and "satisfaction" in merged.columns:
        m = merged["age"].median()
        merged_copy = merged.dropna(subset=["age", "satisfaction"]).copy()
        merged_copy["age_group"] = (merged_copy["age"] >= m).map({True: "older", False: "younger"})
        if len(merged_copy) > 0:
            fig, ax = plt.subplots(figsize=(5, 4))
            merged_copy.boxplot(column="satisfaction", by="age_group", ax=ax)
            ax.set_title("Satisfaction by age (median split)")
            ax.set_xlabel("Age group")
            plt.suptitle("")
            plt.tight_layout()
            plt.savefig(ANALYSIS_DIR / "boxplot_satisfaction_by_age.png", dpi=150, bbox_inches="tight")
            plt.close()
            print("Saved: analysis_answers/boxplot_satisfaction_by_age.png")

    # 6. Interpretation report
    n_pre = len(merged)
    n_with_post = merged["satisfaction"].notna().sum() if "satisfaction" in merged.columns else 0
    lines = [
        "# Интерпретация: анализ только по ответам анкет",
        "",
        f"Выборка: **{n_pre}** анкет до визита (pre), из них **{n_with_post}** с анкетой после (post).",
        "",
        "## Артефакты",
        f"- `{MERGED_CSV.name}` — объединённая таблица pre + post по visitor_id.",
        f"- `{CORR_CSV.name}` — корреляционная матрица числовых переменных ответов (pre и post).",
        "- Папка `analysis_answers/`: тепловая карта корреляций, scatter (satisfaction/goals_reached vs pre), boxplot по полу и возрасту.",
        "",
        "## Ограничения",
        "Малая выборка; интерпретировать устойчивые связи (|r| > 0.3). Анализ только по ответам — без учёта треков.",
        "",
    ]
    Path(INTERPRETATION_MD).write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {INTERPRETATION_MD}")

    print("\nDone.")


if __name__ == "__main__":
    main()
