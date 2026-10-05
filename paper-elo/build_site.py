"""Build the public static site (repo root) from the arena results.

    .venv/bin/python build_site.py

Writes index.html, method.html, ideas/<slug>.html, papers/<idea>/<label>.pdf
and assets/. Fable 5.1 runs are left out of this version.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import judge  # noqa: E402
import plot  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent
RESULTS = HERE / "results"
NEURICO = Path("/data/haokun_test/neurico")
FONT_SRC = Path("/data/haokunliu/veritas-workspace/ICML2026-SAI-demo/blog/fonts/inter-400.woff2")

EXCLUDE = ("fable", "astra")
RATINGS = "ratings_site.json"

IDEAS = ["human_vs_llm_prompter", "keeping_secrets", "lies_vs_hallucinations",
         "isolating_knowledge_updates", "sounds_like_ai"]
JUDGE_NAME = {"google/gemini-3.1-pro-preview": "Gemini 3.1 Pro", "x-ai/grok-4.7": "Grok 4.7",
              "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro"}
CRITERIA = {"addresses_idea": "Addresses the idea", "rigor": "Rigor", "evidence": "Evidence",
            "insight": "Insight", "clarity": "Clarity", "length": "Length"}
SITE = "Paper Arena"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def category(label: str) -> str:
    for k, v in {"neurico-claude": "NeuriCo · Claude", "neurico-codex": "NeuriCo · GPT",
                 "zero-shot-claude": "Claude Code", "zero-shot-codex": "Codex"}.items():
        if label.startswith(k):
            return v
    return label


def method_name(label: str) -> str:
    return f"{category(label).split(' · ')[0]} · {plot.method_name(label)}"


CAT_CLASS = {"NeuriCo · Claude": "nc", "NeuriCo · GPT": "ng", "Claude Code": "cc", "Codex": "cx"}


def dot(cat: str) -> str:
    return f'<span class="dot {CAT_CLASS[cat]}"></span>'


def excluded(label: str) -> bool:
    return any(s in label for s in EXCLUDE)


# ---------------------------------------------------------------- page chrome

def page(title: str, body: str, depth: int = 0, extra_head: str = "") -> str:
    rel = "../" * depth
    nav = f"""<header class="top"><div class="inner">
<a class="brand" href="{rel}index.html">SAI Labs <span>· {SITE}</span></a>
<nav><a href="{rel}index.html">Leaderboard</a><a href="{rel}index.html#ideas">Ideas</a><a href="{rel}method.html">How it works</a></nav>
</div></header>"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {SITE}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='4' fill='%23005f5a'/%3E%3C/svg%3E">
<link rel="stylesheet" href="{rel}assets/style.css">{extra_head}
</head><body>
{nav}
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="inner">SAI Labs · {SITE} · ratings update as more papers finish.</div></footer>
</body></html>"""


# ---------------------------------------------------------------- data

def load() -> dict:
    ratings = json.loads((RESULTS / RATINGS).read_text())
    runs = [r for r in judge.load_manifest(False) if r["outcome"] == "paper" and not excluded(r["label"])]
    papers = {}
    for r in runs:
        t = judge.paper_text(r)
        title = t["text"].split("\n", 1)[0].removeprefix("Title:").strip()
        papers[(r["idea"], r["label"])] = {
            "idea": r["idea"], "label": r["label"], "name": method_name(r["label"]),
            "category": category(r["label"]), "title": title, "pages": t["pages"],
            "words": t["words"], "sha": t["sha"], "src": r["paper_pdf"],
            "pdf": f"papers/{r['idea']}/{r['label']}.pdf",
        }
    judgments = []
    for line in (RESULTS / "judgments.jsonl").read_text().splitlines():
        j = json.loads(line)
        a, b = papers.get((j["idea"], j["first"])), papers.get((j["idea"], j["second"]))
        if a and b and a["sha"] == j["sha_first"] and b["sha"] == j["sha_second"]:
            judgments.append(j)
    ideas = {}
    for slug in IDEAS:
        y = yaml.safe_load((NEURICO / f"ideas/arena_candidates/{slug}.yaml").read_text())["idea"]
        ideas[slug] = {"slug": slug, "title": y["title"], "hypothesis": y["hypothesis"].strip(),
                       "background": ((y.get("background") or {}).get("description") or "").strip()}
    return {"ratings": ratings, "papers": papers, "judgments": judgments, "ideas": ideas}


def win_rates(judgments: list[dict], key=lambda j, lab: lab) -> dict:
    """{(idea or None, label): (wins, games)} with ties as half."""
    out = defaultdict(lambda: [0.0, 0])
    for j in judgments:
        for lab in (j["first"], j["second"]):
            out[key(j, lab)][1] += 1
            if j["winner"] == lab:
                out[key(j, lab)][0] += 1
            elif j["winner"] == "tie":
                out[key(j, lab)][0] += 0.5
    return out


def rank_spread(rows: list[dict]) -> list[tuple[int, int]]:
    spreads = []
    for r in rows:
        best = 1 + sum(o["lo"] > r["hi"] for o in rows)
        worst = sum(o["hi"] >= r["lo"] for o in rows)
        spreads.append((best, worst))
    return spreads


# ---------------------------------------------------------------- index

def leaderboard_table(rows: list[dict]) -> str:
    spreads = rank_spread(rows)
    out = ['<table class="board"><thead><tr><th>Rank</th><th>Method</th><th class="num">Rating</th>'
           '<th class="num">95% interval</th><th class="num">Win rate</th><th class="num">Games</th></tr></thead><tbody>']
    for i, (r, (b, w)) in enumerate(zip(rows, spreads), 1):
        spread = f"{b}" if b == w else f"{b}–{w}"
        name = method_name(r["name"]) if "category" in r else r["name"]
        cat = r.get("category", r["name"])
        out.append(f'<tr><td class="rank">{i}<span class="spread">{spread if spread != str(i) else ""}</span></td>'
                   f'<td>{dot(cat)}{esc(name)}</td>'
                   f'<td class="num strong">{r["elo"]}</td><td class="num muted">{str(r["lo"]).replace("-", "−")} to {r["hi"]}</td>'
                   f'<td class="num">{r["win_rate"]:.0%}</td><td class="num muted">{r["games"]}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def matrix(data: dict, order: list[str]) -> str:
    pair = defaultdict(lambda: [0.0, 0])
    for j in data["judgments"]:
        for a, b in ((j["first"], j["second"]), (j["second"], j["first"])):
            pair[(a, b)][1] += 1
            pair[(a, b)][0] += 1 if j["winner"] == a else 0.5 if j["winner"] == "tie" else 0
    out = ['<div class="matrixwrap"><table class="matrix"><thead><tr><th></th>']
    out += [f'<th><span>{esc(plot.method_name(b))}<br><small>{esc(category(b).split(" · ")[0])}</small></span></th>' for b in order]
    out.append("</tr></thead><tbody>")
    for a in order:
        out.append(f'<tr><th>{esc(method_name(a))}</th>')
        for b in order:
            if a == b:
                out.append('<td class="self"></td>')
                continue
            w, n = pair[(a, b)]
            p = w / n if n else None
            if p is None:
                out.append('<td class="na">–</td>')
            else:
                # colour bucket in the stylesheet: w0..w10 = 0%..100% in steps of 10
                out.append(f'<td class="w{round(p * 10)}" title="{w:g} of {n}">{p:.0%}</td>')
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def build_index(data: dict) -> str:
    rt, meta = data["ratings"], data["ratings"]["meta"]
    n_papers = len(data["papers"])
    order = [m["name"] for m in rt["methods"]]
    n_methods = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}.get(len(order), str(len(order)))
    claude_models = sorted({plot.method_name(l) for l in order if "claude" in l})
    gpt_models = sorted({plot.method_name(l) for l in order if "codex" in l})
    join = lambda xs: " and ".join(xs) if len(xs) <= 2 else ", ".join(xs[:-1]) + " and " + xs[-1]
    ideas_html = []
    per_idea = win_rates(data["judgments"], key=lambda j, lab: (j["idea"], lab))
    for n, slug in enumerate(IDEAS, 1):
        idea = data["ideas"][slug]
        labs = [l for (i, l) in data["papers"] if i == slug]
        best = max(labs, key=lambda l: per_idea[(slug, l)][0] / max(per_idea[(slug, l)][1], 1), default=None)
        first = idea["hypothesis"].split("\n\n")[0].replace("\n", " ")
        ideas_html.append(
            f'<a class="idea" href="ideas/{slug}.html"><div class="n">{n}</div><div>'
            f'<h3>{esc(idea["title"])}</h3><p>{esc(first)}</p>'
            f'<div class="meta">{len(labs)} papers · best: {esc(method_name(best)) if best else "–"}</div></div></a>')
    body = f"""
<p class="eyebrow">SAI Labs · research</p>
<h1>Which AI research method writes the better paper?</h1>
<p class="lead">We gave the same five research ideas to {n_methods} automated research methods and let each one run until it produced a paper. Three independent LLM judges then compared every pair of papers on the same idea, blind, and we turned those comparisons into ratings.</p>

<div class="stats">
<div class="stat"><div class="n">{n_papers}</div><div class="l">papers</div></div>
<div class="stat"><div class="n">{meta["paper_matchups"]}</div><div class="l">paper pairs</div></div>
<div class="stat"><div class="n">{meta["judgments"]}</div><div class="l">blind comparisons</div></div>
<div class="stat"><div class="n">{len(meta["judges"])}</div><div class="l">judges</div></div>
</div>

<section class="fig">
{plot.build_bars(rt)}
<p class="note">1000 is the average method. A 400-point gap means 10:1 odds in a head-to-head comparison.</p>
</section>

<section class="fig">
<h2>Leaderboard</h2>
{leaderboard_table(rt["methods"])}
<p class="note">A small number beside the rank is the range of ranks the method could hold given its interval.</p>
</section>

<section class="fig">
<h2>Head to head</h2>
<p class="intro">How often the row method beats the column method, across all ideas and judges.</p>
{matrix(data, order)}
</section>

<section class="fig" id="ideas">
<h2>The five research ideas</h2>
<p class="intro">Each idea page shows the papers side by side with the judges' verdicts.</p>
<div class="ideas">{"".join(ideas_html)}</div>
</section>

<section class="fig">
<h2>The {n_methods} methods</h2>
<ul class="methods">
<li><b>NeuriCo</b> is our multi-stage research pipeline: literature review, planning, experiments and a separate paper-writing step. We ran it on Claude Code with {join(claude_models)} and on Codex with {join(gpt_models)}.</li>
<li><b>Claude Code</b> and <b>Codex</b> rows are a single agent session given the idea and told to research it and write the paper, with no time limit.</li>
</ul>
<p class="note">Every method received the same idea text. Papers were judged as written; nothing checked the reported numbers against the code. <a href="method.html">How the judging and ratings work →</a></p>
</section>
"""
    return page("Leaderboard", body)


# ---------------------------------------------------------------- idea pages

def build_idea(data: dict, slug: str, n: int) -> str:
    idea = data["ideas"][slug]
    papers = sorted([p for (i, _), p in data["papers"].items() if i == slug],
                    key=lambda p: [m["name"] for m in data["ratings"]["methods"]].index(p["label"]))
    js = [j for j in data["judgments"] if j["idea"] == slug]
    wr = win_rates(js)
    rows = []
    for p in papers:
        w, g = wr[p["label"]]
        rows.append(f'<tr><td>{dot(p["category"])}{esc(p["name"])}</td>'
                    f'<td class="title">{esc(p["title"])}</td><td class="num">{p["pages"]}</td>'
                    f'<td class="num">{p["words"]:,}</td><td class="num strong">{(w / g if g else 0):.0%}</td>'
                    f'<td><a href="../{p["pdf"]}" download>PDF</a></td></tr>')
    options = "".join(f'<option value="{esc(p["label"])}">{esc(p["name"])}</option>' for p in papers)
    payload = {
        "papers": [{k: p[k] for k in ("label", "name", "category", "title", "pdf", "pages", "words")} for p in papers],
        "judgments": [{"first": j["first"], "second": j["second"], "judge": JUDGE_NAME.get(j["judge"], j["judge"]),
                       "winner": j["winner"], "analysis": j["verdict"].get("analysis", ""),
                       "scores": j["verdict"].get("scores", {})} for j in js],
        "criteria": CRITERIA,
        "classes": CAT_CLASS,
    }
    bg = idea["background"]
    body = f"""
<p class="eyebrow">Idea {n} of {len(IDEAS)}</p>
<h1>{esc(idea["title"])}</h1>
<div class="hyp">{"".join(f"<p>{esc(par.replace(chr(10), ' '))}</p>" for par in idea["hypothesis"].split(chr(10) + chr(10)))}</div>
{f'<details class="bg"><summary>Background given to every method</summary>{"".join(f"<p>{esc(par.replace(chr(10), chr(32)))}</p>" for par in bg.split(chr(10) + chr(10)))}</details>' if bg else ""}

<section class="fig">
<h2>Papers on this idea</h2>
<table class="board papers"><thead><tr><th>Method</th><th>Paper</th><th class="num">Pages</th><th class="num">Words</th><th class="num">Win rate</th><th></th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="note">Win rate is over this idea only: {len(js)} comparisons by three judges.</p>
</section>

<section class="fig viewer">
<h2>Read two papers side by side</h2>
<div class="pick">
<label>Left <select id="selA">{options}</select></label>
<label>Right <select id="selB">{options}</select></label>
</div>
<div class="pdfs">
<div class="pane"><div class="pane-head"><span id="titleA"></span><a id="dlA" href="#" target="_blank" rel="noopener">open PDF</a></div><div class="pdfbox" id="pdfA"></div></div>
<div class="pane"><div class="pane-head"><span id="titleB"></span><a id="dlB" href="#" target="_blank" rel="noopener">open PDF</a></div><div class="pdfbox" id="pdfB"></div></div>
</div>
<h2 class="sub">What the judges said about this pair</h2>
<div id="tally" class="tally"></div>
<div id="verdicts" class="verdicts"></div>
</section>

<script id="data" type="application/json">{json.dumps(payload).replace("</", "<\\/")}</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script src="../assets/idea.js"></script>
"""
    return page(idea["title"], body, depth=1)


IDEA_JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const byLabel = Object.fromEntries(D.papers.map(p => [p.label, p]));
const selA = document.getElementById('selA'), selB = document.getElementById('selB');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const pdfjs = window.pdfjsLib;
if (pdfjs) pdfjs.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const renders = {};

async function showPdf(box, url) {
  const token = (renders[box.id] = Symbol());
  box.innerHTML = '';
  if (!pdfjs) {  // fallback: the browser's own viewer
    const f = document.createElement('iframe'); f.src = url + '#view=FitH'; f.title = 'paper'; box.appendChild(f); return;
  }
  let doc;
  try { doc = await pdfjs.getDocument(url).promise; }
  catch (e) { box.innerHTML = `<p class="muted pad">Could not render this PDF here. <a href="${url}" target="_blank" rel="noopener">Open it in a new tab.</a></p>`; return; }
  if (renders[box.id] !== token) return;
  const width = box.clientWidth - 2;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  for (let n = 1; n <= doc.numPages; n++) {
    if (renders[box.id] !== token) return;
    const page = await doc.getPage(n);
    const base = page.getViewport({ scale: 1 });
    const scale = width / base.width;
    const vp = page.getViewport({ scale: scale * dpr });
    const c = document.createElement('canvas');
    c.width = vp.width; c.height = vp.height;
    c.style.width = width + 'px'; c.style.height = (vp.height / dpr) + 'px';
    box.appendChild(c);
    await page.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise;
  }
}

function setPane(side, label) {
  const p = byLabel[label];
  const url = '../' + p.pdf;
  document.getElementById('title' + side).textContent = p.name + ' — ' + p.title;
  document.getElementById('dl' + side).href = url;
  showPdf(document.getElementById('pdf' + side), url);
}

function render() {
  const a = selA.value, b = selB.value;
  setPane('A', a); setPane('B', b);
  const tally = document.getElementById('tally'), box = document.getElementById('verdicts');
  if (a === b) { tally.innerHTML = ''; box.innerHTML = '<p class="muted">Pick two different papers to see the judges\' verdicts.</p>'; return; }
  const js = D.judgments.filter(j => (j.first === a && j.second === b) || (j.first === b && j.second === a));
  let wa = 0, wb = 0, t = 0;
  js.forEach(j => { if (j.winner === a) wa++; else if (j.winner === b) wb++; else t++; });
  const pa = byLabel[a], pb = byLabel[b];
  tally.innerHTML = `<div class="t"><span class="dot ${D.classes[pa.category]}"></span><b>${esc(pa.name)}</b> ${wa}</div>` +
    (t ? `<div class="t muted">tie ${t}</div>` : '') +
    `<div class="t"><span class="dot ${D.classes[pb.category]}"></span><b>${esc(pb.name)}</b> ${wb}</div>` +
    `<div class="t muted">of ${js.length} comparisons</div>`;
  const order = ['Gemini 3.1 Pro', 'Grok 4.7', 'DeepSeek V4 Pro'];
  js.sort((x, y) => order.indexOf(x.judge) - order.indexOf(y.judge) || (x.first === a ? -1 : 1));
  box.innerHTML = js.map(j => {
    const left = byLabel[j.first], right = byLabel[j.second];
    const win = j.winner === 'tie' ? 'Tie' : 'Preferred ' + esc(byLabel[j.winner].name);
    const crit = Object.keys(D.criteria);
    const sc = j.scores && j.scores.A ? `<table class="scores"><thead><tr><th></th>${crit.map(c => `<th>${esc(D.criteria[c])}</th>`).join('')}</tr></thead><tbody>` +
      [['A', left], ['B', right]].map(([k, p]) => `<tr><th>${esc(p.name)}</th>${crit.map(c => `<td>${esc(j.scores[k][c] ?? '')}</td>`).join('')}</tr>`).join('') + '</tbody></table>' : '';
    return `<article class="verdict"><div class="vh"><b>${esc(j.judge)}</b><span class="muted">saw ${esc(left.name)} first</span><span class="win">${win}</span></div>` +
      `<p>${esc(j.analysis)}</p>${sc}</article>`;
  }).join('');
}

selA.addEventListener('change', render); selB.addEventListener('change', render);
let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { setPane('A', selA.value); setPane('B', selB.value); }, 300); });
selA.selectedIndex = 0; selB.selectedIndex = Math.min(1, D.papers.length - 1);
render();
"""


# ---------------------------------------------------------------- method page

def build_method(data: dict) -> str:
    meta = data["ratings"]["meta"]
    judges = ", ".join(JUDGE_NAME.get(j, j) for j in meta["judges"])
    body = f"""
<p class="eyebrow">How it works</p>
<h1>Judging and ratings</h1>
<p class="lead">The arena rates methods, not papers. Every paper is compared only with papers on the same idea, and the ratings summarise who tends to win those comparisons.</p>

<h2>The comparison</h2>
<ul>
<li><b>Blind.</b> The judge sees the idea and the text extracted from the two PDFs, under neutral labels. The author line is removed and the method name is redacted. Figures are not shown.</li>
<li><b>Both orders.</b> Each pair is shown twice, with the papers swapped, so a preference for whichever paper comes first cancels out. The first-shown paper still wins {meta["first_position_win_rate"]:.0%} of decided comparisons, and judges pick the same winner in both orders {meta["order_consistent"]} of the time.</li>
<li><b>Three judges.</b> {judges}. None of them belongs to the model families that wrote the papers, so no judge is grading its own writing.</li>
<li><b>Six criteria.</b> Whether the paper answers the idea it was given, rigor of the experiments, whether conclusions follow from the results, insight, clarity, and whether the length fits the content. The judge writes a short comparison, scores each criterion and names a winner.</li>
</ul>

<h2>The rating</h2>
<ul>
<li><b>Each judge's verdict in each order is one game.</b> A tie counts half.</li>
<li><b>Bradley-Terry, shown on the Elo scale.</b> This is the order-independent version of Elo used by LLM arenas. 1000 is the average method; 400 points is 10:1 odds of winning a comparison.</li>
<li><b>Intervals</b> come from resampling paper pairs, so they reflect how much the result depends on which papers happened to be written.</li>
<li><b>Categories</b> refit the same games with each method relabelled as its family; games within a family are dropped.</li>
</ul>

<h2>What this does not measure</h2>
<ul>
<li>Papers are judged as written. No one checked the reported numbers against the code and logs, which are in each run's repository.</li>
<li>There is no human calibration yet. The judges reward breadth of evidence, such as more models, conditions and samples, above tighter statistics; a human panel might weigh these differently.</li>
<li>Longer papers tend to win. In the judges' reasoning this is because longer papers contain more experiments, and removing appendices changed few verdicts, but length and substance are hard to separate with this many papers.</li>
</ul>
"""
    return page("How it works", body)


# ---------------------------------------------------------------- css

CSS = """
@font-face{font-family:"Inter";font-style:normal;font-weight:100 900;font-display:swap;src:url(inter.woff2) format("woff2")}
:root{--bg:#ffffff;--surface:#fafaf8;--ink:#1e1e1e;--ink2:#3d3d3d;--muted:#757575;--line:#d9d9d9;--line-soft:#e6e4dd;
  --green:#005f5a;--green-accent:#00896c;--purple:#4b47b5;
  --font:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;line-height:1.5}
a{color:var(--green)}
.top{border-bottom:1px solid var(--line-soft)}
.top .inner,.foot .inner{max-width:960px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.brand{font-weight:700;text-decoration:none;color:var(--ink);letter-spacing:-.01em}
.brand span{color:var(--muted);font-weight:500}
.top nav{display:flex;gap:22px}
.top nav a{text-decoration:none;color:var(--ink2);font-size:15px;font-weight:500}
.top nav a:hover{color:var(--green)}
.wrap{max-width:960px;margin:0 auto;padding:48px 24px 80px}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--green);margin:0 0 14px}
h1{font-size:40px;line-height:1.1;letter-spacing:-.025em;font-weight:700;margin:0 0 14px}
.lead{font-size:19px;line-height:1.65;color:var(--ink2);max-width:70ch;margin:0 0 30px}
h2{font-size:25px;letter-spacing:-.02em;font-weight:600;line-height:1.22;margin:0 0 14px}
main > h2{margin-top:44px}
main > ul{margin:0 0 26px;padding:0;list-style:none}
main > ul li{font-size:17px;line-height:1.6;color:var(--ink2);background:var(--surface);border-left:3px solid var(--green);border-radius:0 10px 10px 0;padding:14px 20px;margin:0 0 10px}
main > ul li b{color:var(--ink)}
.stats{display:flex;gap:44px;flex-wrap:wrap;margin:6px 0 26px}
.stat .n{font-size:44px;font-weight:700;letter-spacing:-.025em;line-height:1;color:var(--green);font-variant-numeric:tabular-nums}
.stat .l{font-size:14.5px;color:var(--ink2);margin-top:8px}
.fig{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:30px 32px;margin:22px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.intro{margin:-6px 0 18px;color:var(--ink2);font-size:16px;max-width:74ch}
.note{margin:18px 0 0;color:var(--ink2);font-size:15.5px;line-height:1.5;max-width:82ch}
.muted{color:var(--muted)}
svg{display:block;width:100%;height:auto}
svg text{font-family:var(--font)}
.axl{fill:var(--muted);font-size:15px}
.val{fill:var(--ink);font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.lbl{fill:var(--ink);font-size:17px}
.sub{fill:var(--muted)}
.sec{fill:var(--ink);font-size:17px;font-weight:600}
.dot{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:9px;vertical-align:-1px}
.dot.nc{background:#005f5a}.dot.ng{background:#78c4af}.dot.cc{background:#4b47b5}.dot.cx{background:#9a9a9a}
table.board{width:100%;border-collapse:collapse;font-size:16px;font-variant-numeric:tabular-nums}
table.board th{text-align:left;font-weight:600;color:var(--muted);font-size:13px;letter-spacing:.04em;text-transform:uppercase;padding:0 10px 10px 0;border-bottom:1px solid var(--line)}
table.board td{padding:12px 10px 12px 0;border-bottom:1px solid var(--line-soft);vertical-align:middle}
table.board tr:last-child td{border-bottom:0}
table.board .num{text-align:right;padding-right:0;padding-left:10px}
table.board th.num{padding-right:0}
table.board .strong{font-weight:600}
table.board .rank{font-weight:600;white-space:nowrap}
table.board .spread{font-size:12px;color:var(--muted);font-weight:500;margin-left:6px}
table.board td.title{color:var(--ink2);font-size:15px;line-height:1.35}
table.papers td a{font-weight:500}
.matrixwrap{overflow-x:auto}
table.matrix{border-collapse:separate;border-spacing:3px;font-size:14.5px;font-variant-numeric:tabular-nums}
table.matrix th{font-weight:500;color:var(--ink2);text-align:left;white-space:nowrap;padding:4px 10px 4px 0;font-size:14px}
table.matrix thead th{vertical-align:bottom;text-align:center;padding:0 4px 6px;line-height:1.2}
table.matrix thead th small{color:var(--muted);font-weight:400}
table.matrix td{width:78px;height:40px;text-align:center;border-radius:6px}
table.matrix td.self{background:transparent}
table.matrix td.na{color:var(--muted)}
table.matrix td.w0{background:rgba(117,117,117,.83);color:#fff}
table.matrix td.w1{background:rgba(117,117,117,.68);color:#fff}
table.matrix td.w2{background:rgba(117,117,117,.53);color:#fff}
table.matrix td.w3{background:rgba(117,117,117,.38);color:var(--ink)}
table.matrix td.w4{background:rgba(117,117,117,.23);color:var(--ink)}
table.matrix td.w5{background:rgba(0,95,90,.08);color:var(--ink)}
table.matrix td.w6{background:rgba(0,95,90,.23);color:var(--ink)}
table.matrix td.w7{background:rgba(0,95,90,.38);color:var(--ink)}
table.matrix td.w8{background:rgba(0,95,90,.53);color:#fff}
table.matrix td.w9{background:rgba(0,95,90,.68);color:#fff}
table.matrix td.w10{background:rgba(0,95,90,.83);color:#fff}
.ideas{display:grid;gap:12px}
.idea{display:grid;grid-template-columns:40px 1fr;gap:14px;padding:16px 18px;background:#fff;border:1px solid var(--line-soft);border-radius:12px;text-decoration:none;color:inherit;transition:border-color .15s}
.idea:hover{border-color:var(--green)}
.idea .n{font-size:26px;font-weight:700;color:var(--green);letter-spacing:-.02em;line-height:1.1}
.idea h3{margin:0 0 4px;font-size:18px;font-weight:600;letter-spacing:-.01em}
.idea p{margin:0 0 8px;color:var(--ink2);font-size:15px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.idea .meta{font-size:13.5px;color:var(--muted)}
ul.methods{margin:0 0 6px;padding:0;list-style:none}
ul.methods li{font-size:16.5px;line-height:1.6;color:var(--ink2);padding:0 0 10px}
ul.methods b{color:var(--ink)}
.hyp p{font-size:18px;line-height:1.7;color:var(--ink2);margin:0 0 16px;max-width:76ch}
details.bg{margin:4px 0 30px;max-width:76ch}
details.bg summary{cursor:pointer;color:var(--green);font-weight:500;font-size:16px}
details.bg p{font-size:16px;line-height:1.65;color:var(--ink2);margin:12px 0}
.pick{display:flex;gap:22px;flex-wrap:wrap;margin:0 0 14px}
.pick label{font-size:14px;color:var(--muted);font-weight:500;display:flex;flex-direction:column;gap:6px;flex:1;min-width:220px}
.pick select{font:inherit;font-size:15px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}
.viewer{width:calc(100vw - 32px);max-width:1800px;margin-left:calc(50% - 50vw + 16px);margin-right:calc(50% - 50vw + 16px)}
@media (min-width:1832px){.viewer{margin-left:calc(50% - 900px);margin-right:calc(50% - 900px)}}
.viewer .pick,.viewer h2,.viewer .tally,.viewer .verdicts{max-width:896px}
.pdfs{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.pane{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;min-width:0}
.pdfbox{height:88vh;overflow-y:auto;background:#e9e9e6;padding:1px 0}
.pdfbox canvas{display:block;margin:0 auto 8px;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.pdfbox iframe{display:block;width:100%;height:100%;border:0}
.pdfbox .pad{padding:20px}
.pane-head{display:flex;justify-content:space-between;gap:12px;padding:10px 14px;font-size:13.5px;color:var(--ink2);border-bottom:1px solid var(--line-soft)}
.pane-head span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pane-head a{white-space:nowrap;font-weight:500}
.pane iframe{display:block;width:100%;height:78vh;border:0;background:#f2f2f0}
h2.sub{margin-top:34px;font-size:21px}
.tally{display:flex;gap:22px;flex-wrap:wrap;align-items:center;margin:0 0 16px;font-size:16px}
.tally .t b{margin-right:6px}
.verdicts{display:grid;gap:12px}
.verdict{background:#fff;border:1px solid var(--line-soft);border-radius:12px;padding:16px 18px}
.verdict .vh{display:flex;gap:14px;flex-wrap:wrap;align-items:baseline;font-size:14.5px;margin-bottom:8px}
.verdict .win{margin-left:auto;color:var(--green);font-weight:600}
.verdict p{margin:0 0 12px;font-size:15.5px;line-height:1.6;color:var(--ink2)}
table.scores{border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
table.scores th{font-weight:500;color:var(--muted);text-align:left;padding:3px 14px 3px 0;white-space:nowrap}
table.scores thead th{text-align:center;padding:0 6px 4px;font-size:12.5px}
table.scores td{text-align:center;padding:3px 6px;color:var(--ink)}
.foot{border-top:1px solid var(--line-soft);color:var(--muted);font-size:14px}
@media (max-width:760px){
  .wrap{padding:32px 16px 60px}
  h1{font-size:31px}
  .fig{padding:22px 18px;border-radius:12px}
  .pdfs{grid-template-columns:1fr}
  .viewer{width:auto;margin-left:0;margin-right:0}
  .pdfbox{height:70vh}
  .stats{gap:28px}
  .stat .n{font-size:36px}
  table.board{font-size:14.5px}
  table.board td.title{display:none}
  table.board th:nth-child(2):not(:first-child){}
}
"""


def main() -> None:
    data = load()
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "ideas").mkdir(exist_ok=True)
    (ROOT / "assets/style.css").write_text(CSS.strip() + "\n")
    (ROOT / "assets/idea.js").write_text(IDEA_JS.strip() + "\n")
    if FONT_SRC.exists():
        shutil.copy(FONT_SRC, ROOT / "assets/inter.woff2")
    for p in data["papers"].values():
        dst = ROOT / p["pdf"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p["src"], dst)
    (ROOT / "index.html").write_text(build_index(data))
    (ROOT / "method.html").write_text(build_method(data))
    for n, slug in enumerate(IDEAS, 1):
        if any(i == slug for i, _ in data["papers"]):
            (ROOT / f"ideas/{slug}.html").write_text(build_idea(data, slug, n))
    (ROOT / ".nojekyll").touch()
    print(f"built site: {len(data['papers'])} papers, {len(data['judgments'])} judgments")


if __name__ == "__main__":
    main()
