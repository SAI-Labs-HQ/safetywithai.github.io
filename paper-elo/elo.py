"""Elo-scale ratings from the pairwise judgments.

Ratings are a Bradley-Terry fit (the order-independent form of Elo used by
LLM arenas) reported on the Elo scale: 1000 is average and a 400-point gap
means 10:1 odds of winning. Intervals are a bootstrap over paper matchups.

    .venv/bin/python elo.py
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RESULTS = Path(__file__).parent / "results"
SCALE, BASE = 400 / np.log(10), 1000

CATEGORY = {"neurico-claude": "NeuriCo · Claude", "neurico-codex": "NeuriCo · GPT",
            "zero-shot-claude": "Claude Code", "zero-shot-codex": "Codex"}


def category(label: str) -> str:
    return next(v for k, v in CATEGORY.items() if label.startswith(k))


def fit(games: list[tuple[str, str, float]], players: list[str], prior: float) -> dict[str, float]:
    """Bradley-Terry by MM. `games` are (a, b, score of a); a tie is 0.5.

    `prior` adds that many wins and losses for every player against a fixed
    average opponent, which keeps ratings finite when someone wins every game.
    """
    if not players:
        return {}
    idx = {p: i for i, p in enumerate(players)}
    n = len(players)
    wins = np.full(n, prior)
    played = np.zeros((n, n))
    for a, b, s in games:
        i, j = idx[a], idx[b]
        wins[i] += s
        wins[j] += 1 - s
        played[i, j] += 1
        played[j, i] += 1
    p = np.ones(n)
    for _ in range(2000):
        denom = (played / (p[:, None] + p[None, :])).sum(1) + 2 * prior / (p + 1)
        new = wins / denom
        if np.abs(np.log(new) - np.log(p)).max() < 1e-9:
            p = new
            break
        p = new
    return {pl: BASE + SCALE * np.log(p[idx[pl]]) for pl in players}


def rate(matchups: dict, key, prior: float, n_boot: int, rng) -> list[dict]:
    """Rate `key(label)` groups. `matchups` maps a paper pair to its games."""
    def games_of(ms):
        out = []
        for m in ms:
            for a, b, s in matchups[m]:
                ka, kb = key(a), key(b)
                if ka != kb:
                    out.append((ka, kb, s))
        return out

    all_games = games_of(matchups)
    players = sorted({g[0] for g in all_games} | {g[1] for g in all_games})
    if not players:
        return []
    point = fit(all_games, players, prior)

    ms = list(matchups)
    boots = defaultdict(list)
    for _ in range(n_boot):
        sample = [ms[i] for i in rng.integers(len(ms), size=len(ms))]
        g = games_of(sample)
        present = {x[0] for x in g} | {x[1] for x in g}
        for pl, r in fit(g, [p for p in players if p in present], prior).items():
            boots[pl].append(r)

    rows = []
    for pl in players:
        w = sum(s if a == pl else 1 - s for a, b, s in all_games if pl in (a, b))
        n = sum(pl in (a, b) for a, b, _ in all_games)
        lo, hi = np.percentile(boots[pl], [2.5, 97.5])
        rows.append({"name": pl, "elo": round(point[pl]), "lo": round(lo), "hi": round(hi),
                     "games": n, "win_rate": round(w / n, 3)})
    return sorted(rows, key=lambda r: -r["elo"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", type=float, default=0.5)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--no-forfeits", action="store_true",
                    help="leave out runs that finished without a paper instead of counting them as losses")
    ap.add_argument("--forfeit", nargs="*", default=[], metavar="IDEA:LABEL",
                    help="treat these runs as finished without a paper, whatever the manifest says")
    ap.add_argument("--main-only", action="store_true", help="use the main-body-only judgments (_main files)")
    ap.add_argument("--exclude", nargs="*", default=[], metavar="SUBSTR",
                    help="drop methods whose label contains any of these (e.g. fable)")
    ap.add_argument("--out", default=None, help="output name (default ratings[_main].json)")
    args = ap.parse_args()
    suffix = "_main" if args.main_only else ""
    excluded = lambda label: any(s in label for s in args.exclude)

    papers = [p for p in json.loads((RESULTS / f"papers{suffix}.json").read_text()) if not excluded(p["label"])]
    for p in papers:
        if f"{p['idea']}:{p['label']}" in args.forfeit:
            p["outcome"] = "no_paper"
    current = {(p["idea"], p["label"]): p.get("sha") for p in papers if p["outcome"] == "paper"}
    judgments = [json.loads(l) for l in (RESULTS / f"judgments{suffix}.jsonl").read_text().splitlines()]
    judgments = [j for j in judgments if not excluded(j["first"]) and not excluded(j["second"])]
    # Keep only judgments of the current version of each paper.
    judgments = [j for j in judgments
                 if current.get((j["idea"], j["first"])) == j["sha_first"]
                 and current.get((j["idea"], j["second"])) == j["sha_second"]]

    # One matchup = one pair of papers on one idea; it holds every judge x order game.
    matchups: dict[tuple, list] = defaultdict(list)
    for j in judgments:
        a, b = sorted((j["first"], j["second"]))
        s = 0.5 if j["winner"] == "tie" else float(j["winner"] == a)
        matchups[(j["idea"], a, b)].append((a, b, s))

    # A run that ended without a paper loses to every paper on the same idea,
    # with as many games as a judged matchup has.
    forfeits = 0
    forfeited = sorted({(p["idea"], p["label"]) for p in papers if p["outcome"] == "no_paper"}) if not args.no_forfeits else []
    if not args.no_forfeits:
        per = max((len(v) for v in matchups.values()), default=0)
        for p in papers:
            if p["outcome"] != "no_paper":
                continue
            for (idea, label) in current:
                if idea == p["idea"]:
                    a, b = sorted((label, p["label"]))
                    matchups[(idea, a, b)] = [(a, b, float(a == label))] * per
                    forfeits += 1

    rng = np.random.default_rng(0)
    methods = rate(matchups, lambda l: l, args.prior, args.boot, rng)
    categories = rate(matchups, category, args.prior, args.boot, rng)
    for m in methods:
        m["category"] = category(m["name"])

    # Judge diagnostics.
    by_pair = defaultdict(dict)
    for j in judgments:
        by_pair[(j["idea"], j["judge"], *sorted((j["first"], j["second"])))][j["first"]] = j["winner"]
    both = [v for v in by_pair.values() if len(v) == 2]
    consistent = sum(len(set(v.values())) == 1 for v in both)
    first_wins = sum(j["winner"] == j["first"] for j in judgments if j["winner"] != "tie")
    decided = sum(j["winner"] != "tie" for j in judgments)

    out = {
        "methods": methods,
        "categories": categories,
        "meta": {
            "ideas": sorted({j["idea"] for j in judgments}),
            "papers": len(current),
            "judgments": len(judgments),
            "judges": sorted({j["judge"] for j in judgments}),
            "paper_matchups": len(matchups),
            "forfeit_matchups": forfeits,
            "no_paper_runs": [{"idea": i, "label": l} for i, l in forfeited],
            "order_consistent": f"{consistent}/{len(both)}",
            "first_position_win_rate": round(first_wins / decided, 3) if decided else None,
            "cost_usd": round(sum(j.get("cost") or 0 for j in judgments), 2),
            "excluded": args.exclude,
        },
    }
    (RESULTS / (args.out or f"ratings{suffix}.json")).write_text(json.dumps(out, indent=1))

    for title, rows in (("Methods", methods), ("Categories", categories)):
        print(f"\n{title}")
        for r in rows:
            print(f"  {r['name']:36s} {r['elo']:5d}  [{r['lo']}, {r['hi']}]  "
                  f"win rate {r['win_rate']:.0%} over {r['games']} games")
    print("\n" + json.dumps(out["meta"], indent=1))


if __name__ == "__main__":
    main()
