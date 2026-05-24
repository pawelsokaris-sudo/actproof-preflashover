"""
Secondary Controls — Test A: Stratified FO Baseline
=====================================================
Read-only analysis on existing raw_results_full.json data.

Tests whether observed median lag +44 is significantly different from
a baseline that has the SAME bias to early plies as real FO.

Procedure:
1. Extract empirical FO_ply distribution from n=35 valid games.
2. For each of 35 games, generate pseudo-FO sampled from that empirical distribution.
3. Compute pseudo-lag = TP_ply - pseudo-FO_ply.
4. Repeat 1000x with seeds 42..1041.
5. Report: median pseudo-lag, 95% interval, whether observed +44 is inside.
"""

import json
import numpy as np
import os
import sys
from datetime import datetime

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_a.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_A: {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def main():
    log("START")
    
    with open(RAW_FILE, 'r') as f:
        data = json.load(f)
    
    valid = [g for g in data if g['excluded_reason'] is None]
    n = len(valid)
    log(f"Valid games: {n}")
    
    fo_plies = np.array([g['fo_ply'] for g in valid])
    tp_plies = np.array([g['tp_ply'] for g in valid])
    observed_lags = tp_plies - fo_plies
    observed_median = float(np.median(observed_lags))
    
    log(f"Observed FO_ply: median={np.median(fo_plies)}, mean={np.mean(fo_plies):.1f}")
    log(f"Observed TP_ply: median={np.median(tp_plies)}, mean={np.mean(tp_plies):.1f}")
    log(f"Observed median lag: {observed_median}")
    
    # Empirical FO distribution = the 35 FO_ply values themselves
    empirical_fo = fo_plies.copy()
    
    N_SIMS = 1000
    SEED_START = 42
    
    log(f"Running {N_SIMS} simulations (seeds {SEED_START}..{SEED_START + N_SIMS - 1})")
    
    sim_medians = []
    sim_means = []
    
    for i in range(N_SIMS):
        rng = np.random.RandomState(SEED_START + i)
        # Sample pseudo-FO from empirical distribution (with replacement)
        pseudo_fo = rng.choice(empirical_fo, size=n, replace=True)
        pseudo_lags = tp_plies - pseudo_fo
        sim_medians.append(float(np.median(pseudo_lags)))
        sim_means.append(float(np.mean(pseudo_lags)))
    
    sim_medians = np.array(sim_medians)
    sim_means = np.array(sim_means)
    
    # Results
    median_of_medians = float(np.median(sim_medians))
    mean_of_medians = float(np.mean(sim_medians))
    p2_5 = float(np.percentile(sim_medians, 2.5))
    p97_5 = float(np.percentile(sim_medians, 97.5))
    p5 = float(np.percentile(sim_medians, 5))
    p95 = float(np.percentile(sim_medians, 95))
    
    # Where does observed +44 fall?
    pct_below = float(np.mean(sim_medians < observed_median) * 100)
    pct_equal_or_below = float(np.mean(sim_medians <= observed_median) * 100)
    
    result = {
        'test': 'A',
        'test_name': 'Stratified FO Baseline',
        'n_valid': n,
        'n_simulations': N_SIMS,
        'seed_range': [SEED_START, SEED_START + N_SIMS - 1],
        'observed_median_lag': observed_median,
        'stratified_baseline': {
            'median_of_medians': median_of_medians,
            'mean_of_medians': mean_of_medians,
            'ci_95': [p2_5, p97_5],
            'ci_90': [p5, p95],
            'min': float(np.min(sim_medians)),
            'max': float(np.max(sim_medians)),
        },
        'observed_percentile': pct_equal_or_below,
        'observed_within_95ci': p2_5 <= observed_median <= p97_5,
        'interpretation': None  # filled below
    }
    
    if p2_5 <= observed_median <= p97_5:
        result['interpretation'] = (
            f"Observed +{observed_median:.0f} falls WITHIN the 95% interval "
            f"[{p2_5:.1f}, {p97_5:.1f}] of the stratified baseline "
            f"(median={median_of_medians:.1f}). "
            f"Structural confound fully explains the observed effect."
        )
    elif observed_median > p97_5:
        result['interpretation'] = (
            f"Observed +{observed_median:.0f} is ABOVE the 95% interval "
            f"[{p2_5:.1f}, {p97_5:.1f}] of the stratified baseline "
            f"(median={median_of_medians:.1f}). "
            f"Residual signal above structural shift."
        )
    else:
        result['interpretation'] = (
            f"Observed +{observed_median:.0f} is BELOW the 95% interval "
            f"[{p2_5:.1f}, {p97_5:.1f}] of the stratified baseline "
            f"(median={median_of_medians:.1f}). Anomalous."
        )
    
    log(f"Stratified baseline median: {median_of_medians:.1f}")
    log(f"Stratified baseline 95% CI: [{p2_5:.1f}, {p97_5:.1f}]")
    log(f"Observed +{observed_median:.0f} within 95% CI: {result['observed_within_95ci']}")
    log(f"Observed percentile in distribution: {pct_equal_or_below:.1f}%")
    log(f"Interpretation: {result['interpretation']}")
    
    # Save cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Results cached to {CACHE_FILE}")
    
    log("DONE")
    
    # Print summary for console
    print("\n" + "="*60)
    print("TEST A — Stratified FO Baseline")
    print("="*60)
    print(f"Observed median lag:          +{observed_median:.0f} ply")
    print(f"Stratified baseline median:   +{median_of_medians:.1f} ply")
    print(f"Stratified baseline 95% CI:   [{p2_5:.1f}, {p97_5:.1f}]")
    print(f"Observed within 95% CI:       {result['observed_within_95ci']}")
    print(f"Observed percentile:          {pct_equal_or_below:.1f}%")
    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)

if __name__ == '__main__':
    main()
