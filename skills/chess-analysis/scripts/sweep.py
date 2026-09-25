#!/usr/bin/env python
"""Eval every position of a PGN game with Stockfish; report per-move deltas.

usage: sweep.py game.pgn [--depth 22] [--out sweep.json] [--threshold 30]
Engine binary: $STOCKFISH, else `stockfish` on PATH.
"""
import argparse, json, os
import chess, chess.pgn, chess.engine

p = argparse.ArgumentParser()
p.add_argument("pgn")
p.add_argument("--depth", type=int, default=22)
p.add_argument("--out", default=None)
p.add_argument("--threshold", type=int, default=30, help="centipawn loss to flag")
a = p.parse_args()

SF = os.environ.get("STOCKFISH", "stockfish")
LIMIT = chess.engine.Limit(depth=a.depth)
out_path = a.out or os.path.splitext(a.pgn)[0] + "-sweep.json"

game = chess.pgn.read_game(open(a.pgn))
board = game.board()
engine = chess.engine.SimpleEngine.popen_uci(SF)
engine.configure({"Threads": max(1, (os.cpu_count() or 2) - 1), "Hash": 512})

rows = []
for i, mv in enumerate(game.mainline_moves()):
    mover = "White" if board.turn == chess.WHITE else "Black"
    san = board.san(mv)
    best = engine.analyse(board, LIMIT, multipv=2)
    best_mv = best[0]["pv"][0]
    best_san = board.san(best_mv)
    best_cp = best[0]["score"].white().score(mate_score=10000)
    alt_san = board.san(best[1]["pv"][0]) if len(best) > 1 else None
    alt_cp = best[1]["score"].white().score(mate_score=10000) if len(best) > 1 else None
    fen_before = board.fen()
    board.push(mv)
    after_cp = engine.analyse(board, LIMIT)["score"].white().score(mate_score=10000)
    label = f"{i // 2 + 1}." if mover == "White" else f"{i // 2 + 1}..."
    delta = after_cp - best_cp
    rows.append({
        "ply": i + 1, "label": label, "san": san, "mover": mover,
        "fen_before": fen_before, "fen_after": board.fen(),
        "eval_best": best_cp, "best_san": best_san,
        "alt_san": alt_san, "alt_cp": alt_cp,
        "eval_after_played": after_cp,
        "loss_for_mover": -(delta if mover == "White" else -delta),
    })
    print(f"{label}{san:8s} ({mover:5s}) best={best_san:8s} evalbest={best_cp:6d} "
          f"after={after_cp:6d} loss={rows[-1]['loss_for_mover']:6d}")

engine.quit()
json.dump(rows, open(out_path, "w"), indent=1)
print(f"\nwrote {out_path}\nMistakes (loss >= {a.threshold}cp):")
for r in rows:
    if r["loss_for_mover"] >= a.threshold:
        print(f"  {r['label']}{r['san']} ({r['mover']}) lost {r['loss_for_mover']}cp; better: {r['best_san']}")
