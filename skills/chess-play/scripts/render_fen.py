#!/usr/bin/env python
"""Render a FEN (after optional SAN moves) to PNG, with optional arrows.

usage: render_fen.py "<fen>" out.png [--moves "san ..."] [--arrows "e2e4,g1f3"] [--flip]
"""
import argparse
import cairosvg, chess, chess.svg

p = argparse.ArgumentParser()
p.add_argument("fen")
p.add_argument("out")
p.add_argument("--moves", default="")
p.add_argument("--arrows", default="")
p.add_argument("--flip", action="store_true")
a = p.parse_args()

board = chess.Board(a.fen)
last = None
for san in a.moves.split():
    last = board.push_san(san) or board.move_stack[-1]
arrows = []
for spec in filter(None, a.arrows.split(",")):
    arrows.append(chess.svg.Arrow(chess.parse_square(spec[:2]), chess.parse_square(spec[2:4]),
                                  color="#15781B99" if len(spec) < 5 or spec[4] != 'r' else "#88202099"))
svg = chess.svg.board(board, orientation=chess.BLACK if a.flip else chess.WHITE,
                      lastmove=board.move_stack[-1] if board.move_stack else None,
                      arrows=arrows, size=520, coordinates=True)
cairosvg.svg2png(bytestring=svg.encode(), write_to=a.out)
print(board.fen())
print("wrote", a.out)
