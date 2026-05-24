"""
Secondary Controls — Test F: Random-game Baseline
===================================================
Generates 50 random-vs-random games (uniform legal move selection),
runs the ActProof FO sensor on each, and compares FO_ply distribution
to the GM baseline (n=35 from v1.4 run).

If distributions are identical → sensor measures geometry, not decisions.
If significantly different → sensor detects something GM-specific.

NO Stockfish needed. NO TP analysis. FO only.
"""

import json
import os
import sys
import io
from datetime import datetime
from typing import List, Optional

import chess
import chess.pgn
import numpy as np
from scipy.stats import mannwhitneyu, ks_2samp

# Add project root to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from actproof_chess import ActProofSensor
from actproof_dynamics import analyze_trajectory, detect_flashovers

RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
RAW_FILE = os.path.join(RESULTS_DIR, 'raw_results_full.json')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_f.json')
CACHE_GAMES_FILE = os.path.join(CACHE_DIR, 'secondary_test_f_random_games.pgn')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')

# Frozen parameters matching data_collection.py
FO_PROMINENCE = 0.8
FO_MIN_DISTANCE = 2

N_RANDOM_GAMES = 50
MAX_PLIES = 200
SEED_START = 42


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_F: {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def generate_random_game(seed: int) -> chess.pgn.Game:
    """Generate one random-vs-random game (uniform legal move selection)."""
    rng = np.random.RandomState(seed)
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Random-vs-Random Baseline (Test F)"
    game.headers["White"] = f"Random-{seed}"
    game.headers["Black"] = f"Random-{seed}"
    game.headers["Result"] = "*"

    node = game
    ply_count = 0
    while not board.is_game_over() and ply_count < MAX_PLIES:
        legal = list(board.legal_moves)
        if not legal:
            break
        move = legal[rng.randint(len(legal))]
        node = node.add_variation(move)
        board.push(move)
        ply_count += 1

    # Set result
    if board.is_checkmate():
        game.headers["Result"] = "0-1" if board.turn == chess.WHITE else "1-0"
    elif board.is_stalemate():
        game.headers["Result"] = "1/2-1/2"
    elif board.can_claim_draw():
        game.headers["Result"] = "1/2-1/2"
    else:
        game.headers["Result"] = "1/2-1/2"  # hit max plies

    return game


def find_fo_for_game(game: chess.pgn.Game, sensor: ActProofSensor) -> Optional[int]:
    """Run the FO sensor on a game. Returns FO_ply or None."""
    pgn_text = str(game)
    traj = analyze_trajectory(sensor, pgn_text)
    if not traj or len(traj.get('plies', [])) < 3:
        return None
    fos = detect_flashovers(
        traj, prominence=FO_PROMINENCE, top_k=1, min_distance=FO_MIN_DISTANCE,
    )
    if not fos:
        return None
    return fos[0].ply


def main():
    log("START")
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Check for cached results
    if os.path.exists(CACHE_FILE):
        log(f"Loading cached results from {CACHE_FILE}")
        with open(CACHE_FILE, 'r') as f:
            result = json.load(f)
        print_summary(result)
        return

    # Load GM baseline
    with open(RAW_FILE, 'r') as f:
        raw_data = json.load(f)
    gm_valid = [g for g in raw_data if g['excluded_reason'] is None]
    gm_fo_plies = [g['fo_ply'] for g in gm_valid]
    log(f"GM baseline: n={len(gm_fo_plies)}, FO_ply median={np.median(gm_fo_plies)}")

    # Generate random games
    log(f"Generating {N_RANDOM_GAMES} random-vs-random games (seeds {SEED_START}..{SEED_START + N_RANDOM_GAMES - 1})")
    random_games = []
    game_stats = []
    for i in range(N_RANDOM_GAMES):
        seed = SEED_START + i
        game = generate_random_game(seed)
        n_plies = sum(1 for _ in game.mainline_moves())
        result_str = game.headers["Result"]
        if result_str == "1-0":
            end_type = "white_checkmate"
        elif result_str == "0-1":
            end_type = "black_checkmate"
        else:
            board = chess.Board()
            for mv in game.mainline_moves():
                board.push(mv)
            if board.is_stalemate():
                end_type = "stalemate"
            elif n_plies >= MAX_PLIES:
                end_type = "max_plies"
            else:
                end_type = "draw_claim"
        random_games.append(game)
        game_stats.append({
            'seed': seed,
            'n_plies': n_plies,
            'result': result_str,
            'end_type': end_type
        })
        if (i + 1) % 10 == 0:
            log(f"  Generated {i+1}/{N_RANDOM_GAMES}")

    # Save PGN
    with open(CACHE_GAMES_FILE, 'w') as f:
        for g in random_games:
            f.write(str(g) + '\n\n')
    log(f"Random games saved to {CACHE_GAMES_FILE}")

    # Report game statistics
    plies_list = [s['n_plies'] for s in game_stats]
    end_types = {}
    for s in game_stats:
        end_types[s['end_type']] = end_types.get(s['end_type'], 0) + 1
    log(f"Random game stats: n={len(plies_list)}, mean_plies={np.mean(plies_list):.1f}, "
        f"median_plies={np.median(plies_list):.1f}, min={min(plies_list)}, max={max(plies_list)}")
    log(f"End types: {end_types}")

    # Run FO sensor on each random game
    log("Running ActProof FO sensor on random games...")
    sensor = ActProofSensor(beta=0.01)
    random_fo_plies = []
    random_fo_results = []
    for i, game in enumerate(random_games):
        fo = find_fo_for_game(game, sensor)
        random_fo_plies.append(fo)
        random_fo_results.append({
            'seed': game_stats[i]['seed'],
            'n_plies': game_stats[i]['n_plies'],
            'end_type': game_stats[i]['end_type'],
            'fo_ply': fo
        })
        if (i + 1) % 5 == 0:
            log(f"  Analyzed {i+1}/{N_RANDOM_GAMES}")

    # Filter to those with detected FO
    random_fo_valid = [fo for fo in random_fo_plies if fo is not None]
    log(f"Random FO detected in {len(random_fo_valid)}/{N_RANDOM_GAMES} games")

    if len(random_fo_valid) == 0:
        log("ERROR: No FO detected in any random game. Cannot compare.")
        return

    # Comparison
    gm_arr = np.array(gm_fo_plies, dtype=float)
    rnd_arr = np.array(random_fo_valid, dtype=float)

    gm_median = float(np.median(gm_arr))
    gm_mean = float(np.mean(gm_arr))
    rnd_median = float(np.median(rnd_arr))
    rnd_mean = float(np.mean(rnd_arr))

    # Mann-Whitney U test
    u_stat, u_pval = mannwhitneyu(gm_arr, rnd_arr, alternative='two-sided')

    # Kolmogorov-Smirnov test
    ks_stat, ks_pval = ks_2samp(gm_arr, rnd_arr)

    # Histogram per 10-ply buckets
    buckets = list(range(0, 201, 10))
    gm_hist = np.histogram(gm_arr, bins=buckets)[0].tolist()
    rnd_hist = np.histogram(rnd_arr, bins=buckets)[0].tolist()

    result = {
        'test': 'F',
        'test_name': 'Random-game Baseline',
        'n_random_games': N_RANDOM_GAMES,
        'n_random_fo_detected': len(random_fo_valid),
        'n_gm_valid': len(gm_fo_plies),
        'seed_range': [SEED_START, SEED_START + N_RANDOM_GAMES - 1],
        'random_game_stats': {
            'mean_plies': float(np.mean(plies_list)),
            'median_plies': float(np.median(plies_list)),
            'min_plies': int(min(plies_list)),
            'max_plies': int(max(plies_list)),
            'end_types': end_types
        },
        'gm_fo': {
            'median': gm_median,
            'mean': gm_mean,
            'std': float(np.std(gm_arr)),
        },
        'random_fo': {
            'median': rnd_median,
            'mean': rnd_mean,
            'std': float(np.std(rnd_arr)),
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
        'histogram_10ply_buckets': {
            'bucket_edges': buckets,
            'gm_counts': gm_hist,
            'random_counts': rnd_hist,
        },
        'random_fo_per_game': random_fo_results,
        'interpretation': None  # filled below
    }

    # Interpretation
    if u_pval >= 0.05 and ks_pval >= 0.05:
        result['interpretation'] = (
            f"FO_ply distributions are NOT significantly different "
            f"(Mann-Whitney p={u_pval:.4f}, KS p={ks_pval:.4f}). "
            f"The sensor measures field geometry, not decision quality. "
            f"GM median FO={gm_median:.0f}, Random median FO={rnd_median:.0f}."
        )
    elif u_pval < 0.05 and ks_pval < 0.05:
        result['interpretation'] = (
            f"FO_ply distributions are significantly different "
            f"(Mann-Whitney p={u_pval:.4f}, KS p={ks_pval:.4f}). "
            f"The sensor detects something specific to GM play. "
            f"GM median FO={gm_median:.0f}, Random median FO={rnd_median:.0f}."
        )
    else:
        result['interpretation'] = (
            f"Mixed significance: Mann-Whitney p={u_pval:.4f}, KS p={ks_pval:.4f}. "
            f"GM median FO={gm_median:.0f}, Random median FO={rnd_median:.0f}. "
            f"Partial evidence — details in histogram comparison."
        )

    log(f"Result: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Results cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST F — Random-game Baseline")
    print("="*60)
    print(f"Random games generated:        {result['n_random_games']}")
    print(f"Random games with FO detected: {result['n_random_fo_detected']}")
    rgs = result['random_game_stats']
    print(f"Random game length:            mean={rgs['mean_plies']:.0f}, "
          f"median={rgs['median_plies']:.0f} plies")
    print(f"End types:                     {rgs['end_types']}")
    print()
    gm = result['gm_fo']
    rnd = result['random_fo']
    print(f"GM FO_ply:     median={gm['median']:.0f}, mean={gm['mean']:.1f}")
    print(f"Random FO_ply: median={rnd['median']:.0f}, mean={rnd['mean']:.1f}")
    print()
    mw = result['mann_whitney']
    ks = result['kolmogorov_smirnov']
    print(f"Mann-Whitney U:  U={mw['U_statistic']:.1f}, p={mw['p_value']:.6f}  "
          f"{'*** SIGNIFICANT' if mw['significant_at_005'] else 'not significant'}")
    print(f"Kolmogorov-Smirnov: KS={ks['KS_statistic']:.4f}, p={ks['p_value']:.6f}  "
          f"{'*** SIGNIFICANT' if ks['significant_at_005'] else 'not significant'}")
    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
