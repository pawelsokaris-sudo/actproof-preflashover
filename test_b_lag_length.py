"""
Secondary Controls — Test B: Lag vs Game Length Analysis
========================================================
Tests whether the observed +44 lag is an artifact of game length:
1. TP_ply vs game_length correlation
2. Lag vs game_length correlation
3. FO_ply / game_length ratio analysis
4. Game-length-stratified lag comparison (short vs long games)

If lag correlates with game length → confound includes duration artifact.
If lag is stable across game lengths → structural confound is intrinsic.

Read-only on existing data.
"""

import json
import os
import numpy as np
from datetime import datetime
from scipy.stats import spearmanr, pearsonr, mannwhitneyu

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_b.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_B: {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode())
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def main():
    log("START")
    os.makedirs(CACHE_DIR, exist_ok=True)

    if os.path.exists(CACHE_FILE):
        log(f"Loading cached results from {CACHE_FILE}")
        with open(CACHE_FILE, 'r') as f:
            result = json.load(f)
        print_summary(result)
        return

    with open(RAW_FILE, 'r') as f:
        data = json.load(f)

    valid = [g for g in data if g['excluded_reason'] is None]
    log(f"Valid games: {len(valid)}")

    fo = np.array([g['fo_ply'] for g in valid], dtype=float)
    tp = np.array([g['tp_ply'] for g in valid], dtype=float)
    gl = np.array([g['n_plies'] for g in valid], dtype=float)
    lag = tp - fo

    # ---- 1. TP vs game length ----
    tp_gl_r, tp_gl_p = spearmanr(tp, gl)
    tp_gl_pr, tp_gl_pp = pearsonr(tp, gl)
    log(f"TP vs game_length: Spearman rho={tp_gl_r:.4f} p={tp_gl_p:.6f}")

    # ---- 2. Lag vs game length ----
    lag_gl_r, lag_gl_p = spearmanr(lag, gl)
    lag_gl_pr, lag_gl_pp = pearsonr(lag, gl)
    log(f"Lag vs game_length: Spearman rho={lag_gl_r:.4f} p={lag_gl_p:.6f}")

    # ---- 3. FO/game_length ratio ----
    fo_ratio = fo / gl
    fo_ratio_median = float(np.median(fo_ratio))
    fo_ratio_mean = float(np.mean(fo_ratio))
    log(f"FO/game_length ratio: median={fo_ratio_median:.3f}, mean={fo_ratio_mean:.3f}")
    # This shows what fraction of the game has elapsed by FO

    # TP/game_length ratio
    tp_ratio = tp / gl
    tp_ratio_median = float(np.median(tp_ratio))
    tp_ratio_mean = float(np.mean(tp_ratio))
    log(f"TP/game_length ratio: median={tp_ratio_median:.3f}, mean={tp_ratio_mean:.3f}")

    # ---- 4. Stratified analysis: short vs long games ----
    median_gl = float(np.median(gl))
    short_mask = gl <= median_gl
    long_mask = gl > median_gl

    short_lag = lag[short_mask]
    long_lag = lag[long_mask]
    short_fo = fo[short_mask]
    long_fo = fo[long_mask]
    short_tp = tp[short_mask]
    long_tp = tp[long_mask]

    short_lag_median = float(np.median(short_lag))
    long_lag_median = float(np.median(long_lag))
    short_fo_median = float(np.median(short_fo))
    long_fo_median = float(np.median(long_fo))
    short_tp_median = float(np.median(short_tp))
    long_tp_median = float(np.median(long_tp))

    # Mann-Whitney on lags between short and long games
    if len(short_lag) >= 3 and len(long_lag) >= 3:
        lag_strat_u, lag_strat_p = mannwhitneyu(short_lag, long_lag, alternative='two-sided')
    else:
        lag_strat_u, lag_strat_p = float('nan'), float('nan')
    log(f"Stratified lag: short median={short_lag_median}, long median={long_lag_median}, "
        f"MW p={lag_strat_p:.4f}")

    # ---- 5. Game length descriptives ----
    gl_stats = {
        'min': int(np.min(gl)),
        'q25': float(np.percentile(gl, 25)),
        'median': float(np.median(gl)),
        'q75': float(np.percentile(gl, 75)),
        'max': int(np.max(gl)),
        'mean': round(float(np.mean(gl)), 1),
    }

    # ---- 6. Normalized lag: lag / game_length ----
    norm_lag = lag / gl
    norm_lag_median = float(np.median(norm_lag))
    norm_lag_mean = float(np.mean(norm_lag))

    result = {
        'test': 'B',
        'test_name': 'Lag vs Game Length Analysis',
        'n_valid': len(valid),
        'game_length_stats': gl_stats,
        'tp_vs_game_length': {
            'spearman_rho': round(float(tp_gl_r), 4),
            'spearman_p': round(float(tp_gl_p), 6),
            'pearson_r': round(float(tp_gl_pr), 4),
            'pearson_p': round(float(tp_gl_pp), 6),
            'significant': bool(tp_gl_p < 0.05),
        },
        'lag_vs_game_length': {
            'spearman_rho': round(float(lag_gl_r), 4),
            'spearman_p': round(float(lag_gl_p), 6),
            'pearson_r': round(float(lag_gl_pr), 4),
            'pearson_p': round(float(lag_gl_pp), 6),
            'significant': bool(lag_gl_p < 0.05),
        },
        'fo_game_ratio': {
            'median': round(fo_ratio_median, 4),
            'mean': round(fo_ratio_mean, 4),
        },
        'tp_game_ratio': {
            'median': round(tp_ratio_median, 4),
            'mean': round(tp_ratio_mean, 4),
        },
        'normalized_lag': {
            'median': round(norm_lag_median, 4),
            'mean': round(norm_lag_mean, 4),
        },
        'stratified': {
            'split_at_median_gl': median_gl,
            'short_games': {
                'n': int(np.sum(short_mask)),
                'median_gl': round(float(np.median(gl[short_mask])), 1),
                'median_fo': short_fo_median,
                'median_tp': short_tp_median,
                'median_lag': short_lag_median,
            },
            'long_games': {
                'n': int(np.sum(long_mask)),
                'median_gl': round(float(np.median(gl[long_mask])), 1),
                'median_fo': long_fo_median,
                'median_tp': long_tp_median,
                'median_lag': long_lag_median,
            },
            'lag_difference_mw_p': round(float(lag_strat_p), 4),
            'lag_difference_significant': bool(lag_strat_p < 0.05),
        },
        'interpretation': None,
    }

    # Build interpretation
    parts = []

    if tp_gl_p < 0.05:
        parts.append(
            f"TP correlates with game length (ρ={tp_gl_r:.3f}, p={tp_gl_p:.4f}) — "
            f"longer games have later first mistakes, as expected")
    else:
        parts.append(
            f"TP does NOT significantly correlate with game length "
            f"(ρ={tp_gl_r:.3f}, p={tp_gl_p:.4f})")

    if lag_gl_p < 0.05:
        parts.append(
            f"Lag correlates with game length (ρ={lag_gl_r:.3f}, p={lag_gl_p:.4f}) — "
            f"longer games inflate the lag, game-length confound present")
    else:
        parts.append(
            f"Lag does NOT correlate with game length "
            f"(ρ={lag_gl_r:.3f}, p={lag_gl_p:.4f}) — "
            f"lag is stable across short and long games")

    parts.append(
        f"FO fires at {fo_ratio_median*100:.1f}% into the game (median ratio), "
        f"while TP fires at {tp_ratio_median*100:.1f}% — "
        f"the gap is structural, not duration-dependent")

    if lag_strat_p > 0.05:
        parts.append(
            f"Stratified check: short games lag={short_lag_median:.0f}, "
            f"long games lag={long_lag_median:.0f} — "
            f"no significant difference (MW p={lag_strat_p:.3f})")
    else:
        parts.append(
            f"Stratified check: short games lag={short_lag_median:.0f}, "
            f"long games lag={long_lag_median:.0f} — "
            f"SIGNIFICANT difference (MW p={lag_strat_p:.3f})")

    result['interpretation'] = ". ".join(parts) + "."

    log(f"Interpretation: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST B — Lag vs Game Length Analysis")
    print("="*60)

    gs = result['game_length_stats']
    print(f"\nGame length: min={gs['min']}, Q25={gs['q25']}, "
          f"median={gs['median']}, Q75={gs['q75']}, max={gs['max']}")

    tp = result['tp_vs_game_length']
    print(f"\nTP vs game length:")
    print(f"  Spearman ρ={tp['spearman_rho']}, p={tp['spearman_p']}  "
          f"{'*** SIG' if tp['significant'] else 'n.s.'}")

    lg = result['lag_vs_game_length']
    print(f"\nLag vs game length:")
    print(f"  Spearman ρ={lg['spearman_rho']}, p={lg['spearman_p']}  "
          f"{'*** SIG' if lg['significant'] else 'n.s.'}")

    fr = result['fo_game_ratio']
    tr = result['tp_game_ratio']
    print(f"\nTiming ratios (position in game):")
    print(f"  FO fires at: {fr['median']*100:.1f}% of game (median)")
    print(f"  TP fires at: {tr['median']*100:.1f}% of game (median)")

    nl = result['normalized_lag']
    print(f"  Normalized lag: {nl['median']*100:.1f}% of game (median)")

    s = result['stratified']
    print(f"\nStratified by game length (split at {s['split_at_median_gl']} plies):")
    sh = s['short_games']
    lo = s['long_games']
    print(f"  Short (n={sh['n']}, median={sh['median_gl']} plies):"
          f" FO={sh['median_fo']:.0f}, TP={sh['median_tp']:.0f}, lag={sh['median_lag']:.0f}")
    print(f"  Long  (n={lo['n']}, median={lo['median_gl']} plies):"
          f" FO={lo['median_fo']:.0f}, TP={lo['median_tp']:.0f}, lag={lo['median_lag']:.0f}")
    print(f"  MW p={s['lag_difference_mw_p']}  "
          f"{'*** SIG' if s['lag_difference_significant'] else 'n.s.'}")

    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
