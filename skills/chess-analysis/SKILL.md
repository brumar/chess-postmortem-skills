---
name: chess-analysis
description: Engine post-mortem of a chess game producing a deeply annotated PGN. Runs a Stockfish eval sweep, then interrogates the engine with "naive questions" (via parallel investigator subagents) until every mistake and every complex engine move is genuinely explained, and writes layered annotations (short notes on ordinary moves, deep dives on 0.3+ pawn errors). Use whenever the user asks to analyze/review/annotate a game, find their mistakes, run a post-mortem or "stage 2", asks "where did I go wrong", or after a game played with the chess-play skill ends. Also for analyzing any PGN file the user provides. If the user recorded themselves thinking aloud during the game (a voice memo / mp3 alongside the game), this skill also covers transcribing it locally, clock-aligning it to the moves, and weaving the player's actual beliefs into the annotations.
---

# Chess post-mortem: sweep, interrogate, annotate

Goal: an annotated PGN a human learns from. An eval number is not an
explanation — the deliverable is the *why*, verified against the engine
and against your own eyes (render positions, look at them).

## Pipeline overview

0. **Audience** — whose game this is and what level to write for.
1. **Setup** — engine + venv.
2. **Sweep** — eval every move, flag mistakes (≥0.3 pawn loss).
3. **Investigate** — one subagent per mistake, in parallel, running the
   naive-question method (see below).
3b. **Plan pause** — exactly one quiet position per game, both sides'
   plans derived from the engine.
4. **Brief comments** — a subagent pass giving short notes to the
   ordinary moves.
5. **Build** — merge everything into `annotations.json`, run
   `build_annotated.py`, validate.
6. **Verify** — a subagent re-checks the artifact against the checklist.
7. **Viewer** — bundle the annotated PGN + sweep + engine-line sidecars
   into a standalone HTML analysis board (`build_viewer.py`).
8. **Deliver** — send the PGN and the HTML viewer, summarize findings in
   chat, commit if in a real repo session.

## 0. Who the review is for — settle this before writing anything

Every comment in this pipeline is pitched at a reader. Pick the level
first and record it, or the annotations drift into proving things the
player can already see.

- **The user's own games**: use the level the user gave you (ask once if
  you don't know it, and remember the answer: a CLAUDE.md line or a memory
  note such as "my lichess handle is X, write for 1800"). That number wins
  over the PGN's Elo header. Ratings in the header are often misleading:
  a correspondence or daily rating over a dozen games can sit 300-400
  points below the player's real strength.
- **Anybody else's game**: read `WhiteElo`/`BlackElo` for the side being
  reviewed and calibrate to that. If the tag is missing, or the rating is
  provisional (RD > 150, or a handful of games), ask the user instead of
  assuming a low number.

Write the result into `annotations.json` as a top-level
`"audience": {"level": 1800, "source": "user-set"}` so the
brief-comment pass, the plan pause, the verifier and stage 3's narration
all inherit one number instead of each guessing its own. What that number
changes, concretely, is in `references/style.md` ("Calibrate to the
player's level") — read it before writing comments, and give it to every
subagent that writes prose.

## 1. Setup

- Python venv with `python-chess` + `cairosvg` (repo convention:
  `.venv-chess` at repo root; create if missing).
- Stockfish: `export STOCKFISH=$(scripts/get_stockfish.sh)` — reuses
  `$STOCKFISH`/PATH if available, else downloads the official binary.

## 1b. Think-aloud recording (optional input, highly recommended)

If the player recorded themselves thinking aloud during the game, the transcript upgrades every later stage: investigators
refute the player's ACTUAL beliefs instead of guessed ones, and annotations
can quote them verbatim. Ask for the audio when the user mentions thinking aloud, a voice
recording, or an mp3 next to a game.

- **Transcribe locally** with whisper.cpp (`whisper-cli` with a medium
  model such as `ggml-medium-q5_0.bin`, `-l auto`; ask the user where
  their binary and model live, or install them from
  https://github.com/ggml-org/whisper.cpp).
  Convert to 16 kHz mono wav first (`ffmpeg -ar 16000 -ac 1`). GOTCHA: whisper
  falls into repetition loops after long quiet stretches — if the tail of the
  transcript is one line repeated, re-cut the audio from just before the loop
  (`ffmpeg -ss <sec> -c copy`) and transcribe that piece separately; the fresh
  context breaks the loop.
- **Align to the moves with the PGN clocks.** With `%clk` comments and
  time control base+inc: `used(side, k) = base + inc*k − clk_after_move_k`;
  wall-clock elapsed at any move = white_used + black_used. Audio time ≈
  elapsed − offset, where offset (recording started before the game) is
  calibrated on 2-3 anchor moves the player names aloud. Accuracy is within
  seconds; build a per-ply table first.
- **Save the cleaned transcript** as `chess-games/games/NNN-transcript-<lang>.md`
  (dedupe consecutive whisper duplicates, keep `[mm:ss]` stamps, note the
  alignment rule in the header). Commit it with the game.
- **Feed investigators the quotes** for their plies (the briefing's
  "refute the specific human belief" step becomes literal), and answer any
  question the player asked on tape ("on verra ça à l'analyse") explicitly
  in the relevant annotation.
- **A note belongs to its ply, and to the moves it names.** Each entry in
  the notes or transcript file is stamped with the ply it was written at,
  and covers that ply plus any move its own text explicitly names (a note
  at move 13 writing out "c3, then Qh5, then e5" covers those three
  moves). It covers nothing else. Never carry an entry to a decision it
  does not mention: a correspondence player writing at move 43 was looking
  at the move-43 position. If no entry covers the move you are annotating,
  write nothing about what the player was thinking. "You had already ruled
  it out" with no note behind it is fabrication, and the player will know.
  (A past review shipped exactly this: a ply-85 note, *"the king can't
  help much because of the series of checks"*, was used as the reason for
  the ply-83 king move and then refuted. Wrong position, and a refutation
  of a claim the player never made.)
- The recording also feeds stage 3: the video narration can contrast what
  the player believed with what the engine proved, move by move.

## 2. Sweep

```sh
STOCKFISH=... .venv-chess/bin/python scripts/sweep.py <game>.pgn --depth 22
```

Produces `<game>-sweep.json` with per-ply evals, best move, second-best,
FENs, and centipawn loss; prints the mistake list (default threshold 30cp
= 0.3 pawns). Depth 22 is the default quality bar; drop to 14–16 only for
quick previews and say so in the PGN's Annotator tag.

## 3. Investigate mistakes — parallel subagents, naive posture

Spawn **one investigator subagent per flagged mistake** (batch in
parallel; ~4–6 at a time is a good ceiling). Each gets:

- the sweep row (FENs, played move, best move, evals),
- paths to `scripts/query.py`, `scripts/render_fen.py`, the venv python,
  and `$STOCKFISH`,
- its OWN sidecar path `analysis-ply<NN>.json` — every `query.py` call
  must carry `--log <that file>` so the engine lines it discovers are kept
  for the HTML viewer (one file per investigator: concurrent appends to a
  shared file would race; `build_viewer.py` merges them),
- the briefing file `references/investigator.md` — tell it to read that
  file first and follow it.

The briefing enforces the method that matters (developed over the first reviews
and sharpened by user feedback):

- **Naive questions at the top level**: "why not the move actually
  played?" — restrict-search it, get the refutation, understand it.
- **Naive posture INSIDE branches and sub-branches too**: for every
  non-obvious move within the engine's line (including the opponent's
  replies), ask "why not the natural alternative?", probe it, and write
  that move's own short why-comment. A variation in the final PGN where a
  complex move stands uncommented is a defect.
- **Vision**: render the 1–2 positions where the explanation lives and
  actually look at them before writing prose.
- Output: a JSON fragment in the `annotations.json` move schema (see
  `scripts/build_annotated.py` docstring), with per-move comments inside
  the variation lines.

Sanity-check each returned fragment: replay its SAN lines (build script
will also catch illegal moves), and spot-check one eval claim per
investigator with a quick `query.py` call. Subagents hallucinate;
verification is part of the job.

If the Agent tool is unavailable in your context, run the investigator
briefing yourself for each mistake, sequentially — same method, same
output schema; do not skip the per-move probing inside variations to save
time.

## 3b. The plan pause — exactly one per game

Investigators explain moves. Nothing in the pipeline so far explains the
stretch where no single move is bad enough to flag and the player simply
had no plan — which is where the rating points actually go. So every game
gets **exactly one** plan pause: one quiet position, both sides' plans,
derived from the engine, written up as a normal annotation. One, not zero
(the review is poorer without it) and not three (it stops being *the*
moment of the game, and the probes are not cheap).

Pick the position from the sweep, not by feel:

```sh
.venv-chess/bin/python scripts/pick_pause.py <game>-sweep.json --side white
```

Pass the reviewed player's side (`--side both` for a third-party game). It
filters for quiet positions (no check, neither the engine nor the player
wants a capture, the eval already settled) and ranks them on five criteria,
each printed on its own line so you can see what won:

| | criterion | what it measures |
|-|-----------|------------------|
| positional | `phase` | middlegame: kings committed, minors off their home squares, material still substantial. An endgame tapers it to zero. |
| positional | `settled` | the pawn skeleton has stopped churning: no tension pending, pawns fixed head to head, the skeleton holding for several plies. |
| outcome | `drift` | centipawns the side bled from here up to its next crash. |
| outcome | `strays` | the fraction of the moves in that run that left the engine's line AND cost something. |
| outcome | `crash` | the blunder that ends the run, at low weight: it is the bill, not the reason. |

The positional pair says a plan is the question this position asks; the
outcome trio says the player failed to answer it. `strays` is the one that
distinguishes a missing plan from a tactical oversight: four consecutive
small departures from the engine's line score 1.0, while one bad move among
four fine ones scores 0.33 and drops down the list, which is right, because
that move already has an investigator on it.

Every weight is a flag (`--w-settled 2` to insist on a fixed structure,
`--w-drift 2` to rank on the bleed above all) if a game needs re-balancing.
When no drift run clears `--min-drift` the script ranks every quiet position
and says so, leaving the positional criteria to decide, so a cleanly played
game still gets a pause.

Read the top 2-3 and choose with your eyes on the board: the script ranks,
you decide. Prefer one where the think-aloud transcript (§1b) catches the
player asking a planning question out loud, so the annotation answers a
question that was actually asked.

Then run **one** subagent on it, given `references/plan-pause.md` as its
briefing (tell it to read that first), the pause FEN, the drift rows from
the sweep, any transcript quotes for those plies, and its own sidecar
`analysis-plan-pause.json`. It returns an annotation fragment for the pause
ply; merge it into `annotations.json` like any other, and verify it the same
way — replay its SAN lines, spot-check one eval claim.

The one number that must survive into the chat summary is the briefing's
honesty gate: how far apart the candidate plans actually are. When five
plans sit within a quarter of a pawn, "you played the wrong move" is false
and "you had no plan" is true, and only the second is worth the player's
time.

## 4. Brief comments on ordinary moves

Users appreciate light annotation everywhere, not only at the wrecks.
Spawn one subagent (or two: opening/middlegame) with the sweep JSON, the
audience level from §0, `references/style.md`, and the game to propose
**one-line comments** for moves worth a note: opening
names and theory landmarks, the plan behind a regroup, a near-miss
(0.15–0.3 loss), the point where the game's character changed. Not every
move needs one — a good density is a comment every 2–4 plies. Merge into
the same `annotations.json` (comment only, no glyph, no variation).

## 5. Build

Fill the rest of the spec: `audience` (§0), `annotator` (engine + depth), `game_comment`
(3–6 sentence human summary of the game's story), `final_comment`
(result/state). Then:

```sh
.venv-chess/bin/python scripts/build_annotated.py annotations.json
```

It writes `<game>-annotated.pgn` and fails loudly on illegal SAN or
unparseable output.

## 6. Verify — one more subagent

Give a verifier subagent the annotated PGN + sweep JSON + the audience
level + the notes/transcript file + the checklist in
`references/style.md`. It must confirm: parse-clean; every ≥0.3 mistake
annotated with glyph + why + at least one variation; every capture,
sacrifice, or quiet-move-in-a-tactic inside variations carries its own
comment; eval claims match the sweep within rounding; layered density
present; **nothing explained below the audience level, and every claim
about what the player thought traceable to a note at that same ply**. Fix
what it flags; rerun until clean.

## 7. Build the HTML viewer

```sh
python3 scripts/build_viewer.py <game>-annotated.pgn \
    --sweep <game>-sweep.json --analysis analysis-*.json \
    --name "<White> vs <Black>"
```

Emits `<game>-viewer.html`: a standalone lichess-style analysis board
(board + move list with all annotations, eval bar/graph, keyboard nav) —
no network, no dependencies, opens from file://. The engine panel shows
the **cached Stockfish lines** from the sweep and the investigators'
sidecars wherever the reader has no engine; if the file sits next to an
`engine/` folder holding `stockfish-17.1-lite-single.{js,wasm}` (from the
`stockfish` npm package) and is served over HTTP, a live local engine is
available too.
Sanity-check the artifact: open it (or load it headless) and confirm the
move list renders and no console errors.

## 8. Deliver

Send the annotated PGN **and the HTML viewer** to the user, with a chat
summary that leads with the 2–4 biggest swings, the plan pause (both
plans in one sentence each, with the spread from the honesty gate), and the
transferable lessons (name the blind spots, not just the moves). Evals quoted from
White's POV. Commit+push when working in a real repo session (never during
skill tests).
