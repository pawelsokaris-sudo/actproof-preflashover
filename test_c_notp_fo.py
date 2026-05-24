"""
Secondary Controls — Test C: Non-TP Games FO Analysis
======================================================
Read-only analysis on existing raw_results_full.json data.

Tests whether the 13 games excluded for no_tp_in_first_80_plies have
similar FO_ply distribution to the 35 valid games.

If similar → FO is independent of TP existence → opening-structural confound.
If different → FO may be coupled to game dynamics that produce TP.
"""

import json
import os
import numpy as np
from datetime import datetime
from scipy.stats import mannwhitneyu, ks_2samp

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_c.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_C: {msg}"
    print(line)
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
    no_tp = [g for g in data if g['excluded_reason'] == 'no_tp_in_first_80_plies']
    timeout = [g for g in data if g['excluded_reason'] == 'position_timeout']

    log(f"Valid games: {len(valid)}")
    log(f"No-TP games: {len(no_tp)}")
    log(f"Timeout games: {len(timeout)}")

    # FO_ply for valid games
    valid_fo = [g['fo_ply'] for g in valid]
    # FO_ply for no-TP games (already computed!)
    no_tp_fo = [g['fo_ply'] for g in no_tp if g['fo_ply'] is not None]

    log(f"Valid FO_ply available: {len(valid_fo)}/{len(valid)}")
    log(f"No-TP FO_ply available: {len(no_tp_fo)}/{len(no_tp)}")

    # Per-game detail for no-TP
    no_tp_details = []
    for g in no_tp:
        no_tp_details.append({
            'game_id': g['game_id'],
            'fo_ply': g['fo_ply'],
            'n_plies': g['n_plies'],
            'white': g['white'],
            'black': g['black'],
        })
        log(f"  No-TP game {g['game_id']}: fo_ply={g['fo_ply']}, n_plies={g['n_plies']}")

    valid_arr = np.array(valid_fo, dtype=float)
    no_tp_arr = np.array(no_tp_fo, dtype=float)

    # Descriptive stats
    valid_median = float(np.median(valid_arr))
    valid_mean = float(np.mean(valid_arr))
    no_tp_median = float(np.median(no_tp_arr))
    no_tp_mean = float(np.mean(no_tp_arr))

    log(f"Valid FO: median={valid_median}, mean={valid_mean:.1f}")
    log(f"No-TP FO: median={no_tp_median}, mean={no_tp_mean:.1f}")

    # Statistical tests
    u_stat, u_pval = mannwhitneyu(valid_arr, no_tp_arr, alternative='two-sided')
    ks_stat, ks_pval = ks_2samp(valid_arr, no_tp_arr)

    log(f"Mann-Whitney U: U={u_stat:.1f}, p={u_pval:.6f}")
    log(f"KS: D={ks_stat:.4f}, p={ks_pval:.6f}")

    # Percentage in first 20 plies
    valid_early = sum(1 for f in valid_fo if f <= 20) / len(valid_fo) * 100
    no_tp_early = sum(1 for f in no_tp_fo if f <= 20) / len(no_tp_fo) * 100

    # Combined (all 48 games with FO, excluding 2 timeout)
    all_fo = valid_fo + no_tp_fo
    all_arr = np.array(all_fo, dtype=float)
    combined_median = float(np.median(all_arr))
    combined_mean = float(np.mean(all_arr))
    combined_early = sum(1 for f in all_fo if f <= 20) / len(all_fo) * 100

    result = {
        'test': 'C',
        'test_name': 'Non-TP Games FO Analysis',
        'n_valid': len(valid),
        'n_no_tp': len(no_tp),
        'n_no_tp_with_fo': len(no_tp_fo),
        'n_timeout': len(timeout),
        'valid_fo': {
            'median': valid_median,
            'mean': valid_mean,
            'std': float(np.std(valid_arr)),
            'pct_in_first_20': valid_early,
        },
        'no_tp_fo': {
            'median': no_tp_median,
            'mean': no_tp_mean,
            'std': float(np.std(no_tp_arr)),
            'pct_in_first_20': no_tp_early,
        },
        'combined_fo': {
            'n': len(all_fo),
            'median': combined_median,
            'mean': combined_mean,
            'pct_in_first_20': combined_early,
        },
        'mann_whitney': {
            'U_statistic': float(u_stat),
            'p_value': float(u_pval),
            'significant_at_005': bool(u_pval < 0.05),
        },
        'kolmogorov_smirnov': {
            'KS_statistic': float(ks_stat),
            'p_value': float(ks_pval),
            'significant_at_005': bool(ks_pval < 0.05),
        },
        'no_tp_details': no_tp_details,
        'interpretation': None,
    }

    if u_pval >= 0.05 and ks_pval >= 0.05:
        result['interpretation'] = (
            f"FO_ply distributions are NOT significantly different between "
            f"valid (median={valid_median:.0f}) and no-TP (median={no_tp_median:.0f}) games "
            f"(MW p={u_pval:.4f}, KS p={ks_pval:.4f}). "
            f"FO timing is independent of TP existence. "
            f"Supports opening-structural interpretation."
        )
    else:
        result['interpretation'] = (
            f"FO_ply distributions ARE significantly different between "
            f"valid (median={valid_median:.0f}) and no-TP (median={no_tp_median:.0f}) games "
            f"(MW p={u_pval:.4f}, KS p={ks_pval:.4f}). "
            f"FO timing may be coupled to game dynamics."
        )

    log(f"Interpretation: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST C — Non-TP Games FO Analysis")
    print("="*60)
    v = result['valid_fo']
    n = result['no_tp_fo']
    print(f"Valid games (TP+FO, n={result['n_valid']}):")
    print(f"  FO_ply median={v['median']:.0f}, mean={v['mean']:.1f}, "
          f"{v['pct_in_first_20']:.0f}% in first 20 plies")
    print(f"No-TP games (n={result['n_no_tp']}, FO available: {result['n_no_tp_with_fo']}):")
    print(f"  FO_ply median={n['median']:.0f}, mean={n['mean']:.1f}, "
          f"{n['pct_in_first_20']:.0f}% in first 20 plies")
    c = result['combined_fo']
    print(f"Combined (n={c['n']}):")
    print(f"  FO_ply median={c['median']:.0f}, mean={c['mean']:.1f}, "
          f"{c['pct_in_first_20']:.0f}% in first 20 plies")
    print()
    mw = result['mann_whitney']
    ks = result['kolmogorov_smirnov']
    print(f"Mann-Whitney U:     U={mw['U_statistic']:.1f}, p={mw['p_value']:.6f}  "
          f"{'*** SIG' if mw['significant_at_005'] else 'n.s.'}")
    print(f"Kolmogorov-Smirnov: D={ks['KS_statistic']:.4f}, p={ks['p_value']:.6f}  "
          f"{'*** SIG' if ks['significant_at_005'] else 'n.s.'}")
    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
