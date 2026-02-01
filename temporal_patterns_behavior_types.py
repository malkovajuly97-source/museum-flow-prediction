"""
Этап 5: Временные паттерны поведения (4 типа, этаж 0)

Скрипт:
1. Загружает траектории с timestamp и типами поведения
2. Нормализует время визита: t_norm = timestamp / duration
3. Разбивает визит на фазы: начало [0, 0.33), середина [0.33, 0.67), конец [0.67, 1.0]
4. Агрегирует по (тип поведения, фаза) и опционально по (тип, квадрант, фаза)
5. Строит таблицы и визуализации
6. Сохраняет результаты в analysis_results_merged
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Пути
INPUT_DIR = Path("analysis_results")
MERGED_DIR = Path("analysis_results_merged")
OUTPUT_DIR = Path("analysis_results_merged")
OUTPUT_DIR.mkdir(exist_ok=True)

TRAJECTORIES_WITH_FEATURES = INPUT_DIR / "floor0_trajectories_with_features.csv"
CLUSTERED_MERGED = MERGED_DIR / "floor0_trajectories_clustered_merged.csv"

# Границы фаз (доли визита)
PHASE_BOUNDS = [(0.0, 1/3, 'start'), (1/3, 2/3, 'mid'), (2/3, 1.0, 'end')]
PHASE_LABELS_RU = {'start': 'начало', 'mid': 'середина', 'end': 'конец'}


def load_temporal_data():
    """Загружает траектории с timestamp и типами поведения (только этаж 0, 4 типа)."""
    print("=" * 70)
    print("ЗАГРУЗКА ДАННЫХ ДЛЯ ВРЕМЕННОГО АНАЛИЗА")
    print("=" * 70)

    df_traj = pd.read_csv(TRAJECTORIES_WITH_FEATURES)
    df_traj['trajectory_id'] = df_traj['trajectory_id'].astype(str)

    df_clustered = pd.read_csv(CLUSTERED_MERGED)
    df_clustered['trajectory_id'] = df_clustered['trajectory_id'].astype(str)
    behavior_types = df_clustered[['trajectory_id', 'behavior_type']].copy()

    df = df_traj.merge(behavior_types, on='trajectory_id', how='inner')
    print(f"Точек после объединения: {len(df)}")
    print(f"Траекторий: {df['trajectory_id'].nunique()}")
    for bt, cnt in df['behavior_type'].value_counts().items():
        print(f"  {bt}: {cnt} точек ({df[df['behavior_type']==bt]['trajectory_id'].nunique()} траекторий)")
    return df


def add_normalized_time_and_phase(df):
    """Добавляет t_norm и фазу к каждой точке."""
    # t_norm = доля визита (0..1). duration одинаков для всех точек одной траектории
    df = df.copy()
    df['t_norm'] = df['timestamp'] / (df['duration'].replace(0, np.nan))
    df['t_norm'] = df['t_norm'].clip(0, 1)

    def assign_phase(t):
        if t < 1/3:
            return 'start'
        if t < 2/3:
            return 'mid'
        return 'end'

    df['phase'] = df['t_norm'].apply(assign_phase)
    return df


def add_quadrants(df):
    """Добавляет квадрант по медианам x,y по всем точкам (как в этапе 4)."""
    x_median = df['x'].median()
    y_median = df['y'].median()
    df = df.copy()
    df['quadrant'] = 'SE'
    df.loc[(df['x'] < x_median) & (df['y'] < y_median), 'quadrant'] = 'SW'
    df.loc[(df['x'] < x_median) & (df['y'] >= y_median), 'quadrant'] = 'NW'
    df.loc[(df['x'] >= x_median) & (df['y'] >= y_median), 'quadrant'] = 'NE'
    return df


def aggregate_by_type_and_phase(df):
    """Агрегация по (behavior_type, phase): число точек и доля."""
    print("\n" + "=" * 70)
    print("АГРЕГАЦИЯ ПО ТИПУ И ФАЗЕ (начало / середина / конец)")
    print("=" * 70)

    order_phase = ['start', 'mid', 'end']
    rows = []
    for bt in sorted(df['behavior_type'].unique()):
        sub = df[df['behavior_type'] == bt]
        n_total = len(sub)
        for ph in order_phase:
            n_ph = (sub['phase'] == ph).sum()
            pct = 100.0 * n_ph / n_total if n_total else 0
            rows.append({
                'behavior_type': bt,
                'phase': ph,
                'phase_ru': PHASE_LABELS_RU[ph],
                'n_points': n_ph,
                'pct_points': round(pct, 2),
                'n_trajectories': sub['trajectory_id'].nunique(),
                'n_total_points': n_total,
            })
        for ph in order_phase:
            pct = next(r['pct_points'] for r in rows if r['behavior_type']==bt and r['phase']==ph)
            print(f"  {bt} / {PHASE_LABELS_RU[ph]}: {pct:.1f}% точек")

    out_df = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "temporal_patterns_by_type.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nТаблица сохранена: {out_path}")
    return out_df


def aggregate_by_type_quadrant_phase(df):
    """Агрегация по (behavior_type, quadrant, phase)."""
    print("\n" + "=" * 70)
    print("АГРЕГАЦИЯ ПО ТИПУ, КВАДРАНТУ И ФАЗЕ")
    print("=" * 70)

    order_phase = ['start', 'mid', 'end']
    order_quad = ['SW', 'SE', 'NW', 'NE']
    rows = []
    for bt in sorted(df['behavior_type'].unique()):
        sub = df[df['behavior_type'] == bt]
        n_type = len(sub)
        for q in order_quad:
            sq = sub[sub['quadrant'] == q]
            n_q = len(sq)
            for ph in order_phase:
                n_qp = ((sq['phase'] == ph).sum())
                pct_of_type = 100.0 * n_qp / n_type if n_type else 0
                pct_in_quad = 100.0 * n_qp / n_q if n_q else 0
                rows.append({
                    'behavior_type': bt,
                    'quadrant': q,
                    'phase': ph,
                    'phase_ru': PHASE_LABELS_RU[ph],
                    'n_points': n_qp,
                    'pct_of_type_points': round(pct_of_type, 2),
                    'pct_within_quadrant': round(pct_in_quad, 2) if n_q else 0,
                })

    out_df = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "temporal_by_quadrant_phase.csv"
    out_df.to_csv(out_path, index=False)
    print(f"Таблица сохранена: {out_path}")
    return out_df


def plot_phase_share_by_type(df_temporal):
    """Столбчатая диаграмма: доля точек в начале/середине/конце по типам."""
    print("\nПостроение: доля точек по фазам и типам...")

    order_phase = ['start', 'mid', 'end']
    type_order = df_temporal['behavior_type'].unique()
    if not isinstance(type_order, np.ndarray):
        type_order = sorted(type_order)
    else:
        type_order = sorted(type_order.tolist())

    # pivot: строки = тип, столбцы = фаза, значения = pct_points
    pivot = df_temporal.set_index(['behavior_type', 'phase'])['pct_points'].unstack(fill_value=0)
    pivot = pivot.reindex(columns=order_phase, index=type_order, fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(type_order))
    w = 0.25
    colors = ['#2ecc71', '#3498db', '#e74c3c']
    for i, ph in enumerate(order_phase):
        ax.bar(x + i * w, pivot[ph].values, width=w, label=PHASE_LABELS_RU[ph], color=colors[i])

    ax.set_xticks(x + w)
    ax.set_xticklabels(type_order, rotation=15, ha='right')
    ax.set_ylabel('Доля точек, %')
    ax.set_title('Распределение времени визита по фазам (начало / середина / конец) по типам поведения')
    ax.legend()
    ax.set_ylim(0, 50)
    plt.tight_layout()
    out_path = OUTPUT_DIR / "temporal_phase_share_by_type.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Сохранено: {out_path}")


def plot_cumulative_time_by_type(df):
    """График кумулятивной доли визита по нормализованному времени (по типам)."""
    print("Построение: кумулятивная доля визита по t_norm...")

    type_order = sorted(df['behavior_type'].unique())
    n_bins = 50
    bins = np.linspace(0, 1, n_bins + 1)

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(type_order), 1)))

    for idx, bt in enumerate(type_order):
        sub = df[df['behavior_type'] == bt]
        counts, _ = np.histogram(sub['t_norm'], bins=bins)
        cum = np.cumsum(counts)
        if cum[-1] > 0:
            cum_pct = 100.0 * cum / cum[-1]
        else:
            cum_pct = np.zeros_like(cum)
        ax.plot(bins[:-1] + (bins[1]-bins[0])/2, cum_pct, label=bt, color=colors[idx % len(colors)], lw=2)

    ax.axhline(50, color='gray', ls='--', alpha=0.6)
    ax.axvline(0.5, color='gray', ls='--', alpha=0.6)
    ax.set_xlabel('Нормализованное время визита (0 = старт, 1 = конец)')
    ax.set_ylabel('Кумулятивная доля точек, %')
    ax.set_title('Накопленная доля посещённых точек по ходу визита (по типам поведения)')
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 105)
    plt.tight_layout()
    out_path = OUTPUT_DIR / "temporal_cumulative_by_type.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Сохранено: {out_path}")


def plot_quadrant_phase_heatmap(df_quad_phase):
    """Heatmap: тип × (квадрант–фаза) или отдельные маленькие heatmap по типам."""
    print("Построение: квадрант x фаза по типам (heatmap)...")

    types = sorted(df_quad_phase['behavior_type'].unique())
    n_types = len(types)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    for idx, bt in enumerate(types):
        if idx >= len(axes):
            break
        ax = axes[idx]
        sub = df_quad_phase[df_quad_phase['behavior_type'] == bt]
        pivot = sub.pivot_table(index='quadrant', columns='phase', values='pct_of_type_points', aggfunc='sum')
        for c in ['start', 'mid', 'end']:
            if c not in pivot.columns:
                pivot[c] = 0
        pivot = pivot[['start', 'mid', 'end']]
        pivot = pivot.reindex(['SW', 'SE', 'NW', 'NE'], fill_value=0)
        im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=25)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels([PHASE_LABELS_RU['start'], PHASE_LABELS_RU['mid'], PHASE_LABELS_RU['end']])
        ax.set_yticks(range(4))
        ax.set_yticklabels(['SW', 'SE', 'NW', 'NE'])
        ax.set_title(bt)
        ax.set_xlabel('Фаза')

    fig.suptitle('Доля точек по квадрантам и фазам визита (% от типа)', y=1.02)
    plt.tight_layout()
    out_path = OUTPUT_DIR / "temporal_quadrant_phase_heatmap.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Сохранено: {out_path}")


def main():
    df = load_temporal_data()
    df = add_normalized_time_and_phase(df)
    df = add_quadrants(df)

    df_temporal = aggregate_by_type_and_phase(df)
    df_quad_phase = aggregate_by_type_quadrant_phase(df)

    plot_phase_share_by_type(df_temporal)
    plot_cumulative_time_by_type(df)
    plot_quadrant_phase_heatmap(df_quad_phase)

    print("\n" + "=" * 70)
    print("ЭТАП 5 (ВРЕМЕННЫЕ ПАТТЕРНЫ) ЗАВЕРШЁН")
    print("=" * 70)
    print("Результаты в каталоге:", OUTPUT_DIR)
    print("  - temporal_patterns_by_type.csv")
    print("  - temporal_by_quadrant_phase.csv")
    print("  - temporal_phase_share_by_type.png")
    print("  - temporal_cumulative_by_type.png")
    print("  - temporal_quadrant_phase_heatmap.png")


if __name__ == "__main__":
    main()
