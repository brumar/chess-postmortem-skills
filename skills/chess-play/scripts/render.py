#!/usr/bin/env python
"""Render the final position of a PGN game to a PNG image.

Usage:
    .venv-chess/bin/python render.py games/<game>.pgn [--flip] [--size N] [-o out.png]

By default the image is written to boards/<game>.png next to this script.
The side-to-move, FEN and SAN move list are printed so the position can be
cross-checked against the image.
"""

import argparse
import io
import sys
from pathlib import Path

import cairosvg
import chess
import chess.pgn
import chess.svg

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pgn", type=Path, help="PGN file of the game")
    parser.add_argument("--flip", action="store_true", help="orient board from Black's side")
    parser.add_argument("--size", type=int, default=520, help="image width/height in pixels")
    parser.add_argument("-o", "--out", type=Path, default=None, help="output PNG path")
    args = parser.parse_args()

    game = chess.pgn.read_game(io.StringIO(args.pgn.read_text()))
    if game is None:
        print(f"error: no game found in {args.pgn}", file=sys.stderr)
        return 1
    errors = game.errors
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    board = game.board()
    san_moves = []
    last_move = None
    for move in game.mainline_moves():
        san_moves.append(board.san(move))
        board.push(move)
        last_move = move

    svg = chess.svg.board(
        board,
        orientation=chess.BLACK if args.flip else chess.WHITE,
        lastmove=last_move,
        check=board.king(board.turn) if board.is_check() else None,
        size=args.size,
        coordinates=True,
    )

    out = args.out or (HERE / "boards" / (args.pgn.stem + ".png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out))

    numbered = []
    for i, san in enumerate(san_moves):
        if i % 2 == 0:
            numbered.append(f"{i // 2 + 1}. {san}")
        else:
            numbered.append(san)
    print("moves:", " ".join(numbered) if numbered else "(none)")
    print("fen:  ", board.fen())
    print("turn: ", "White" if board.turn == chess.WHITE else "Black")
    if board.is_game_over():
        print("game over:", board.result(), "-", board.outcome().termination.name)
    print("wrote:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
