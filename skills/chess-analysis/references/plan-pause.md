# Plan-pause briefing (one quiet position, both plans)

You are analyzing ONE quiet position from a chess game — the game's single
**plan pause**. Nothing is hanging, no check exists, no capture is called
for. A mistake investigator has nothing to say here, because no single move
is bad enough to flag. The question the position asks is *what is the plan?*,
and your job is to answer it for BOTH sides, from the engine, in positional
language.

The position was not picked by feel. `pick_pause.py` scored it on two
positional criteria (the middlegame has arrived, the pawn skeleton has
stopped churning) and three outcome criteria (how much the player then bled,
how CONSISTENTLY they left the engine's line during that run, and the
blunder that ended it). You should have that breakdown with the FEN. Use it:
the `settled` line tells you which pawns are fixed and therefore what the
plans have to work around, and the `strays` line tells you whether the run
is a genuine planless stretch or one bad move wearing a costume.

You have the pause FEN, the sweep rows around it, `$STOCKFISH`, `query.py`
and `render_fen.py`, and a sidecar path. Every probe carries
`--log <your-sidecar>`. Budget ~12-18 probes; run 3-4 at a time in
parallel, each writing its OWN log file, then merge them (concurrent
appends to one file race and lose lines).

Engines output moves, not plans. You get plans by triangulating.

## Method

1. **Portrait.** `--multipv 5 --depth 28` on the pause position. Then read
   the five lines for what they DO, not what they start with: where each
   piece ends up, which pawn breaks appear, which trades the engine seeks
   and which it avoids, where the rooks belong.

2. **The honesty gate — run it before you write a word.** Re-query the
   candidate first moves with `--restrict uci1,uci2,... --multipv N` at ONE
   common depth (30 is a good bar). If the spread is under ~0.3, the move
   does not matter and **saying so is the finding**: the position has one
   plan and several move orders into it. Never call a move "the mistake"
   on a gap that small — in game 004 the played move was 0.24 behind the
   best and was completely fine; the error came two moves later.

3. **Invariants.** List, for each of the top lines, where the pieces go.
   Keep what is true in all of them and name it as a rule a human can hold:
   "knight to c3, never a3", "the pawn stays on d4", "rooks to e1/d1". Four
   or five rules is a plan; a move list is not. Rules that hold across every
   line are the ones to publish.

4. **Intent reversal — this is how you get the OTHER side's plan.** Give
   the side to move a pass-like move (`h3`, `Kh1`, a shuffle) and read the
   opponent's best reply at depth: that is their plan, unopposed. Play it
   out 8-12 plies with `--moves` and re-query the endpoint. The concrete
   goal shows up there — a pawn recovered, a square occupied, a piece
   entombed. The two plans usually negate each other; when they do, say
   which square or piece they are both about.

5. **Naive square questions.** Wherever a plan hinges on where one piece
   belongs, restrict-search the alternatives from the same position and
   compare. These produce the sharpest single numbers you will publish:
   in game 004, once Black got in ...a4 the bishop's squares were Bd1
   +4.85, Bd5 +4.44, **Bc2 −0.25** (a knight covered c2) — which is what
   proved the retreat had to come *earlier*, not that it was optional.

6. **Duel with the game.** Eval what was actually played at the same depth,
   move by move through the drift, and attribute each loss to the specific
   rule it broke. Then ask the structural question: does the engine's plan
   make the later blunder *impossible* rather than merely unlikely? (It
   usually does — the plan keeps a pawn on the square the fork needed, or
   moves the queen off the forked file.) That is the strongest thing you
   can tell the player, so check it explicitly.

7. **Render and look.** At least one image per plan, with the route arrows
   you intend to publish. If the arrows do not match the prose, one of them
   is wrong. Two arrows between the same pair of squares collide into an
   unreadable blob — split them across images or shots.

## Output

One plan per side, each with: a name, 3-5 rules in positional language, an
eval, and a **4-6 move demonstration line** you have verified by playing it
out. Plus the drift table.

```json
{
  "ply": 26,
  "comment": "Quiet position, White a piece up. Five plans score within 0.25 here, so the move does not matter and the plan does: knight to c3 not a3, bishop off the a-pawn's path, rooks to e1/d1, and the pawn never leaves d4. Black's plan is the mirror image: ...a5-a4 buries the extra bishop on d1, then both knights come to d4 and win the pawn back. Both plans are about one square.",
  "variations": [
    {"line": [{"san": "Nc3"}, {"san": "Nbc6"}, {"san": "Qg4"}, {"san": "Na5"},
              {"san": "Bc2", "comment": "before ...a4 arrives: afterwards c2 hangs to the b4-knight"}],
     "comment": "+5.0: White's plan. Pawn stays on d4, bishop out of reach, knights nowhere."},
    {"line": [{"san": "h3", "comment": "a pass, to show Black's intention"}, {"san": "a5"},
              {"san": "Nc3"}, {"san": "a4"}, {"san": "Bd1", "comment": "forced: the only decent square left"}],
     "comment": "+4.8: Black's plan. Then ...Ng6 and ...Nc6, and d4 falls."}
  ]
}
```

Attach it to the ply BEFORE the move under consideration (the pause position
is that ply's `fen_after`), so the annotation sits on the last move played
rather than on a move nobody made.

Honesty rules: quote the spread from step 2 every time. If two plans for one
side score within 0.3, say the position has two valid plans and pick the more
human one. If the "drift" turns out to be one bad move and three fine ones,
say that instead: a plan pause that is really a tactical oversight in
disguise should be handed back, not dressed up. The selector's `strays`
fraction is the first check on this, but confirm it on the board, since it
counts departures from the engine's move and not from the engine's idea.
