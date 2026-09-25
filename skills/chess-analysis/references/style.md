# Annotation style & verifier checklist

## Calibrate to the player's level

The audience level is set in stage 0 and carried in `annotations.json`
(`audience.level`). It is not decoration: it decides which sentences are
worth writing.

For the user's own games the level is the one the user set (stage 0),
regardless of the Elo tag in the PGN. For anyone else, it is the PGN's Elo
for the reviewed side.

Example at 1800 (shift the columns for weaker or stronger players):

| never spend a sentence on | state it, don't prove it | this is what the review is for |
|---|---|---|
| a piece hangs; a one-move fork, pin or skewer; a square is defended so a piece may not sit there; the king must leave check; back-rank and other stock mates | a 3-6 ply forcing sequence whose POINT is the move order; an endgame technique by its name (opposition, cutting, Lucena, Philidor, the short-side defence) rather than from first principles; a known opening idea | the plan and the question the position asks; pawn structure and which squares it concedes; what a trade costs long-term; prophylaxis; why this move order and not that one; the honest size of the difference |

Two rules that follow from the table:

- **State a tactical fact once.** "Both checks drop the rook" is a fact.
  Repeating it as a closing lesson, and again in the summary, turns a fact
  into a lecture.
- **Don't teach what the player demonstrably knows.** If the game shows
  them calculating a five-move line correctly, do not explain a two-move
  one to them thirty plies later.

The failure mode this exists to prevent is real: a past video told an
1800 player that a rook could not check because it would be taken, and
made it the lesson of the endgame.

## Never invent what the player thought

A note covers **its own ply, plus any move its own text explicitly names**
— a note at move 13 that writes out "c3, then Qh5, then e5" covers those
three moves, because that is what it is about. It covers nothing else. It
may never be produced as the reason for a decision it does not mention,
and it may never be refuted at a ply it was not written for.

Quote it, agree with it or refute it there and nowhere else, and never
write "you believed X" when no entry covering that move says X — the
engine can tell you what was wrong with a move, it cannot tell you what
was in the player's head. With no note for the move, the annotation is
about the position, full stop.

## Style (for everyone writing comments)

- **Layered density.** Ordinary moves: nothing, or one line (theory name,
  plan, nuance) — aim for a note every 2–4 plies so the game reads as a
  story. Mistakes ≥0.3: full treatment (glyph, belief-refutation comment,
  variation(s) with per-move comments). Near-misses 0.15–0.3: a one-liner
  is welcome.
- **Explain mechanisms, not scores.** "+2.3" is evidence, not a reason.
  Name the motif: opened line, overload, zwischenzug, declined trade,
  trapped piece, color-complex collapse.
- **Complex moves inside variations always get their own comment** — this
  includes sub-branches. Quiet moves, declines, retreats, only-moves,
  strange recaptures: if a reader would pause on it, there's a comment on
  it. (This rule exists because a user reviewing a previous annotation
  found engine moves standing unexplained inside lines.)
- **Refute the human thought — when there is one on record.** The best
  comments name what the player believed and show the move that breaks the
  belief, but only from a note at that same ply (see above). Without one,
  refute the *move*, not the player.
- Evals from White's POV in pawns, one decimal. English SAN. Lessons
  phrased as transferable rules, sparingly.

## Verifier checklist (subagent: check the artifact, report defects)

1. Annotated PGN parses with zero errors (`python-chess` round-trip).
2. Every sweep-flagged mistake (loss ≥ threshold) has: a glyph, a comment
   giving a mechanism, and ≥1 variation showing the better path.
3. Inside every variation: no capture, sacrifice, check, decline, or
   quiet-move-in-tactics without its own comment. Flag each naked one.
4. Eval numbers quoted in comments match the sweep/query data within
   ±0.2 (or are explicitly marked as deeper re-analysis).
5. Layered density: the stretches between mistakes are not comment
   deserts; at least ~1 note per 3 plies through the opening and at the
   game's turning points.
6. Game comment (header) tells the story in ≤6 sentences; final comment
   states the terminal state/result.
7. No French piece letters inside PGN movetext; comments in English.
8. Nothing is explained below `audience.level`: no sentence proves that a
   piece hangs or that a one-move tactic works. Flag each one with its ply.
9. Every claim about what the player thought, believed, feared or ruled
   out traces to a notes/transcript entry stamped at that same ply. Flag
   any that is imported from another ply or has no source at all.

Report as a list of concrete defects (ply + what's missing), or "clean".
