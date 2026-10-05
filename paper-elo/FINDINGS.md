# Paper arena: findings so far

Last updated 2026-10-05. Numbers come from `results/ratings.json` (all 8
methods), `results/ratings_nofable.json` (6 methods, Fable 5.1 excluded),
`results/lengths.json` and `results/judgments.jsonl`.

## Setup

- **Papers.** 8 methods × 5 research ideas, 39 finished papers at the time of
  writing (`sounds_like_ai` / Claude Code · Fable 5.1 still running). Methods:
  NeuriCo pipeline and a single zero-shot session, each with Claude Code
  (Opus 5.5, Fable 5.1) and Codex (GPT-5.6-sol, GPT-6-Astra) backbones.
- **Judge.** Every pair of papers on the same idea is compared in both
  presentation orders by three models from families that wrote none of the
  papers: Gemini 3.1 Pro, Grok 4.7, DeepSeek V4 Pro (via OpenRouter,
  temperature 0, JSON output). The judge sees the research idea and text
  extracted from the two PDFs with the author block removed and "NeuriCo"
  redacted, plus word counts. It scores six criteria (addresses the idea,
  rigor, evidence, insight, clarity, length) and picks a winner. Length is a
  criterion in both directions: too thin to report methods and results counts
  against a paper, and so does padding.
- **Ratings.** Bradley-Terry fit reported on the Elo scale (1000 = average,
  400 points = 10:1 odds), one game per judge × order, ties as half a win, a
  0.5-game prior against an average opponent to keep ratings finite. 95%
  intervals from a bootstrap over paper matchups (2000 resamples). Category
  ratings refit the same games with each method relabelled as its category;
  games within a category are dropped.
- **Cost.** 798 judgments, $38.97 in total. Per call: Gemini $0.08, Grok
  $0.067, DeepSeek $0.006. Key: `OPENROUTER_API_DEV_KEY` (shared with the
  review backend dev deployment, so the OpenRouter dashboard shows other
  models too; the judge only calls the three above).

## Ratings (all 8 methods, 133 paper pairs, 798 judgments)

| Method | Elo | 95% interval | Win rate |
| --- | --- | --- | --- |
| Claude Code · Fable 5.1 | 1450 | 1375–1573 | 87% |
| NeuriCo · Opus 5.5 | 1329 | 1253–1442 | 79% |
| Claude Code · Opus 5.5 | 1289 | 1193–1392 | 75% |
| NeuriCo · Fable 5.1 | 1266 | 1185–1367 | 73% |
| Codex · GPT-6-Astra | 754 | 643–826 | 35% |
| NeuriCo · GPT-5.6-sol | 679 | 541–770 | 29% |
| NeuriCo · GPT-6-Astra | 619 | 474–708 | 24% |
| Codex · GPT-5.6-sol | 318 | 69–462 | 5% |

| Category | Elo | 95% interval | Win rate |
| --- | --- | --- | --- |
| Claude Code | 1327 | 1265–1409 | 85% |
| NeuriCo · Claude | 1268 | 1222–1327 | 80% |
| NeuriCo · GPT | 644 | 498–729 | 22% |
| Codex | 570 | 408–669 | 14% |

- The backbone family dominates: the four Claude-backed methods (1266–1450)
  and the four GPT-backed methods (318–754) do not overlap.
- NeuriCo vs zero-shot on the same backbone, head to head: NeuriCo wins 100%
  with GPT-5.6-sol, 50% with Opus 5.5, 27% with GPT-6-Astra, 23% with
  Fable 5.1. The pipeline helps the weakest backbone a lot and the strongest
  ones not at all.
- The ordering holds across ideas: Claude Code · Fable 5.1 wins 80–93% on
  every idea; Codex · GPT-5.6-sol wins 0–14% on every idea.

## Ratings without Fable 5.1 (6 methods, 75 pairs, 450 judgments)

| Method | Elo | 95% interval | Win rate |
| --- | --- | --- | --- |
| NeuriCo · Opus 5.5 | 1484 | 1376–1716 | 89% |
| Claude Code · Opus 5.5 | 1446 | 1308–1679 | 87% |
| Codex · GPT-6-Astra | 958 | 891–1021 | 46% |
| NeuriCo · GPT-5.6-sol | 881 | 798–950 | 38% |
| NeuriCo · GPT-6-Astra | 826 | 733–897 | 33% |
| Codex · GPT-5.6-sol | 524 | 318–645 | 7% |

| Category | Elo | 95% interval | Win rate |
| --- | --- | --- | --- |
| NeuriCo · Claude | 1323 | 1246–1502 | 89% |
| Claude Code | 1285 | 1177–1430 | 87% |
| NeuriCo · GPT | 720 | 572–793 | 32% |
| Codex | 645 | 484–737 | 21% |

## Paper lengths

| Method | Pages | Main words | Words after references | Tables |
| --- | --- | --- | --- | --- |
| Claude Code · Fable 5.1 | 18.5 (14–21) | 7,400 | 3,000 | 13 |
| NeuriCo · Fable 5.1 | 14.2 (13–16) | 6,300 | 1,300 | 8 |
| Claude Code · Opus 5.5 | 14.6 (12–17) | 6,200 | 2,000 | 8 |
| NeuriCo · Opus 5.5 | 14.6 (13–17) | 6,200 | 1,500 | 7 |
| Codex · GPT-6-Astra | 9.4 (8–12) | 4,300 | 1,400 | 7 |
| NeuriCo · GPT-6-Astra | 13.8 (11–16) | 4,200 | 2,200 | 7 |
| NeuriCo · GPT-5.6-sol | 10.4 (9–12) | 4,200 | 700 | 4 |
| Codex · GPT-5.6-sol | 4.2 (3–5) | 2,200 | 400 | 1 |

Median over all 39 papers: 13 pages, 5,100 main-text words (range 3–21 pages,
1,400–7,900 words). Length tracks rating closely (Spearman 0.88 between mean
main words and Elo) and splits by backbone family the same way the ratings do.

## Judge checks

There is no human ground truth yet. Consistency checks only:

- Same winner in both presentation orders: 324 of 399 pairs×judges (81%).
  The first-shown paper wins 58% of decided comparisons.
- On idea 1, re-judging on the main body only (references and appendices
  removed, word counts matching what the judge reads) changed 5 of 90
  verdicts, all among the bottom four papers. The appendix is not what
  decides the top of the table.
- Criterion scores carry little independent information: the winner had the
  higher total score in 90 of 90 idea-1 comparisons. Rigor and insight
  separate winner and loser most (~2 points), clarity and length least.
- A longer paper won 81 of 90 idea-1 comparisons, but longer papers also
  contain more experiments, and the judges' written reasons are about the
  experiments (models, controls, sample sizes), not the page count.

## Why NeuriCo · Fable 5.1 loses to Claude Code · Fable 5.1

Same backbone, yet zero-shot wins ~77% of their games. Two investigations,
one from the judges' reasoning and papers, one from the run logs.

**From the judgments and papers (24 judgments, 4 ideas).**

- Two clean sweeps (`lies_vs_hallucinations`, `keeping_secrets`, 6/6 each)
  plus two near coin-flips. All five NeuriCo wins came when NeuriCo was shown
  first, so position bias decided the contested ideas.
- Judges cite experimental breadth: more models, conditions or scenarios
  (15/24 analyses), larger samples (8), an extra control cell (9), a causal
  intervention that worked in zero-shot and failed in NeuriCo (6/6 on
  `secrets`). Writing was essentially never the deciding factor; length was
  explicitly excused as substantive in 5 analyses.
- Verified in the papers. `lies`: NeuriCo tested one model, 3,000 questions,
  one incentive prompt (6 tables); zero-shot two models, 6,000 questions, five
  pressure scenarios, two extra control cells (17 tables). `secrets`: NeuriCo
  used 120 stories per condition and the writer model as its own guesser, and
  its own limitations say the projection ablation "did not work without
  destroying fluency"; zero-shot used 360 stories, two independent guessers,
  a working ablation with controls.
- NeuriCo papers were the statistically tighter ones (Holm correction,
  bootstrap CIs, 32 vs 3 random steering directions) in 10 of 24 analyses,
  but that only won it `isolating_knowledge_updates`. These judges weigh
  "more evidence" above "cleaner statistics".

**From the runs.**

| Idea | NeuriCo | Zero-shot | Scale difference |
| --- | --- | --- | --- |
| human_vs_llm_prompter | 7.7 h (5 h, SIGTERM, 2.4 h resume) | 8.0 h | 5 vs 6 models |
| isolating_knowledge_updates | 7.9 h | 13.0 h | 11 vs 17 methods, 7 vs 10 targets; four planned methods "not run" |
| keeping_secrets | 9.4 h | 13.8 h | 120 vs 360 stories/condition; no second guesser |
| lies_vs_hallucinations | 3.3 h | 16.8 h | 1 vs 2 models, 1 vs 10 prompts, 3,000 vs 6,000 questions |

1. The paper is written by a separate agent in 4–6 minutes from `REPORT.md`
   (`templates/agents/paper_writer.txt`: claims must come from the experiment
   report). The writers never opened `results/`. The zero-shot session writes
   the paper in-session with raw results in context, over 2–10 hours.
2. The pipeline budgets time (`session_instructions.txt`: Implementation
   60–90 min, Experimentation 60–90 min, Analysis 30–45 min; "experiments were
   run (even if simple or preliminary)"; `state_contract.txt` caps research
   directions). The zero-shot prompt says "There is no time limit: doing the
   research properly and finishing the paper matters more than speed."
   Execution ran 3–9 h vs 8–17 h.
3. Experiments were cut accordingly, exactly on the two ideas the judges swept.
4. Rigid template: a NeurIPS preamble that fails to compile (every writer
   patched it), mandated house style, citations only from the literature
   review.
5. Operational trouble: the idea-1 run was killed after 5 h when the batch
   queue was reordered and resumed 17 h later with its first transcript
   overwritten; API credits ran out mid-run on two ideas (zero-shot hit this
   once too).
6. Context load: ~80 KB instruction prompt plus 45 KB resource handoff vs a
   10 KB zero-shot prompt; the experimenter never reads the papers itself.

The same mechanism explains why the pipeline helps GPT-5.6-sol (it forces a
complete study out of a model that otherwise writes 4-page papers) and does
not help the strong backbones.

**If a fair pipeline-vs-session comparison is wanted:** give both arms the
same "no time limit" instruction, and give the paper writer the `results/`
directory and a longer budget. Fixing the queue reordering is separate.

## Open issues

- No human calibration. A blind human ranking of a handful of pairs would
  tell us whether "breadth over statistics" is the right preference.
- Position bias (58% first-shown wins) is handled by judging both orders but
  still decides close pairs.
- Papers are judged as write-ups; nothing checks the reported numbers against
  the code in `results/`.
- `sounds_like_ai` is missing the Claude Code · Fable 5.1 paper.

## Rerunning

```bash
cd paper-elo
.venv/bin/python judge.py            # judges new pairs only (cached by PDF hash)
.venv/bin/python elo.py              # results/ratings.json
.venv/bin/python elo.py --exclude fable --out ratings_nofable.json
.venv/bin/python plot.py             # results/elo.png, elo-category.png
.venv/bin/python plot.py --ratings ratings_nofable.json --name elo-nofable
.venv/bin/python judge.py --main-only && .venv/bin/python elo.py --main-only   # appendix-free variant
```
