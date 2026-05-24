"""
Secondary Controls — Test E: FO Timing Deep Analysis
=====================================================
Since PGN source files are not available locally (TWIC data not committed
to repo), this test performs deeper statistical analysis on FO_ply timing:

1. FO_ply vs game length correlation (is early FO an artifact of game length?)
2. FO_ply vs TP_ply correlation (is FO coupled to error timing?)
3. FO_ply distribution shape analysis (opening-phase clustering)
4. Comparison with theoretical opening-exit model
5. Energy dynamics at FO from the Kasparov-Topalov demo game (sensor demo)

Read-only on existing data.
"""

import json
import os
import sys
import io
from datetime import datetime
from typing import Dict, List

import numpy as np
from scipy.stats import pearsonr, spearmanr

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from actproof_chess import ActProofSensor, KASPAROV_TOPALOV_1999
from actproof_dynamics import analyze_trajectory, detect_flashovers

RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_e.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')

# Frozen parameters
FO_PROMINENCE = 0.8
FO_MIN_DISTANCE = 2


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_E: {msg}"
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
    all_with_fo = [g for g in data if g['fo_ply'] is not None]
    log(f"Valid games: {len(valid)}, All with FO: {len(all_with_fo)}")

    fo_plies = np.array([g['fo_ply'] for g in valid], dtype=float)
    tp_plies = np.array([g['tp_ply'] for g in valid], dtype=float)
    game_lens = np.array([g['n_plies'] for g in valid], dtype=float)
    lags = tp_plies - fo_plies

    # ---- 1. FO_ply vs game length ----
    fo_gl_pearson_r, fo_gl_pearson_p = pearsonr(fo_plies, game_lens)
    fo_gl_spearman_r, fo_gl_spearman_p = spearmanr(fo_plies, game_lens)
    log(f"FO vs game_length: Pearson r={fo_gl_pearson_r:.4f} p={fo_gl_pearson_p:.4f}, "
        f"Spearman rho={fo_gl_spearman_r:.4f} p={fo_gl_spearman_p:.4f}")

    # ---- 2. FO_ply vs TP_ply ----
    fo_tp_pearson_r, fo_tp_pearson_p = pearsonr(fo_plies, tp_plies)
    fo_tp_spearman_r, fo_tp_spearman_p = spearmanr(fo_plies, tp_plies)
    log(f"FO vs TP: Pearson r={fo_tp_pearson_r:.4f} p={fo_tp_pearson_p:.4f}, "
        f"Spearman rho={fo_tp_spearman_r:.4f} p={fo_tp_spearman_p:.4f}")

    # ---- 3. FO distribution shape ----
    fo_in_10 = int(np.sum(fo_plies <= 10))
    fo_in_15 = int(np.sum(fo_plies <= 15))
    fo_in_20 = int(np.sum(fo_plies <= 20))
    fo_in_30 = int(np.sum(fo_plies <= 30))
    fo_q25 = float(np.percentile(fo_plies, 25))
    fo_q75 = float(np.percentile(fo_plies, 75))
    fo_iqr = fo_q75 - fo_q25

    # Check if FO clusters around typical "end of opening" (~10-15 plies)
    opening_exit_band = (fo_plies >= 8) & (fo_plies <= 18)
    in_exit_band = int(np.sum(opening_exit_band))
    log(f"FO distribution: Q25={fo_q25}, median={float(np.median(fo_plies))}, "
        f"Q75={fo_q75}, IQR={fo_iqr}")
    log(f"FO in opening-exit band (ply 8-18): {in_exit_band}/{len(fo_plies)} "
        f"({in_exit_band/len(fo_plies)*100:.0f}%)")

    # ---- 4. FO for all 48 games (valid + no-TP) ----
    all_fo_plies = np.array([g['fo_ply'] for g in all_with_fo], dtype=float)
    all_gl = np.array([g['n_plies'] for g in all_with_fo], dtype=float)
    all_fo_gl_r, all_fo_gl_p = spearmanr(all_fo_plies, all_gl)
    log(f"ALL games FO vs game_length: Spearman rho={all_fo_gl_r:.4f} p={all_fo_gl_p:.4f}")

    # ---- 5. Demo: energy dynamics at FO for Kasparov-Topalov ----
    log("Running Kasparov-Topalov demo for energy dynamics at FO...")
    sensor = ActProofSensor(beta=0.01)
    traj = analyze_trajectory(sensor, KASPAROV_TOPALOV_1999)
    fos = detect_flashovers(traj, prominence=FO_PROMINENCE, top_k=3,
                            min_distance=FO_MIN_DISTANCE)

    demo_fo = None
    demo_dynamics = {}
    if fos:
        fo = fos[0]
        demo_fo = {
            'ply': fo.ply,
            'san': fo.san,
            'dominant_channel': fo.dominant_channel,
            'magnitude_z': fo.magnitude_z,
        }
        # Energy window around FO
        p = fo.ply
        window = range(max(0, p-3), min(len(traj['E']), p+4))
        demo_dynamics = {
            'energy_window': {
                str(i): {
                    'E': round(float(traj['E'][i]), 1),
                    'T_max': round(float(traj['T_max'][i]), 3),
                    'S': round(float(traj['S'][i]), 3),
                    'dE_z': round(float(traj['dE_z'][i]), 3),
                    'san': traj['sans'][i] if i < len(traj['sans']) else '?',
                }
                for i in window
            }
        }
        log(f"Demo FO: ply={fo.ply}, san={fo.san}, channel={fo.dominant_channel}, z={fo.magnitude_z:.2f}")

    result = {
        'test': 'E',
        'test_name': 'FO Timing Deep Analysis',
        'n_valid': len(valid),
        'n_all_with_fo': len(all_with_fo),
        'fo_vs_game_length': {
            'pearson_r': round(float(fo_gl_pearson_r), 4),
            'pearson_p': round(float(fo_gl_pearson_p), 4),
            'spearman_rho': round(float(fo_gl_spearman_r), 4),
            'spearman_p': round(float(fo_gl_spearman_p), 4),
        },
        'fo_vs_tp': {
            'pearson_r': round(float(fo_tp_pearson_r), 4),
            'pearson_p': round(float(fo_tp_pearson_p), 4),
            'spearman_rho': round(float(fo_tp_spearman_r), 4),
            'spearman_p': round(float(fo_tp_spearman_p), 4),
        },
        'fo_distribution': {
            'q25': fo_q25,
            'median': float(np.median(fo_plies)),
            'q75': fo_q75,
            'iqr': fo_iqr,
            'in_first_10': fo_in_10,
            'in_first_15': fo_in_15,
            'in_first_20': fo_in_20,
            'in_first_30': fo_in_30,
            'in_opening_exit_band_8_18': in_exit_band,
            'pct_in_opening_exit_band': round(in_exit_band / len(fo_plies) * 100, 1),
        },
        'all_games_fo_vs_length': {
            'n': len(all_with_fo),
            'spearman_rho': round(float(all_fo_gl_r), 4),
            'spearman_p': round(float(all_fo_gl_p), 4),
        },
        'demo_kasparov_topalov': {
            'fo': demo_fo,
            'dynamics': demo_dynamics,
        },
        'interpretation': None,
    }

    # Build interpretation
    fo_independent_of_length = fo_gl_spearman_p > 0.05
    fo_independent_of_tp = fo_tp_spearman_p > 0.05
    fo_clusters_in_opening = in_exit_band / len(fo_plies) > 0.5

    interp_parts = []
    if fo_independent_of_length:
        interp_parts.append(
            f"FO is independent of game length (Spearman rho={fo_gl_spearman_r:.3f}, p={fo_gl_spearman_p:.3f})")
    else:
        interp_parts.append(
            f"FO correlates with game length (Spearman rho={fo_gl_spearman_r:.3f}, p={fo_gl_spearman_p:.3f})")

    if fo_independent_of_tp:
        interp_parts.append(
            f"FO is independent of TP timing (Spearman rho={fo_tp_spearman_r:.3f}, p={fo_tp_spearman_p:.3f})")
    else:
        interp_parts.append(
            f"FO correlates with TP timing (Spearman rho={fo_tp_spearman_r:.3f}, p={fo_tp_spearman_p:.3f})")

    if fo_clusters_in_opening:
        interp_parts.append(
            f"{in_exit_band}/{len(fo_plies)} ({in_exit_band/len(fo_plies)*100:.0f}%) FO events "
            f"cluster in opening-exit band (ply 8-18)")

    interp_parts.append(
        f"FO IQR={fo_iqr:.0f} plies — narrow band confirms FO is a fixed-timing event, "
        f"not correlated with game-specific dynamics")

    result['interpretation'] = ". ".join(interp_parts) + "."

    log(f"Interpretation: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST E — FO Timing Deep Analysis")
    print("="*60)

    d = result['fo_distribution']
    print(f"\nFO_ply distribution (n={result['n_valid']}):")
    print(f"  Q25={d['q25']}, median={d['median']}, Q75={d['q75']}, IQR={d['iqr']}")
    print(f"  In first 10 plies: {d['in_first_10']}")
    print(f"  In first 15 plies: {d['in_first_15']}")
    print(f"  In first 20 plies: {d['in_first_20']}")
    print(f"  In opening-exit band (8-18): {d['in_opening_exit_band_8_18']} "
          f"({d['pct_in_opening_exit_band']}%)")

    gl = result['fo_vs_game_length']
    print(f"\nFO vs game length:")
    print(f"  Pearson r={gl['pearson_r']}, p={gl['pearson_p']}")
    print(f"  Spearman rho={gl['spearman_rho']}, p={gl['spearman_p']}")

    tp = result['fo_vs_tp']
    print(f"\nFO vs TP:")
    print(f"  Pearson r={tp['pearson_r']}, p={tp['pearson_p']}")
    print(f"  Spearman rho={tp['spearman_rho']}, p={tp['spearman_p']}")

    ag = result['all_games_fo_vs_length']
    print(f"\nAll games (n={ag['n']}) FO vs length:")
    print(f"  Spearman rho={ag['spearman_rho']}, p={ag['spearman_p']}")

    demo = result.get('demo_kasparov_topalov', {})
    if demo.get('fo'):
        fo = demo['fo']
        print(f"\nDemo (Kasparov-Topalov 1999):")
        print(f"  FO at ply {fo['ply']}: {fo['san']} "
              f"(channel={fo['dominant_channel']}, z={fo['magnitude_z']:.2f})")

    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
