---
name: chess-position
description: Deep study of ONE chess position (a FEN, a screenshot, a diagram, or "move N of game X"), not a whole game. First asks the user whether they want a POSITIONAL analysis (structure, plans for both sides, where each piece belongs) or a TACTICAL one (forcing lines, what works and what fails), then investigates with Stockfish as a fact-checker and explains the position in human terms. Optionally ends with a narrated video of the position via the chess-video skill. Use when the user shares a single position and asks "what is the plan here", "analyze this position", "what should White do", "explain this position", "is there a tactic", or sends a board image with no game attached.
---

# Single position: ask, investigate, explain

Goal: the user understands the position after reading you. The engine is
a fact-checker, not the author. A list of Stockfish lines is not an
answer; an explanation that a strong human would give, with every claim in
it verified, is.

Tools come from the sibling skills: `chess-analysis/scripts/query.py`
(eval, multipv, `--restrict`, `--moves`), `chess-analysis/scripts/render_fen.py`,
`chess-analysis/scripts/get_stockfish.sh`, and for the video
`chess-video/scripts/make_video.py`. Same venv convention (`.venv-chess`).

## 0. Ask first. Always.

Before any engine call, ask the user which analysis they want, with
AskUserQuestion (skip only if their message already says it in so many
words):

- **Positional**: no forcing line decides the position. The question is
  what each side is trying to do: pawn structure, good and bad pieces,
  weak squares, pawn breaks, where every piece belongs, the plan for both
  sides.
- **Tactical**: there may be a combination, a trap, or a forcing
  sequence. The question is what works, what fails, and why.

Do not guess from the position. A quiet-looking position can hide a
tactic the user wants found, and a sharp one can be a question about
plans. The two modes produce different deliverables, and the user loses
time reading the wrong one.

In the same question round, settle what is missing:

- **Side to move. Never infer it.** A screenshot or diagram never says
  whose turn it is, so for an image input always ask, even when the answer
  looks obvious (board orientation, last-move highlight, "it's my
  position"). Only a FEN's side-to-move field or the user's own words
  settle it. A wrong guess changes every line and every plan in the
  answer.
- **Level** to write for, unless already known (CLAUDE.md, memory, or the
  chess-analysis skill's `audience.level`). Calibrate with
  `chess-analysis/references/style.md`.
- **Video at the end?** (optional, see §4).

## 1. Get the position right

- From an image: transcribe the FEN rank by rank, then **render it with
  `render_fen.py` and compare the render to the image square by square**.
  Count material both ways. A single misplaced pawn invalidates the whole
  analysis.
- Castling rights: infer from king and rook squares; when both are
  castled, use `-`.
- Record the FEN and the assumptions (side to move, castling) and state
  them in the final answer.

## 2. Investigate

- Positional: follow `references/positional.md`. This is the demanding
  mode. You must reach an understanding you can state as rules, and then
  prove each rule with the engine.
- Tactical: follow `references/tactical.md`.

Parallel probes: run 3-5 `query.py` calls at once in one shell command
(`( ... ) & ( ... ) & wait`). For a large probe budget, subagents with the
chess-analysis `investigator.md` posture work too, but one position is
usually small enough to do yourself, and doing it yourself is how you
actually understand it.

## 3. Deliver in chat

Lead with the answer, not the method. Positional shape:

1. **What the position is about**: structure name (if any) and the one or
   two facts everything else follows from.
2. **Constraints**: what each side cannot do yet, and why (one clause of
   proof each, with the number).
3. **Plan for each side** as 3-5 rules, each with its reason. Rules, not
   move lists: "h3 first, because it opens h2 as a retreat for the bishop",
   not "1.h3 g6 2.Rac1".
4. **What not to do**, with the cost in pawns.
5. **Verdict**: the square(s) or piece(s) both plans are about, the eval,
   and the honesty-gate spread ("five moves within 0.1: the plan matters,
   the move does not").

Tactical shape: the key line first, then the refutation of each
tempting alternative, then the idea in one sentence the user can reuse.

State your assumptions (side to move) at the top. If you corrected
yourself during the work, say so plainly. The user needs to know which
parts are solid.

## 4. Optional video

Uses the chess-video skill. `make_video.py` accepts a PGN with a `[FEN]`
tag and no moves, so every shot is `"ply": 0` and every line is a `var`.
If the side to move cannot start the line you want to show (e.g. a Black
idea with White to move), prefix it with the side to move's best quiet
move (the engine's first choice), not a random pass, and say so in the
narration or pick a move that belongs to the plan anyway (`h3` here).

Storyboard for one position (~3-4 min, piper ~160 words/min):

1. The frozen position: structure, the key imbalance, the honesty-gate
   number. `hold` 2.
2. The constraints: each "cannot yet" shown as a short `var`.
3. One segment per side's plan: route arrows first, then a 4-6 ply `var`.
4. Double-edged pieces or squares, if the position has one.
5. What not to do.
6. Verdict: the rules, spoken, both sides.

Then verify as the chess-video skill says: extract frames, check
captions are not clipped (keep them under ~18 characters, e.g. `...g6!`,
not a sentence), check arrows do not pile up on one square, and read the
`.srt` end to end as prose. **Re-read every factual sentence against the
board**: a narration line like "no black pawn can attack c5" is exactly
the kind of claim that sounds right and is false (...b6 does).

Worked example of the whole skill: `examples/position-carlsbad/`.
