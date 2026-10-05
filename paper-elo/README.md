# Paper Elo

Blind pairwise LLM judging of the papers described in
`/data/haokun_test/neurico/docs/PAPER_COMPARISON.md`, turned into Elo ratings.

```bash
.venv/bin/python judge.py   # judge new pairs (cached in results/judgments.jsonl)
.venv/bin/python elo.py     # results/ratings.json
.venv/bin/python plot.py    # results/elo.html and results/elo.png
```

Rerun all three as more papers finish; only new pairs are judged.

- **Judge**: papers on the same idea are compared in both orders by three
  models from families that wrote none of the papers. The judge sees the idea
  and extracted paper text with the author block removed. It scores six
  criteria (addresses the idea, rigor, evidence, insight, clarity, length) and
  picks a winner.
- **Ratings**: Bradley-Terry fit on the Elo scale (1000 = average, 400 points
  = 10:1 odds), with 95% bootstrap intervals over paper matchups. Category
  ratings refit the same games with each method relabelled as its category;
  games within a category are dropped.
- **Missing papers**: a `no_paper` run loses to every paper on its idea
  (`elo.py --no-forfeits` leaves it out instead).
- Uses `OPENROUTER_API_DEV_KEY` from `../.env`.
