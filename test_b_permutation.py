"""
Secondary Controls — Test B-permutation: Phase-matched Permutation Baseline
=============================================================================
Phase-matched permutation test for lag significance.

For each of 35 games:
  1. Determine which phase bucket the real FO_ply falls into:
     [0-20], [20-40], [40-60], [60+]
  2. Generate pseudo-FO sampled uniformly from within that same bucket
     (constrained to [0, game_length])
  3. Compute pseudo-lag = TP_ply - pseudo-FO_ply

Repeat 1000x with seeds 42..1041.
Compare observed median lag to the permutation distribution.

This is more conservative than Test A: it respects the phase structure
(early vs mid vs late) while randomizing within-phase.

Read-only on existing data.
"""

import json
import os
import numpy as np
from datetime import datetime
from typing import List, Tuple

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_b_perm.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')

N_PERMUTATIONS = 1000
SEED_START = 42

# Phase buckets defined BEFORE analysis (preregistered in brief)
PHASE_BUCKETS = [(0, 20), (20, 40), (40, 60), (60, None)]  # None = game_length


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_B_PERM: {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode())
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def get_phase_bucket(fo_ply: int) -> Tuple[int, int]:
    """Return the (lo, hi) phase bucket for this fo_ply."""
    for lo, hi in PHASE_BUCKETS:
        if hi is None:
            return (lo, None)
        if fo_ply < hi:
            return (lo, hi)
    return (60, None)


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

    fo_plies = np.array([g['fo_ply'] for g in valid], dtype=float)
    tp_plies = np.array([g['tp_ply'] for g in valid], dtype=float)
    game_lens = np.array([g['n_plies'] for g in valid], dtype=float)
    observed_lags = tp_plies - fo_plies
    observed_median_lag = float(np.median(observed_lags))
    log(f"Observed median lag: {observed_median_lag}")

    # Phase bucket assignment
    bucket_assignments = []
    bucket_counts = {}
    for g in valid:
        bucket = get_phase_bucket(g['fo_ply'])
        bucket_assignments.append(bucket)
        key = f"{bucket[0]}-{bucket[1] if bucket[1] else 'end'}"
        bucket_counts[key] = bucket_counts.get(key, 0) + 1
    log(f"Phase bucket distribution: {bucket_counts}")

    # Permutation test
    perm_median_lags = []
    for seed in range(SEED_START, SEED_START + N_PERMUTATIONS):
        rng = np.random.RandomState(seed)
        pseudo_lags = []
        for i, g in enumerate(valid):
            lo, hi = bucket_assignments[i]
            # Upper bound: min(bucket_hi, game_length), but also must be < TP_ply
            # (FO must come before TP for lag to be positive)
            upper = int(game_lens[i])
            if hi is not None:
                upper = min(hi, upper)
            # Sample pseudo-FO uniformly in [lo, upper)
            if upper <= lo:
                # Edge case: bucket wider than game, use lo
                pseudo_fo = lo
            else:
                pseudo_fo = rng.randint(lo, upper)
            pseudo_lag = tp_plies[i] - pseudo_fo
            pseudo_lags.append(pseudo_lag)
        perm_median_lags.append(float(np.median(pseudo_lags)))

    perm_arr = np.array(perm_median_lags)
    perm_median = float(np.median(perm_arr))
    perm_mean = float(np.mean(perm_arr))
    perm_ci_lo = float(np.percentile(perm_arr, 2.5))
    perm_ci_hi = float(np.percentile(perm_arr, 97.5))
    perm_percentile = float(np.mean(perm_arr <= observed_median_lag) * 100)

    log(f"Permutation baseline: median={perm_median:.1f}, "
        f"95% CI=[{perm_ci_lo:.1f}, {perm_ci_hi:.1f}]")
    log(f"Observed {observed_median_lag:.0f} at percentile {perm_percentile:.1f}%")

    # Is observed within 95% CI?
    within_ci = bool(perm_ci_lo <= observed_median_lag <= perm_ci_hi)
    log(f"Within 95% CI: {within_ci}")

    result = {
        'test': 'B-permutation',
        'test_name': 'Phase-matched Permutation Baseline',
        'n_valid': len(valid),
        'n_permutations': N_PERMUTATIONS,
        'seed_range': [SEED_START, SEED_START + N_PERMUTATIONS - 1],
        'phase_buckets': [[lo, hi] for lo, hi in PHASE_BUCKETS],
        'bucket_distribution': bucket_counts,
        'observed_median_lag': observed_median_lag,
        'permutation_distribution': {
            'median': perm_median,
            'mean': perm_mean,
            'ci_95_lo': perm_ci_lo,
            'ci_95_hi': perm_ci_hi,
            'std': float(np.std(perm_arr)),
        },
        'observed_percentile': perm_percentile,
        'observed_within_95ci': within_ci,
        'interpretation': None,
    }

    if within_ci:
        result['interpretation'] = (
            f"Observed median lag (+{observed_median_lag:.0f}) falls WITHIN "
            f"the phase-matched 95% CI [{perm_ci_lo:.1f}, {perm_ci_hi:.1f}] "
            f"(baseline median = +{perm_median:.1f}, percentile = {perm_percentile:.1f}%). "
            f"Even when controlling for phase (early/mid/late), the lag is "
            f"fully explained by the structural position of FO within its phase bucket."
        )
    else:
        if observed_median_lag > perm_ci_hi:
            result['interpretation'] = (
                f"Observed median lag (+{observed_median_lag:.0f}) is ABOVE "
                f"the phase-matched 95% CI [{perm_ci_lo:.1f}, {perm_ci_hi:.1f}] "
                f"(baseline median = +{perm_median:.1f}, percentile = {perm_percentile:.1f}%). "
                f"Even after phase-matching, the observed lag exceeds the "
                f"structural baseline — partial residual signal."
            )
        else:
            result['interpretation'] = (
                f"Observed median lag (+{observed_median_lag:.0f}) is BELOW "
                f"the phase-matched 95% CI [{perm_ci_lo:.1f}, {perm_ci_hi:.1f}]. "
                f"Unexpected result."
            )

    log(f"Interpretation: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST B-permutation: Phase-matched Permutation Baseline")
    print("="*60)
    print(f"\nPhase buckets: {result['phase_buckets']}")
    print(f"Bucket distribution: {result['bucket_distribution']}")
    print(f"\nObserved median lag: +{result['observed_median_lag']:.0f}")
    pd = result['permutation_distribution']
    print(f"Permutation baseline (n={result['n_permutations']}):")
    print(f"  Median: +{pd['median']:.1f}")
    print(f"  95% CI: [{pd['ci_95_lo']:.1f}, {pd['ci_95_hi']:.1f}]")
    print(f"  Std: {pd['std']:.1f}")
    print(f"\nObserved percentile: {result['observed_percentile']:.1f}%")
    print(f"Within 95% CI: {result['observed_within_95ci']}")
    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
