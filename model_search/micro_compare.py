"""
Helpers for model_search_micro.ipynb: real vs simulated comparison (density, ToP, stop duration).
Import this module in the notebook and call run_* functions to reduce inline code.
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.stats import pearsonr, spearmanr

try:
    from skimage.metrics import structural_similarity as ssim
    HAS_SSIM = True
except ImportError:
    HAS_SSIM = False


def compare_maps(real, sim, name="Map"):
    """Print Pearson and Spearman correlation (only cells where real or sim > 0)."""
    r_flat = np.asarray(real).ravel().astype(float)
    s_flat = np.asarray(sim).ravel().astype(float)
    mask = (r_flat > 0) | (s_flat > 0)
    if mask.sum() < 2:
        print(f"{name}: too few cells")
        return
    r, p = pearsonr(r_flat[mask], s_flat[mask])
    r_spear, _ = spearmanr(r_flat[mask], s_flat[mask])
    print(f"  Pearson r = {r:.4f}, Spearman rho = {r_spear:.4f} (p = {p:.4f})")


def map_errors(real, sim, name="Map"):
    """Print MAE, RMSE, NMAE (using ravel so mask matches)."""
    r_flat = np.asarray(real).ravel().astype(float)
    s_flat = np.asarray(sim).ravel().astype(float)
    mask = (r_flat > 0) | (s_flat > 0)
    if mask.sum() == 0:
        print(f"{name}: no cells")
        return
    r, s = r_flat[mask], s_flat[mask]
    mae = float(np.mean(np.abs(r - s)))
    rmse = float(np.sqrt(np.mean((r - s) ** 2)))
    nmae = mae / (float(np.mean(r)) + 1e-9)
    print(f"  MAE = {mae:.4f}, RMSE = {rmse:.4f}, NMAE = {nmae:.4f}")


def corr_errors(real, sim):
    """Return dict with pearson, spearman, mae, nmae for global summary. Returns None if too few cells."""
    r_flat = np.asarray(real).ravel().astype(float)
    s_flat = np.asarray(sim).ravel().astype(float)
    mask = (r_flat > 0) | (s_flat > 0)
    if mask.sum() < 2:
        return None
    r_pear, _ = pearsonr(r_flat[mask], s_flat[mask])
    r_spear, _ = spearmanr(r_flat[mask], s_flat[mask])
    rr, ss = r_flat[mask], s_flat[mask]
    mae = float(np.mean(np.abs(rr - ss)))
    nmae = mae / (float(np.mean(rr)) + 1e-9)
    return {"pearson": r_pear, "spearman": r_spear, "mae": mae, "nmae": nmae}


def interpret_corr(spear):
    if spear >= 0.7:
        return "strong"
    if spear >= 0.4:
        return "moderate"
    if spear >= 0.2:
        return "weak"
    return "very weak / absent"


def interpret_ratio(ratio):
    if ratio < 0.8:
        return "simulation clearly underestimates"
    if ratio < 1.0:
        return "simulation slightly underestimates"
    if ratio <= 1.2:
        return "simulation is close to reality"
    if ratio <= 1.5:
        return "simulation slightly overestimates"
    return "simulation clearly overestimates"


def print_stop_stats(name, stats):
    """Print stop duration stats (n_stops, mean, median, percentiles, proportion long)."""
    if not stats:
        print(f"{name}: no stops")
        return
    print(f"{name}:")
    print(f"  n_stops: {stats.get('n_stops', '—')}")
    print(f"  mean: {stats.get('mean_sec', '-')} s, median: {stats.get('median_sec', '-')} s")
    print(f"  75th: {stats.get('p75_sec', '-')} s, 90th: {stats.get('p90_sec', '-')} s")
    thr = stats.get("long_stop_threshold_sec", 30)
    prop = stats.get("proportion_long_stops", 0)
    print(f"  proportion of long stops (>{thr} s): {prop:.2%}")


def run_density_comparison(d_real, d_sim, hm_real_smooth, hm_sim_smooth, xe, ye, segments):
    """Print density metrics and plot difference map. No-op if d_sim or hm_sim_smooth is None."""
    if d_sim is None or hm_sim_smooth is None:
        print("No simulated density — skip comparison.")
        return
    print("Correlation:")
    compare_maps(hm_real_smooth, hm_sim_smooth, "Density")
    print("Errors:")
    map_errors(hm_real_smooth, hm_sim_smooth, "Density")
    if HAS_SSIM:
        dr = max(hm_real_smooth.max(), hm_sim_smooth.max()) - min(hm_real_smooth.min(), hm_sim_smooth.min()) or 1.0
        print(f"  SSIM = {ssim(hm_real_smooth, hm_sim_smooth, data_range=dr):.4f}")
    from plot_density_grids import plot_heatmap_on_plan
    diff_d = hm_real_smooth - hm_sim_smooth
    v_abs = np.percentile(np.abs(diff_d[diff_d != 0]), 95) if np.any(diff_d != 0) else 1e-9
    v_abs = max(float(v_abs), 1e-9)
    cmap_div = mcolors.LinearSegmentedColormap.from_list("div", ["#2166ac", "white", "#b2182b"], N=256)
    fig, ax = plt.subplots(figsize=(8, 6))
    plot_heatmap_on_plan(ax, diff_d, xe, ye, segments, "Density: real - sim", label="points",
                         vmin=-v_abs, vmax=v_abs, cmap=cmap_div, draw_grid=False, interpolation="bilinear")
    plt.tight_layout()
    plt.show()


def run_top_comparison(d_real, d_sim, top_real_smooth, top_sim_smooth, xe, ye, segments):
    """Print ToP metrics and plot difference map. No-op if d_sim or top_sim_smooth is None."""
    if d_sim is None or top_sim_smooth is None:
        print("No simulated ToP — skip comparison.")
        return
    print("Correlation:")
    compare_maps(top_real_smooth, top_sim_smooth, "ToP")
    print("Errors:")
    map_errors(top_real_smooth, top_sim_smooth, "ToP (sec)")
    if HAS_SSIM:
        dr = max(top_real_smooth.max(), top_sim_smooth.max()) - min(top_real_smooth.min(), top_sim_smooth.min()) or 1.0
        print(f"  SSIM = {ssim(top_real_smooth, top_sim_smooth, data_range=dr):.4f}")
    from plot_density_grids import plot_heatmap_on_plan
    diff_t = top_real_smooth - top_sim_smooth
    v_abs = np.percentile(np.abs(diff_t[diff_t != 0]), 95) if np.any(diff_t != 0) else 1e-9
    v_abs = max(float(v_abs), 1e-9)
    cmap_div = mcolors.LinearSegmentedColormap.from_list("div", ["#2166ac", "white", "#b2182b"], N=256)
    fig, ax = plt.subplots(figsize=(8, 6))
    plot_heatmap_on_plan(ax, diff_t, xe, ye, segments, "ToP: real - sim", label="sec",
                         vmin=-v_abs, vmax=v_abs, cmap=cmap_div, draw_grid=False, interpolation="bilinear")
    plt.tight_layout()
    plt.show()


def run_stop_duration_comparison(d_real, d_sim):
    """Print stop stats for real and sim, then comparison (diff mean, median, proportion long)."""
    print_stop_stats("Real", d_real.get("stop_duration_stats"))
    if d_sim is not None:
        print_stop_stats("Simulated", d_sim.get("stop_duration_stats"))
    s_real = d_real.get("stop_duration_stats") or {}
    s_sim = d_sim.get("stop_duration_stats") if d_sim else None
    if not s_sim or not s_real:
        if not s_real:
            print("Comparison: no real stop stats.")
        elif not s_sim:
            print("Comparison: no simulated data.")
        return
    m_r, m_s = s_real.get("mean_sec"), s_sim.get("mean_sec")
    med_r, med_s = s_real.get("median_sec"), s_sim.get("median_sec")
    p_r, p_s = s_real.get("proportion_long_stops", 0), s_sim.get("proportion_long_stops", 0)
    print("Comparison (real vs simulated):")
    if m_r is not None and m_s is not None:
        print(f"  Mean stop duration: real {m_r} s, sim {m_s} s, diff = {m_r - m_s:.2f} s")
    if med_r is not None and med_s is not None:
        print(f"  Median: real {med_r} s, sim {med_s} s, diff = {med_r - med_s:.2f} s")
    print(f"  Proportion long stops: real {p_r:.2%}, sim {p_s:.2%}, diff = {p_r - p_s:.2%}")


def run_global_summary(d_real, d_sim, hm_real_smooth, hm_sim_smooth, top_real_smooth, top_sim_smooth):
    """Build and display Markdown summary from current metrics. Call from notebook with display(run_global_summary(...))."""
    from IPython.display import display, Markdown
    lines = ["## Global summary: real vs simulated\n"]
    if d_sim is None or hm_sim_smooth is None:
        lines.append("Simulated data not loaded — comparison not possible.")
    else:
        d_met = corr_errors(hm_real_smooth, hm_sim_smooth)
        d_tot_r = int(d_real["heatmap"].sum())
        d_tot_s = int(d_sim["heatmap"].sum())
        d_ratio = d_tot_s / max(d_tot_r, 1)
        lines.append("### Density")
        if d_met:
            lines.append(f"- **Correlation:** Pearson r = {d_met['pearson']:.3f}, Spearman rho = {d_met['spearman']:.3f} — **{interpret_corr(d_met['spearman'])}** agreement.")
            lines.append(f"- **Errors:** MAE = {d_met['mae']:.2f}, NMAE = {d_met['nmae']:.2f} — {'substantial differences in magnitude.' if d_met['nmae'] > 1 else 'moderate differences.'}")
        lines.append(f"- **Global total:** density sum real = {d_tot_r}, sim = {d_tot_s}, ratio sim/real = {d_ratio:.3f} — **{interpret_ratio(d_ratio)}** overall visits.")
        if d_met:
            ok_s = "✓" if d_met["spearman"] >= 0.7 else "✗"
            ok_n = "✓" if d_met["nmae"] <= 1.0 else "✗"
            lines.append(f"- **Targets:** Spearman ρ ≥ 0.7 (spatial pattern) {ok_s}; NMAE ≤ 1.0 (magnitude) {ok_n}.")
        lines.append("")
        t_met = corr_errors(top_real_smooth, top_sim_smooth)
        t_tot_r = float(d_real["top_matrix"].sum())
        t_tot_s = float(d_sim["top_matrix"].sum())
        t_ratio = t_tot_s / max(t_tot_r, 1e-9)
        lines.append("### Time of Presence (ToP)")
        if t_met:
            lines.append(f"- **Correlation:** Pearson r = {t_met['pearson']:.3f}, Spearman rho = {t_met['spearman']:.3f} — **{interpret_corr(t_met['spearman'])}** agreement.")
            lines.append(f"- **Errors:** MAE = {t_met['mae']:.2f} s, NMAE = {t_met['nmae']:.2f} — {'substantial differences.' if t_met['nmae'] > 1 else 'moderate differences.'}")
        lines.append(f"- **Global total:** ToP sum real = {t_tot_r:.0f} s ({t_tot_r/60:.1f} min), sim = {t_tot_s:.0f} s ({t_tot_s/60:.1f} min), ratio sim/real = {t_ratio:.3f} — **{interpret_ratio(t_ratio)}** presence time.")
        if t_met:
            ok_s = "✓" if t_met["spearman"] >= 0.7 else "✗"
            ok_n = "✓" if t_met["nmae"] <= 1.0 else "✗"
            lines.append(f"- **Targets:** Spearman ρ ≥ 0.7 (spatial pattern) {ok_s}; NMAE ≤ 1.0 (magnitude) {ok_n}.")
        lines.append("")
        sr, ss = d_real.get("stop_duration_stats") or {}, d_sim.get("stop_duration_stats") or {}
        lines.append("### Stop duration")
        if sr and ss:
            m_r, m_s = sr.get("mean_sec"), ss.get("mean_sec")
            med_r, med_s = sr.get("median_sec"), ss.get("median_sec")
            p_r, p_s = sr.get("proportion_long_stops", 0), ss.get("proportion_long_stops", 0)
            diff_mean = (m_r - m_s) if (m_r is not None and m_s is not None) else None
            diff_prop = (p_r - p_s) if (p_r is not None and p_s is not None) else None
            lines.append(f"- **Real:** n_stops = {sr.get('n_stops', '—')}, mean = {m_r} s, median = {med_r} s, proportion of long stops (>30 s) = {p_r:.2%}.")
            lines.append(f"- **Simulated:** n_stops = {ss.get('n_stops', '—')}, mean = {m_s} s, median = {med_s} s, proportion long = {p_s:.2%}.")
            if diff_mean is not None:
                lines.append(f"- **Comparison:** difference in means = {diff_mean:.2f} s; difference in proportion long = {diff_prop:.2%}.")
                if diff_mean > 2:
                    lines.append("  Real stops are on average longer — simulation produces more short dwells.")
                elif diff_mean < -2:
                    lines.append("  Simulated stops are on average longer — model overestimates dwell time.")
                else:
                    lines.append("  Stop duration distributions are similar.")
            ok_mean = "✓" if (diff_mean is not None and abs(diff_mean) < 3) else "✗"
            ok_prop = "✓" if (diff_prop is not None and abs(diff_prop) < 0.10) else "✗"
            lines.append(f"- **Targets:** |mean diff| < 3 s {ok_mean}; |proportion long diff| < 10% {ok_prop}.")
        else:
            lines.append("No stop statistics for real or simulated (trajectories with timestamps required).")
        lines.append("")
        lines.append("### Recommendations (targets to aim for)")
        lines.append("- **Density:** Spearman ρ ≥ 0.7 for good spatial agreement; NMAE ≤ 1.0 for acceptable magnitude errors. Ratio sim/real between 0.8 and 1.2 indicates similar overall activity level.")
        lines.append("- **ToP:** Same as density (Spearman ≥ 0.7, NMAE ≤ 1.0). Global ToP ratio near 1.0 means total presence time is well matched.")
        lines.append("- **Stop duration:** |Difference in mean stop duration| < 3 s and |difference in proportion of long stops| < 10% suggest similar dwelling behaviour.")
        lines.append("")
        lines.append("---")
        lines.append("*Summary generated from metrics computed in the cells above.*")
    display(Markdown("\n".join(lines)))
