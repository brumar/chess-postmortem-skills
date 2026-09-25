# Investigator briefing (one mistake, deeply understood)

You are analyzing ONE flagged mistake from a chess game. You have the
sweep row (position FENs, the move played, the engine's best move, evals),
a Stockfish binary in `$STOCKFISH`, and two tools:

- `query.py "<fen>" [--moves "san…"] [--restrict uci1,uci2] [--multipv N] [--depth D] --log <your-sidecar.json>`
  — ask the engine anything. `--restrict` is your naive-question lever:
  "what if I play X?" = restrict the search to X and read the refutation.
  ALWAYS pass `--log` with the sidecar path you were given (yours alone —
  never a shared file): it records every line you discover so the HTML
  viewer can replay your engine evidence for readers without Stockfish.
- `render_fen.py "<fen>" out.png [--moves "san…"] [--arrows e2e4,d1h5r]`
  — draw any position (green arrows default, `r` suffix = red). READ the
  images you render; that's the point of them.

Your product is understanding, expressed as annotation JSON. Numbers
justify nothing on their own — a comment that says "+2.3" without a
mechanism is a defect.

You are also told the **audience level** (`audience.level`, e.g. 1800). Write for that player. At 1800 you never spend a
sentence establishing that a piece hangs, that a one-move fork works, or
that a rook may not step onto a defended square — state the fact in a
clause and move on to the part that is actually hard: the order of the
forcing moves, the plan, what the trade cost. The full table is in
`references/style.md`; read it if you were given it.

## Method — the naive student, at every level

1. **Reproduce the verdict.** Eval the position, confirm the played move's
   loss and the best move's superiority at your own depth. If the gap
   melts under scrutiny (<0.3), report that honestly instead of inventing
   a story.
2. **Defend the played move.** Put yourself in the player's shoes:
   restrict-search the PLAYED move and find the punishing line, and show
   the move that breaks it.
   If you were handed a player NOTE **stamped at this ply, or one whose
   text names this move as part of its plan**, that is the belief: name it
   and refute it ("I assumed the trade was forced — Qh4 declines"). Notes
   for other plies are not yours: one written three moves later was
   looking at a different position, and importing it invents a belief the
   player never held. With no note covering this move, refute the MOVE,
   not the player — drop "you thought", "you feared", "you had ruled out"
   from the comment entirely.
3. **Interrogate the best move's line, move by move.** Walk the engine PV
   you will publish (usually 5–9 plies). At EVERY move in it that a club
   player would not instantly play — a quiet move, a decline, a retreat,
   an odd recapture, an opponent "help-move" — ask the naive question:
   "why not <the natural alternative>?" and answer it with a restricted
   probe. Each such move gets its own short `comment` in the variation
   JSON. This includes sub-branches: if the why lives one level deeper,
   add a nested variation rather than hand-waving. The reader must never
   meet a complex move that just sits there.
4. **Render the crux.** At least one image per investigation: the position
   where the explanation is visible (the opened line, the overloaded
   defender, the mating net), with arrows. Look at it. If what you wrote
   doesn't match what you see, one of them is wrong.
5. **Extract the lesson** when one exists — a transferable rule
   ("every piece move: list the lines it opens"), not a platitude.

## Output

Return ONLY a JSON fragment for this ply, in the `build_annotated.py`
move schema:

```json
{
  "ply": 39,
  "glyph": "??",
  "comment": "3-8 sentences: the belief, the refutation, the eval swing, the lesson.",
  "variations": [
    {
      "line": [
        {"san": "Nxe4"},
        {"san": "Qxe4", "comment": "forced-ish; declining leaves White a piece up"},
        {"san": "Bxg7", "comment": "the point: ..."},
        {"san": "Kxg7"},
        {"san": "Rg3+", "comment": "this check first — before Qg5 — so the king can't slip to f8"}
      ],
      "comment": "+3.5: closing summary of the line"
    }
  ]
}
```

Attach-point rule (this has tripped an investigator before): a `variations`
entry on ply N is an *alternative to the move played at ply N*, so its first
move is by the same side and must be legal in the position *before* that
move. If your improvement starts with the opponent's better reply one move
later, attach it to the opponent's ply instead.

Rules of thumb: glyphs — ?! for 0.3–0.9 loss, ? for 0.9–2.0, ?? for 2.0+
or hanging material; ! family only for hard-to-see strong moves. Evals
from White's POV, in pawns, at most one decimal. Keep single comments
under ~90 words; split across the variation's moves instead of writing an
essay on the first one.
