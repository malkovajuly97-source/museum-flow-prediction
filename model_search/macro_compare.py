"""
Helpers for model_search_macro.ipynb: room popularity and edge-load comparison (real vs simulated).
Import in the notebook and call run_room_popularity_comparison / run_edge_load_comparison to reduce inline code.
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr, t as t_dist


def run_room_popularity_comparison(df_real, df_sim, n_traj_sim):
    """
    Compare room popularity: merge real/sim, scatter n_real vs n_sim, regression, Pearson/Spearman, slopegraph.
    df_real, df_sim: DataFrames with columns zone, rank, n_agents_visited.
    """
    if n_traj_sim == 0 or len(df_sim) == 0:
        print("No simulated data for comparison.")
        return None

    compare_df = df_real.rename(columns={"rank": "rank_real", "n_agents_visited": "n_real"})
    sim_df = df_sim.rename(columns={"rank": "rank_sim", "n_agents_visited": "n_sim"})
    compare_df = compare_df.merge(sim_df[["zone", "rank_sim", "n_sim"]], on="zone", how="outer")
    compare_df = compare_df.fillna(0).astype({"rank_sim": int, "n_sim": int})
    valid = compare_df[(compare_df["n_real"] > 0) | (compare_df["n_sim"] > 0)]

    # Scatter: n_real vs n_sim
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(valid["n_real"], valid["n_sim"], alpha=0.7)
    for _, r in valid.iterrows():
        ax.annotate(str(int(r["zone"])), (r["n_real"], r["n_sim"]), fontsize=9)
    mx = max(valid["n_real"].max(), valid["n_sim"].max())
    ax.plot([0, mx], [0, mx], "k--", alpha=0.5, label="y=x")
    b, a = np.polyfit(valid["n_real"], valid["n_sim"], 1)
    x_line = np.linspace(valid["n_real"].min(), valid["n_real"].max(), 100)
    y_line = a + b * x_line
    if len(valid) >= 3:
        x_vals, y_vals = valid["n_real"].values, valid["n_sim"].values
        n = len(x_vals)
        y_pred = a + b * x_vals
        mse = np.sum((y_vals - y_pred) ** 2) / (n - 2)
        x_mean = np.mean(x_vals)
        ss_x = np.sum((x_vals - x_mean) ** 2)
        se = np.sqrt(mse * (1 / n + (x_line - x_mean) ** 2 / ss_x))
        t_val = t_dist.ppf(0.975, n - 2)
        ax.fill_between(x_line, y_line - t_val * se, y_line + t_val * se, alpha=0.2, color="gray")
    ax.plot(x_line, y_line, "r-", alpha=0.7, label=f"Regression y={b:.2f}x+{a:.2f}")
    ax.set_xlabel("n_agents_visited (real)")
    ax.set_ylabel("n_agents_visited (simulated)")
    ax.set_title("Room popularity: real vs simulated")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Statistics
    both = compare_df[(compare_df["n_real"] > 0) & (compare_df["n_sim"] > 0)]
    if len(both) >= 2:
        r_pearson, p_pearson = pearsonr(both["n_real"], both["n_sim"])
        r_spearman, p_spearman = spearmanr(both["rank_real"], both["rank_sim"])
        print(f"n_real: mean={both['n_real'].mean():.1f}, std={both['n_real'].std():.1f}")
        print(f"n_sim:  mean={both['n_sim'].mean():.1f}, std={both['n_sim'].std():.1f}")
        print(f"Pearson correlation (n_agents): r={r_pearson:.3f}, p={p_pearson:.4f}")
        print(f"Spearman correlation (rank):     r={r_spearman:.3f}, p={p_spearman:.4f}")

    # Slopegraph: zones on left by rank_real, on right by rank_sim
    df_left = compare_df.sort_values("rank_real").reset_index(drop=True)
    rank_to_pos_right = dict(zip(df_left.sort_values("rank_sim")["zone"], range(len(df_left))))
    fig, ax = plt.subplots(figsize=(6, 8))
    n_rows = len(df_left)
    for i, row in df_left.iterrows():
        z = row["zone"]
        y_right = rank_to_pos_right.get(z, i)
        ax.plot([0, 1], [i, y_right], "b-", alpha=0.5)
        ax.text(-0.05, i, f"{int(z)}", ha="right", va="center", fontsize=9)
        ax.text(1.05, y_right, f"{int(z)}", ha="left", va="center", fontsize=9)
    ax.set_xlim(-0.3, 1.3)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["real", "simulated"])
    ax.set_yticks([])
    ax.set_title("Slopegraph: zone ranks real vs simulated")
    plt.tight_layout()
    plt.show()

    return compare_df


def run_edge_load_comparison(df_trans_real, df_trans_sim):
    """
    Compare edge-load: merge on (from_zone, to_zone), scatter pct_real vs pct_sim, regression, Pearson/Spearman/MAE.
    df_trans_real, df_trans_sim: DataFrames with from_zone, to_zone, dependency_pct, count.
    """
    if df_trans_real is None or len(df_trans_real) == 0 or df_trans_sim is None or len(df_trans_sim) == 0:
        print("No simulated tracks for edge-load comparison.")
        return None

    merge_df = df_trans_real.rename(columns={"dependency_pct": "pct_real", "count": "count_real"})
    merge_df = merge_df.merge(
        df_trans_sim[["from_zone", "to_zone", "dependency_pct", "count"]].rename(
            columns={"dependency_pct": "pct_sim", "count": "count_sim"}
        ),
        on=["from_zone", "to_zone"],
        how="outer",
    ).fillna(0)
    merge_df["edge"] = (
        merge_df["from_zone"].astype(int).astype(str) + " -> " + merge_df["to_zone"].astype(int).astype(str)
    )

    plt.figure(figsize=(7, 7))
    plt.scatter(merge_df["pct_real"], merge_df["pct_sim"], alpha=0.7)
    for _, r in merge_df.iterrows():
        plt.annotate(r["edge"], (r["pct_real"], r["pct_sim"]), fontsize=7, alpha=0.8)
    plt.xlabel("Edge load real (%)")
    plt.ylabel("Edge load simulated (%)")
    plt.title("Edge-load comparison: real vs simulated")
    mx = merge_df[["pct_real", "pct_sim"]].max().max()
    plt.plot([0, mx], [0, mx], "k--", alpha=0.5, label="y=x")
    b, a = np.polyfit(merge_df["pct_real"], merge_df["pct_sim"], 1)
    x_line = np.linspace(0, merge_df["pct_real"].max(), 100)
    y_line = a + b * x_line
    if len(merge_df) >= 3:
        x_vals = merge_df["pct_real"].values
        y_vals = merge_df["pct_sim"].values
        n = len(x_vals)
        y_pred = a + b * x_vals
        mse = np.sum((y_vals - y_pred) ** 2) / (n - 2)
        x_mean = np.mean(x_vals)
        ss_x = np.sum((x_vals - x_mean) ** 2)
        se = np.sqrt(mse * (1 / n + (x_line - x_mean) ** 2 / ss_x))
        t_val = t_dist.ppf(0.975, n - 2)
        plt.fill_between(x_line, y_line - t_val * se, y_line + t_val * se, alpha=0.2, color="gray")
    plt.plot(x_line, y_line, "r-", alpha=0.7, label=f"Regression y={b:.2f}x+{a:.2f}")
    plt.legend()
    plt.tight_layout()
    plt.show()

    pct_real = merge_df["pct_real"].values
    pct_sim = merge_df["pct_sim"].values
    count_real = merge_df["count_real"].values
    count_sim = merge_df["count_sim"].values
    pearson_pct, _ = pearsonr(pct_real, pct_sim)
    spearman_pct, _ = spearmanr(pct_real, pct_sim)
    pearson_cnt, _ = pearsonr(count_real, count_sim)
    spearman_cnt, _ = spearmanr(count_real, count_sim)
    mae_pct = np.mean(np.abs(pct_real - pct_sim))
    rmse_pct = np.sqrt(np.mean((pct_real - pct_sim) ** 2))
    mae_cnt = np.mean(np.abs(count_real - count_sim))

    print("--- Basic edge-load stats ---")
    print(
        f"pct_real:  mean={np.mean(pct_real):.4f}, std={np.std(pct_real):.4f}, min={np.min(pct_real):.4f}, max={np.max(pct_real):.4f}"
    )
    print(
        f"pct_sim:   mean={np.mean(pct_sim):.4f}, std={np.std(pct_sim):.4f}, min={np.min(pct_sim):.4f}, max={np.max(pct_sim):.4f}"
    )
    print(
        f"count_real: mean={np.mean(count_real):.2f}, std={np.std(count_real):.2f}, min={np.min(count_real):.0f}, max={np.max(count_real):.0f}"
    )
    print(
        f"count_sim:  mean={np.mean(count_sim):.2f}, std={np.std(count_sim):.2f}, min={np.min(count_sim):.0f}, max={np.max(count_sim):.0f}"
    )
    print("--- Edge-load correlation and comparison metrics ---")
    print(f"dependency_pct: Pearson={pearson_pct:.4f}, Spearman={spearman_pct:.4f}")
    print(f"dependency_pct: MAE={mae_pct:.4f}, RMSE={rmse_pct:.4f}")
    print(f"count: Pearson={pearson_cnt:.4f}, Spearman={spearman_cnt:.4f}")
    print(f"count: MAE={mae_cnt:.2f}")

    return merge_df


def _interpret_corr_macro(spear):
    if spear >= 0.7:
        return "strong"
    if spear >= 0.4:
        return "moderate"
    if spear >= 0.2:
        return "weak"
    return "very weak / absent"


def run_global_summary_macro(df_real, df_sim, n_traj_sim, df_trans_real, df_trans_sim):
    """
    Build global summary markdown for macro: room popularity + edge-load with targets and recommendations.
    Returns markdown string; in notebook use: display(Markdown(run_global_summary_macro(...))).
    Pass None or empty DataFrame for missing data.
    """
    lines = ["## Global summary: real vs simulated (macro)\n"]

    # Room popularity
    has_room = (
        df_real is not None and len(df_real) > 0
        and df_sim is not None and len(df_sim) > 0
        and n_traj_sim is not None and n_traj_sim > 0
    )
    if has_room:
        compare_df = df_real.rename(columns={"rank": "rank_real", "n_agents_visited": "n_real"})
        sim_df = df_sim.rename(columns={"rank": "rank_sim", "n_agents_visited": "n_sim"})
        compare_df = compare_df.merge(sim_df[["zone", "rank_sim", "n_sim"]], on="zone", how="outer").fillna(0)
        both = compare_df[(compare_df["n_real"] > 0) & (compare_df["n_sim"] > 0)]
        if len(both) >= 2:
            r_pear, _ = pearsonr(both["n_real"], both["n_sim"])
            r_spear, _ = spearmanr(both["rank_real"], both["rank_sim"])
            lines.append("### Room popularity")
            lines.append(f"- **Pearson (n_agents):** r = {r_pear:.3f} — linear agreement on visit counts per zone.")
            lines.append(f"- **Spearman (rank):** rho = {r_spear:.3f} — **{_interpret_corr_macro(r_spear)}** agreement on zone ranking.")
            ok_s = "✓" if r_spear >= 0.7 else "✗"
            lines.append(f"- **Target:** Spearman (rank) ≥ 0.7 {ok_s}.")
        else:
            lines.append("### Room popularity")
            lines.append("Too few zones with both real and sim visits for correlation.")
    else:
        lines.append("### Room popularity")
        lines.append("No simulated room popularity data — comparison not possible.")
    lines.append("")

    # Edge-load
    has_edge = (
        df_trans_real is not None and len(df_trans_real) > 0
        and df_trans_sim is not None and len(df_trans_sim) > 0
    )
    if has_edge:
        merge_df = df_trans_real.rename(columns={"dependency_pct": "pct_real", "count": "count_real"}).merge(
            df_trans_sim[["from_zone", "to_zone", "dependency_pct", "count"]].rename(
                columns={"dependency_pct": "pct_sim", "count": "count_sim"}
            ),
            on=["from_zone", "to_zone"],
            how="outer",
        ).fillna(0)
        pct_r, pct_s = merge_df["pct_real"].values, merge_df["pct_sim"].values
        cnt_r, cnt_s = merge_df["count_real"].values, merge_df["count_sim"].values
        if len(merge_df) >= 2:
            pearson_pct, _ = pearsonr(pct_r, pct_s)
            spearman_pct, _ = spearmanr(pct_r, pct_s)
            pearson_cnt, _ = pearsonr(cnt_r, cnt_s)
            spearman_cnt, _ = spearmanr(cnt_r, cnt_s)
            mae_pct = float(np.mean(np.abs(pct_r - pct_s)))
            lines.append("### Edge-load")
            lines.append(f"- **dependency_pct:** Pearson r = {pearson_pct:.3f}, Spearman rho = {spearman_pct:.3f} — **{_interpret_corr_macro(spearman_pct)}** agreement.")
            lines.append(f"- **count:** Pearson r = {pearson_cnt:.3f}, Spearman rho = {spearman_cnt:.3f}. MAE(pct) = {mae_pct:.3f}.")
            ok_pct = "✓" if spearman_pct >= 0.7 else "✗"
            lines.append(f"- **Target:** Spearman (dependency_pct) ≥ 0.7 {ok_pct}.")
        else:
            lines.append("### Edge-load")
            lines.append("Too few edges for correlation.")
    else:
        lines.append("### Edge-load")
        lines.append("No simulated edge-load data — comparison not possible.")
    lines.append("")

    lines.append("### Recommendations (targets to aim for)")
    lines.append("- **Room popularity:** Spearman rank correlation ≥ 0.7 indicates good agreement on which zones are most/least visited. Pearson on n_agents reflects similarity in absolute counts.")
    lines.append("- **Edge-load:** Spearman ≥ 0.7 on dependency_pct (or count) indicates that transition flows between zones match well. Lower MAE on dependency_pct is better.")
    lines.append("")
    lines.append("---")
    lines.append("*Summary generated from metrics computed in the cells above.*")

    return "\n".join(lines)
