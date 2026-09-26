# Positional analysis of one position

The user asked what the position is about. The answer is an
understanding, stated as rules, each rule proved. Stockfish gives moves;
plans come from you, and the engine confirms or kills them.

Work in this order. Steps 1-3 happen BEFORE the first engine call: form
your own picture first, so the engine has something to confirm or refute.
If you start with the engine, you end up paraphrasing its lines.

## 1. Read the pawns

- Go file by file. Which pawns is each side missing? Which pawns are
  fixed head to head? Which are passed, isolated, doubled, backward?
- Name the structure if it has a name (Carlsbad, IQP, hanging pawns,
  Stonewall, Maroczy, French chain, Hedgehog...). A name brings its known
  plans with it, which you then test here. Identify it from the missing
  pawns, not from the opening: White without the c-pawn and Black
  without the e-pawn, with the d-pawns blocked and c6/e3 behind them, is
  Carlsbad whatever the move order was.
- Half-open files (a rook's home), weak squares no enemy pawn can reach
  (outposts, holes), the pawn breaks each side has.
- Be careful with "no pawn can attack X". Check every pawn that could
  still advance, including the one-step moves (...b6 attacks c5).

## 2. Read the pieces through the pawns

- Good and bad bishops: a bishop whose own fixed pawns sit on its color
  is bad. The side with the bad bishop usually wants to trade it or get it
  outside the chain. This one fact often drives the whole position.
- For every piece: what does it do now, what does it block, where would
  it be best? Look for pieces that cut both ways (a knight that blockades
  well but blocks its own bishop and freezes a pawn).
- Batteries and long lines (queen + bishop on a diagonal, doubled rooks)
  create constraints: squares the other side cannot use yet, pieces that
  are tied to defence.

## 3. Write down hypotheses

Before the engine: "Black wants to trade the c8 bishop via f5", "White
wants a knight on c5", "the minority attack b4-b5". Three to six of them.
They are what you will test.

## 4. Portrait (engine)

`query.py <fen> --multipv 5 --depth 28`, for the side to move. If side to
move is uncertain, run both. Read the lines for what they DO: where the
pieces end up, which breaks appear, which trades the engine seeks or
avoids.

## 5. Honesty gate

Restrict the top candidates to one common depth. If the spread is under
~0.3 pawn, the move does not matter and the plan does. Say so with the
number. Never call a move "the best" on a 0.05 edge.

## 6. Constraints: what each side cannot do yet

For each natural move a human would want (the trade the structure asks
for, the piece chasing a bishop, the freeing break), restrict-search it.
When it fails, find the reason in one clause: "f5 is attacked twice and
defended once", "the f6 knight is the only guard of h7", "dxc5 hits the
d6 knight". These constraints are the most useful part of the answer,
because they explain the quiet moves that follow (why ...g6 must come
first).

## 7. Prove every prophylactic move's real purpose

Quiet moves in engine lines (h3, Kh1, a3, Rfe1) always have a concrete
reason. Find it by playing the position WITHOUT the move and letting the
opponent use what the move prevented. Example: without h3, ...g6 and
...Nh5 force White to give up the f4 bishop; with h3, the bishop retreats
to h2. "Luft" or "useful waiting move" is not an explanation until you
have checked there is not a sharper reason.

## 8. Intent reversal: the other side's plan

Give the side to move a quiet move that belongs to its own plan and read
the opponent's best reply at depth. That reply, played 6-10 plies, is the
opponent's plan. Re-query the endpoint: where does the eval go if that
plan succeeds? (Black's bishop trade taking the eval from +0.4 to 0.00
was the whole story of the example position.)

## 9. Rules, then proof

Condense each side's plan into 3-5 rules a human can hold at the board,
each with its reason. Verify each rule with a restricted query or a
played-out line, and keep the number. Keep only the rules that hold across
the top engine lines.

## 10. What not to do

Test the tempting mistakes a player at the user's level would consider:
the fake sacrifice the battery suggests, the premature break, the trade
that hands over the bishop pair, the pawn storm that drops a pawn. One
clause and one number each.

## 11. Render and look

Render the position with the arrows you intend to publish
(`render_fen.py --arrows`). If the picture and the prose disagree, one of
them is wrong.

## 12. Self-check before sending

- Every claim of the form "X cannot", "only Y", "no pawn can" checked on
  the board.
- Every number quoted comes from a probe you ran, at a depth you can name.
- The answer explains WHY. If a sentence only says what the engine plays,
  either add the reason or cut it.
