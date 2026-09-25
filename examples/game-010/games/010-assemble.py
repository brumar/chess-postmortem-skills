#!/usr/bin/env python
"""Merge the investigator fragments into annotations.json for game 010."""
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

GAME_COMMENT = (
    "A 15+10 rapid Najdorf with 6.Bg5 in which White asked the right planning question "
    "out loud at move 8 (Bc4 or Be2, short or long castling, f4 now or later) and picked "
    "the slow answer. Two moves later 9.Qd2 allowed the 9...Nxe4 trick; White saw it "
    "coming, and while waiting for it counted 10.Bxe7 Nxd2 11.Bxd8 as a mass trade, one move "
    "short of seeing both pieces hang with only one of them savable. 10.Nxe4 left him a "
    "pawn down at -1.4, but 12...Nc6 traded off the only piece blocking the d-file and "
    "13.Nxc6 bxc6 14.Nxd6+ took the pawn back with interest. After 17.Bf3 gave Black a "
    "chance (17...Ke7!) that 17...Rd8 missed, White reached a rook ending a pawn up with a "
    "3-v-1 queenside majority and converted it cleanly: two passed pawns against a black "
    "king that went raiding on the wrong wing."
)

FINAL_COMMENT = (
    "After 40.Re7 the rook sits behind the e-pawn and b8=Q is next: "
    "White queens and wins the rook for the e-pawn in any order."
)

spec = {
    "source_pgn": "010-le_brumar-vs-Chess_player1245.pgn",
    "output_pgn": "010-le_brumar-vs-Chess_player1245-annotated.pgn",
    "annotator": "Claude + Stockfish 17.1 (sweep depth 22; flagged moves re-checked at depth 24-28)",
    "audience": {"level": 1800, "source": "user-set for le_brumar (chess-analysis skill, stage 0)"},
    "game_comment": GAME_COMMENT,
    "final_comment": FINAL_COMMENT,
    "moves": {},
}

# local fixes on top of the fragments
OVERRIDES = {
    "15": "PLANPAUSE",
    "35": {"comment": ("He worked this out at the board: 'fou prend c6 échec, il reprend avec le "
                       "fou, je reprends avec la tour', and it wins a clean pawn (+3.8).")},
    "55": {"comment": ("The plan stated at move 27, carried out. 28.c5 was marginally better "
                       "(+5.5 vs +5.3 at depth 26): with a3 already in, b4 can back it next move "
                       "and the king has time to reach c3.")},
    "61": {"comment": ("'J'aurais pu faire c5 tout à l'heure, je suis idiot' (I could have played c5 "
                       "earlier): not idiotic. 28.c5 was 0.2 better than b4, a move-order detail, and "
                       "a move before a3 it would have thrown the win away. Now c5 is the engine's "
                       "choice too.")},
}

PLAN_COMMENT = (
    "The plan pause. White to move, +0.4, nothing hanging, and he asked the right questions out loud: "
    "'Bc4, ou tranquillement e2 et petit roque? ... laisser les deux routes ouvertes ... f4 plus tard' "
    "(Bc4 or Be2, short or long castling, f4 later). At one common depth (26): 8.f4 +0.4, 8.Qe2 0.0, "
    "8.a3 0.0, 8.Qf3 0.0, 8.Be2 -0.1, 8.Bc4 -0.4. Be2 beat Bc4, so his feeling that c4 hits granite was right. "
    "But Qe2, a3, Qf3 and Be2 sit within 0.1 of each other and f4 stands half a pawn clear: the position has one "
    "plan, and it starts with the pawn move he postponed ('later' costs: after 8.Be2 Be7, 9.f4 is -0.2). "
    "White's plan: f4 now, the h4 bishop home to f2 where it guards d4 against ...Qb6, queen to f3 to hold e4, "
    "castle long. Black's plan: ...Be7, ...b5, ...Bb7, then ...b4 to chase the c3 knight, the only defender of e4, "
    "and ...g5 to chase the h4 bishop. Both plans are about the same two things, the e4 pawn and the loose h4 bishop. "
    "That is why the 9...Nxe4 trick could happen at all: in the engine plan, ...Nxe4 after 8.f4 Be7 9.Qf3 simply "
    "loses a piece (+4.3), and after Bf2 there is no bishop on h4 to collect. The crash itself was a missed "
    "tactic, but it landed exactly on the fault line both plans are about."
)

moves = spec["moves"]
for f in ["010-frag-brief.json"] + sorted(set(glob.glob("010-frag-*.json")) - {"010-frag-brief.json"}):
    data = json.load(open(f))
    for fr in (data if isinstance(data, list) else [data]):
        k = str(fr.pop("ply"))
        for extra in [x for x in fr if x not in ("glyph", "comment", "variations")]:
            fr.pop(extra)
        moves[k] = fr            # deep fragments are merged after the brief one, so they win
pp = moves.pop("14")
pp["variations"] = [v for v in pp["variations"] if v["line"][0]["san"] != "Be2"]
pp["glyph"] = "?!"
pp["comment"] = PLAN_COMMENT
OVERRIDES["15"] = pp
for k, v in OVERRIDES.items():
    if k in moves and "variations" in moves[k] and "variations" not in v:
        moves[k].update(v)
    else:
        moves[k] = v


# ---- verifier round 1 fixes ----
def rep(k, old, new):
    c = moves[str(k)]["comment"]
    assert old in c, (k, old)
    moves[str(k)]["comment"] = c.replace(old, new)
def setc(k, text):
    moves[str(k)]["comment"] = text
def step(k, vi, si, text, san=None):
    st = moves[str(k)]["variations"][vi]["line"][si]
    assert san is None or st["san"] == san, (k, vi, si, st["san"])
    st["comment"] = text
def varc(k, vi, text):
    moves[str(k)]["variations"][vi]["comment"] = text

rep(11, "the ...b5-b4 idea you mention is real", "the ...b5-b4 idea he mentions is real")
rep(12, "The engine rates it +1.0 against +0.4 for 6...e6.", "The engine rates it +1.0 against +0.4 for 6...e6 (depth 24).")
step(12, 2, 2, "forced", "gxf6")
rep(13, "and Black must spend ...h5 to stop Qh5, so ...h6 was a lost tempo.", "and Black must spend ...h5 to stop Qh5.")
step(13, 0, 1, "...exf6 is worse (+1.7), see the previous note", "gxf6")
setc(17, "Heading for O-O-O. Right after playing it: \"D2 c'est pas bon... cavalier prend E4, forcément\" "
         "(Qd2 was bad, the knight takes e4). It was not a pawn blunder: 9...Nxe4 fails tactically (see 10.Bxe7). "
         "The real cost is about 0.2 (-0.4 against -0.2 for 9.f4 or 9.a4).")
setc(18, "The trick: the knight leaves f6 with tempo on Qd2 and Nc3 and opens the e7-h4 diagonal, so after "
         "10.Nxe4 Bxh4 Black has won the e4 pawn. The flaw is that the unmasked e7 bishop is loose too (see 10.Bxe7). "
         "-0.3 with a normal move becomes +4.0 with correct play.")
rep(19, "and the h4 bishop hits f2, which will cost White g3 and a tempo.", "and the h4 bishop eyes f2.")
setc(20, "The point of the trick: the pawn is won and Black has the bishop pair.")
step(24, 1, 1, "fails: the d-file is still shut", "Nxd6")
varc(24, 1, "-4.8")
setc(25, "The right order: trade on c6 first. 13.Nxd6+ at once fails because the d4 knight still blocks the d-file, so after ...Bxd6 nothing can recapture.")
step(32, 0, 5, "now it works", "Bxc6")
varc(32, 0, "+2.7: White still wins c6, but the order is Rhd1 first, then Bf3.")
step(33, 1, 3, "forced", "Kf6")
setc(34, "17...Rd8 ignores c6: 18.Bxc6+ wins it. 17...Ke7! (+0.7) was the move: it hits d6 and heads for ...Rad8 "
         "and a full rook trade. After 19.Rxc6 White is a pawn up with a 3-v-1 queenside majority (a, b and c against "
         "Black's a-pawn), and the c6 rook hits a6 and e6 while the h8 rook and e8 king are still undeveloped: +3.6.")
step(34, 0, 1, "forced: the rook has no better square", "Rhd1")
step(34, 0, 3, "all four rooks come off", "Rxd8")
setc(41, "Doubling on the a6 pawn: 'je devrais pouvoir manger le pion sans angoisse' (I should be able to take "
         "the pawn without worry). Rd4 and Rdd6 are practically equal (+4.0 and +3.9 at depth 22).")
setc(42, "The pawn steps out of the double attack.")
setc(47, "He debated collecting a5 with the king against pushing c4 at once. The engine sees no difference "
         "(Kb2 and c4 both +5.1 in the sweep), and its main line after Kb2 plays c4 two moves later anyway.")
setc(49, "Trading rooks is best. Of the follow-ups he named, at depth 22: 26.c4 +4.2, 26.Rd7 +3.8, 26.Rd4 +3.1. Rd4 is the one to avoid.")
setc(51, "'On y va maintenant sur c4 pour mettre la pression' (let's go c4 now to put on pressure): the engine's "
         "first choice (+4.2 at depth 22, 26.a3 a little weaker at +3.9). His worry that 26.Rd4 lets ...e5 gain time was right: +3.1.")
rep(53, "The engine slightly prefers 27.Kc3 (+5.1) to a3 (+4.8)", "The engine slightly prefers 27.Kc3 to a3 (+5.1 against +4.8 at depth 24)")
rep(59, "On d2 the rook still guards the second rank, so after ...Ke4-f3 the king finds f2 and h2 defended. On d1 it guards nothing on that rank",
        "On d2 the rook still guards f2, so ...Ke4-f3 finds nothing to take. On d1 it does not")
step(59, 0, 0, "guards f2 from the side", "Rd2")
setc(63, "Tempo count: c7 is next, and Black has no pawn anywhere near queening.")
moves["68"].pop("glyph", None)
setc(68, "Black loses the race by one tempo: the b-pawn reaches b7 and the c8 rook cannot cover both b8 and c7. "
         "The sweep's huge 'loss' here is a mate-score artifact: Black is lost after any move, and 34...Ra8, behind "
         "the b-pawn, only keeps the rook alive a few moves longer.")
step(68, 0, 4, "the only check", "Rb4+")
varc(68, 0, "Queen against rook and pawns, winning for White.")
setc(73, "Black has to give the rook for the c-pawn.")
setc(79, "The rook stops the e-pawn from behind and b8=Q follows.")
spec["final_comment"] = "Black resigned. White queens next move and wins the rook for the e-pawn in any order."

_pp = json.dumps(moves["15"]["variations"], ensure_ascii=False)
for a, b in [("+1.12", "+1.1"), ("+0.4 to +0.55", "+0.4 to +0.6"), ("+0.55", "+0.6"), (" for you", "")]:
    _pp = _pp.replace(a, b)
moves["15"]["variations"] = json.loads(_pp)

json.dump(spec, open("010-annotations.json", "w"), indent=1, ensure_ascii=False)
deep = sorted(int(k) for k, v in moves.items() if "variations" in v)
print(f"{len(moves)} annotated plies, {len(deep)} with variations: {deep}")
