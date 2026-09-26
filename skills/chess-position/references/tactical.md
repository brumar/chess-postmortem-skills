# Tactical analysis of one position

The user asked what works here. The answer is the forcing line, why it
works, and why the tempting alternatives do not.

## 1. Your own scan first

Before the engine, list what you see: checks, captures, threats (for the
side to move AND for the opponent if it were their turn), loose pieces,
overloaded defenders, pins, back-rank and king-cover weaknesses. This is
the list the user would make at the board; the answer must address it.

## 2. Portrait

`query.py <fen> --multipv 5 --depth 28`. If the top line wins material or
mates, that is the headline. If all five lines are within ~0.3, say there
is no tactic, then offer to switch to positional mode.

## 3. Naive questions on every forcing candidate

For each move from your scan (and each engine top move), restrict-search
it: `--restrict <uci>`. For the ones that fail, find the refutation and
the reason in one clause ("the queen is overloaded", "the knight has no
g5", "the back rank has luft"). Tempting-but-wrong moves the user would
consider deserve as much space as the right one.

## 4. Naive questions inside the line

For every non-obvious move in the winning line, including the defender's
replies, ask "why not the natural alternative?" and restrict-search it.
A line whose key defensive try is not shown is not proved. This is the
chess-analysis `investigator.md` posture; read it for the full method.

## 5. The idea in one sentence

What pattern makes it work, stated so it transfers to other games
("the defender of f5 is also the guard of h7").

## 6. Render and self-check

Render the critical position with arrows. Replay every SAN line you
publish. Every eval quoted comes from a probe you ran.
