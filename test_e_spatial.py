"""
Secondary Controls — Test E-spatial: Per-piece Field Decomposition at FO
=========================================================================
Decomposes field energy by piece type at flashover moments.

Key question: which piece types contribute disproportionately to the
field energy at FO? Does the FO signal come from specific pieces
(e.g., minor piece development) or from the whole board?

Method: "removal energy" — for each piece type, compute E_total - E_without.
This captures both direct and cross-term contributions.

Data sources:
- Kasparov-Topalov 1999 (full trajectory, hardcoded in actproof_chess.py)
- 50 random games from Test F cache (for comparison)
- Starting position (reference)
"""

import json
import os
import sys
import io
from datetime import datetime
from typing import Dict, List

import chess
import chess.pgn
import numpy as np

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from actproof_chess import ActProofSensor, InformationField, FieldConfig, KASPAROV_TOPALOV_1999
from actproof_dynamics import analyze_trajectory, detect_flashovers

RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'secondary_test_e_spatial.json')
RANDOM_PGN = os.path.join(CACHE_DIR, 'secondary_test_f_random_games.pgn')
LOG_FILE = os.path.join(RESULTS_DIR, 'secondary_controls.log')

FO_PROMINENCE = 0.8
FO_MIN_DISTANCE = 2

PIECE_NAMES = {
    chess.PAWN: 'Pawn',
    chess.KNIGHT: 'Knight',
    chess.BISHOP: 'Bishop',
    chess.ROOK: 'Rook',
    chess.QUEEN: 'Queen',
    chess.KING: 'King',
}
PIECE_ORDER = ['King', 'Queen', 'Rook', 'Bishop', 'Knight', 'Pawn']


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] TEST_E_SPATIAL: {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode())
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def field_per_piece(board: chess.Board, field: InformationField) -> Dict[str, float]:
    """Removal energy per piece type.

    For each type T: removal_E[T] = E_total - E_without_T.
    Captures direct + cross-term contributions.
    Sum of removal energies != E_total (cross-terms counted multiple times).
    """
    Z_total = field.potential(board)
    E_total = field.dirichlet_energy(Z_total)

    result = {'total': E_total}
    for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
        temp = board.copy()
        for sq in chess.SQUARES:
            p = temp.piece_at(sq)
            if p and p.piece_type == pt:
                temp.remove_piece_at(sq)
        Z_without = field.potential(temp)
        E_without = field.dirichlet_energy(Z_without)
        result[PIECE_NAMES[pt]] = E_total - E_without
    return result


def get_piece_counts(board: chess.Board) -> Dict[str, int]:
    counts = {}
    for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
        counts[PIECE_NAMES[pt]] = len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK))
    return counts


def board_at_ply(pgn_text: str, ply: int) -> chess.Board:
    """Return board state after `ply` half-moves."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    board = game.board()
    for i, mv in enumerate(game.mainline_moves()):
        if i >= ply:
            break
        board.push(mv)
    return board


def find_fo_ply(pgn_text: str, sensor: ActProofSensor) -> int:
    """Find FO_ply for a game."""
    traj = analyze_trajectory(sensor, pgn_text)
    if not traj or len(traj.get('plies', [])) < 3:
        return None
    fos = detect_flashovers(traj, prominence=FO_PROMINENCE, top_k=1,
                            min_distance=FO_MIN_DISTANCE)
    if not fos:
        return None
    return fos[0].ply


def main():
    log("START")
    os.makedirs(CACHE_DIR, exist_ok=True)

    if os.path.exists(CACHE_FILE):
        log(f"Loading cached results from {CACHE_FILE}")
        with open(CACHE_FILE, 'r') as f:
            result = json.load(f)
        print_summary(result)
        return

    sensor = ActProofSensor(beta=0.01)
    field = sensor.field

    # ===== 1. Starting position reference =====
    log("Computing starting position decomposition...")
    start_board = chess.Board()
    start_decomp = field_per_piece(start_board, field)
    start_counts = get_piece_counts(start_board)
    log(f"  Start E_total={start_decomp['total']:.1f}")
    for p in PIECE_ORDER:
        log(f"  Start {p}: removal_E={start_decomp[p]:.1f}, "
            f"pct={start_decomp[p]/start_decomp['total']*100:.1f}%")

    # ===== 2. Kasparov-Topalov 1999: full trajectory =====
    log("Analyzing Kasparov-Topalov 1999...")
    kt_traj = analyze_trajectory(sensor, KASPAROV_TOPALOV_1999)
    kt_fos = detect_flashovers(kt_traj, prominence=FO_PROMINENCE, top_k=3,
                                min_distance=FO_MIN_DISTANCE)
    kt_fo_ply = kt_fos[0].ply if kt_fos else None
    log(f"  KT FO at ply {kt_fo_ply}: {kt_fos[0].san if kt_fos else '?'}")

    # Decomposition at key moments: start, FO-2, FO, FO+2, mid-game, late
    kt_game = chess.pgn.read_game(io.StringIO(KASPAROV_TOPALOV_1999))
    kt_moves = list(kt_game.mainline_moves())
    kt_n_plies = len(kt_moves)

    checkpoints = {
        'start': 0,
        'fo_minus_2': max(0, kt_fo_ply - 2),
        'fo': kt_fo_ply,
        'fo_plus_2': min(kt_n_plies, kt_fo_ply + 2),
        'mid_game': kt_n_plies // 2,
        'endgame': min(kt_n_plies, int(kt_n_plies * 0.85)),
    }

    kt_decompositions = {}
    for label, ply in checkpoints.items():
        board = kt_game.board()
        for i, mv in enumerate(kt_moves):
            if i >= ply:
                break
            board.push(mv)
        decomp = field_per_piece(board, field)
        counts = get_piece_counts(board)
        kt_decompositions[label] = {
            'ply': ply,
            'total_E': round(decomp['total'], 1),
            'pieces': {p: round(decomp[p], 1) for p in PIECE_ORDER},
            'pct': {p: round(decomp[p] / decomp['total'] * 100, 1) for p in PIECE_ORDER},
            'piece_counts': counts,
        }
        log(f"  KT ply {ply} ({label}): E={decomp['total']:.1f}")

    # ===== 3. Random games: decomposition at FO =====
    log("Analyzing random games at FO...")
    random_decomps = []
    if os.path.exists(RANDOM_PGN):
        with open(RANDOM_PGN, 'r') as f:
            pgn_text_all = f.read()

        # Parse individual games
        games_pgn = []
        reader = io.StringIO(pgn_text_all)
        while True:
            game = chess.pgn.read_game(reader)
            if game is None:
                break
            games_pgn.append(str(game))

        log(f"  Loaded {len(games_pgn)} random games from cache")

        # Sample 10 for decomposition (full 50 would take too long)
        sample_indices = list(range(0, min(len(games_pgn), 50), 5))  # every 5th
        for idx in sample_indices:
            pgn = games_pgn[idx]
            fo_ply = find_fo_ply(pgn, sensor)
            if fo_ply is None:
                continue
            board = board_at_ply(pgn, fo_ply)
            decomp = field_per_piece(board, field)
            counts = get_piece_counts(board)
            random_decomps.append({
                'game_idx': idx,
                'fo_ply': fo_ply,
                'total_E': round(decomp['total'], 1),
                'pieces': {p: round(decomp[p], 1) for p in PIECE_ORDER},
                'pct': {p: round(decomp[p] / decomp['total'] * 100, 1) for p in PIECE_ORDER},
                'piece_counts': counts,
            })
            if len(random_decomps) % 3 == 0:
                log(f"  Processed {len(random_decomps)} random games")

        log(f"  Total random decompositions: {len(random_decomps)}")
    else:
        log("  WARNING: Random games PGN not found, skipping")

    # ===== 4. Compute averages =====
    # Average random game decomposition at FO
    avg_random = {}
    if random_decomps:
        for p in PIECE_ORDER:
            vals = [d['pct'][p] for d in random_decomps]
            avg_random[p] = round(float(np.mean(vals)), 1)
        avg_random['avg_fo_ply'] = round(float(np.mean([d['fo_ply'] for d in random_decomps])), 1)
        avg_random['avg_total_E'] = round(float(np.mean([d['total_E'] for d in random_decomps])), 1)
        avg_random['n'] = len(random_decomps)
        # Average piece counts
        avg_random['avg_counts'] = {}
        for p in PIECE_ORDER:
            avg_random['avg_counts'][p] = round(float(np.mean([d['piece_counts'][p] for d in random_decomps])), 1)

    # KT at FO
    kt_at_fo = kt_decompositions.get('fo', {})

    # ===== 5. Key comparison: which pieces change most start→FO in KT? =====
    start_pct = {p: round(start_decomp[p] / start_decomp['total'] * 100, 1) for p in PIECE_ORDER}
    fo_pct = kt_at_fo.get('pct', {})
    delta_pct = {}
    for p in PIECE_ORDER:
        if p in fo_pct and p in start_pct:
            delta_pct[p] = round(fo_pct[p] - start_pct[p], 1)

    result = {
        'test': 'E-spatial',
        'test_name': 'Per-piece Field Decomposition at FO',
        'start_position': {
            'total_E': round(start_decomp['total'], 1),
            'pieces': {p: round(start_decomp[p], 1) for p in PIECE_ORDER},
            'pct': start_pct,
            'piece_counts': start_counts,
        },
        'kasparov_topalov': {
            'fo_ply': kt_fo_ply,
            'fo_san': kt_fos[0].san if kt_fos else None,
            'n_plies': kt_n_plies,
            'decompositions': kt_decompositions,
            'delta_pct_start_to_fo': delta_pct,
        },
        'random_games': {
            'n_analyzed': len(random_decomps),
            'avg_pct_at_fo': avg_random if avg_random else None,
            'individual': random_decomps[:5],  # save first 5 for detail
        },
        'interpretation': None,
    }

    # Interpretation
    # Find which piece has highest removal energy % at FO
    if fo_pct:
        dominant = max(fo_pct, key=fo_pct.get)
        dominant_pct = fo_pct[dominant]
        # Which piece shifted most?
        if delta_pct:
            most_increased = max(delta_pct, key=delta_pct.get)
            most_decreased = min(delta_pct, key=delta_pct.get)

            interp = (
                f"At FO (ply {kt_fo_ply}), field energy is dominated by "
                f"{dominant} ({dominant_pct}% of removal energy). "
                f"From start to FO, {most_increased} contribution increased by "
                f"{delta_pct[most_increased]:+.1f}pp while {most_decreased} "
                f"decreased by {delta_pct[most_decreased]:+.1f}pp. "
            )

            if avg_random:
                # Compare GM FO vs random FO profiles
                gm_king_pct = fo_pct.get('King', 0)
                rnd_king_pct = avg_random.get('King', 0)
                interp += (
                    f"Random games at FO (avg ply {avg_random['avg_fo_ply']:.0f}): "
                    f"King contribution = {rnd_king_pct:.1f}% vs GM FO King = {gm_king_pct:.1f}%. "
                )

                # Count difference at FO
                gm_counts = kt_at_fo.get('piece_counts', {})
                rnd_counts = avg_random.get('avg_counts', {})
                pieces_lost_gm = sum(start_counts[p] - gm_counts.get(p, 0) for p in PIECE_ORDER if p != 'King')
                pieces_lost_rnd = sum(start_counts[p] - rnd_counts.get(p, 0) for p in PIECE_ORDER if p != 'King')
                interp += (
                    f"At FO, GM game has lost {pieces_lost_gm} pieces vs "
                    f"random games {pieces_lost_rnd:.1f} pieces — "
                )
                if pieces_lost_gm <= 2:
                    interp += (
                        "GM FO occurs with near-full material, confirming it's an "
                        "opening development signal, not a material-change signal."
                    )
                else:
                    interp += "material reduction may contribute to FO signal."

            result['interpretation'] = interp
        else:
            result['interpretation'] = f"Dominant piece at FO: {dominant} ({dominant_pct}%)"
    else:
        result['interpretation'] = "Could not compute decomposition."

    log(f"Interpretation: {result['interpretation']}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"Cached to {CACHE_FILE}")
    log("DONE")

    print_summary(result)


def print_summary(result):
    print("\n" + "="*60)
    print("TEST E-spatial: Per-piece Field Decomposition at FO")
    print("="*60)

    s = result['start_position']
    print(f"\nStarting position: E_total = {s['total_E']}")
    print(f"  {'Piece':8s} {'Removal E':>10s} {'% of total':>10s}")
    for p in PIECE_ORDER:
        print(f"  {p:8s} {s['pieces'][p]:10.1f} {s['pct'][p]:9.1f}%")

    kt = result['kasparov_topalov']
    fo = kt['decompositions'].get('fo', {})
    if fo:
        print(f"\nKasparov-Topalov at FO (ply {kt['fo_ply']}, {kt['fo_san']}):")
        print(f"  E_total = {fo['total_E']}")
        print(f"  {'Piece':8s} {'Removal E':>10s} {'% total':>8s} {'Delta pp':>8s}")
        for p in PIECE_ORDER:
            d = kt['delta_pct_start_to_fo'].get(p, 0)
            print(f"  {p:8s} {fo['pieces'][p]:10.1f} {fo['pct'][p]:7.1f}% {d:+7.1f}")

    rnd = result['random_games']
    if rnd['avg_pct_at_fo']:
        avg = rnd['avg_pct_at_fo']
        print(f"\nRandom games at FO (n={avg['n']}, avg ply {avg['avg_fo_ply']:.0f}):")
        print(f"  avg E_total = {avg['avg_total_E']}")
        print(f"  {'Piece':8s} {'% total':>8s}")
        for p in PIECE_ORDER:
            print(f"  {p:8s} {avg[p]:7.1f}%")

    print(f"\nInterpretation: {result['interpretation']}")
    print("="*60)


if __name__ == '__main__':
    main()
