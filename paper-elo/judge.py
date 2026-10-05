# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "pymupdf", "pyyaml"]  (or use the local .venv)
# ///
"""Blind pairwise LLM judge for the NeuriCo paper comparison.

Reads the results manifest, pairs finished papers that share an idea, and asks
each judge model which paper is better, in both presentation orders. Judgments
are cached in results/judgments.jsonl, so rerunning only judges new pairs.

    uv run judge.py                 # judge everything that is new
    uv run judge.py --dry-run       # show what would be judged
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import os
import re
import subprocess
from pathlib import Path

import pymupdf
import httpx
import yaml

HERE = Path(__file__).parent
RESULTS = HERE / "results"
NEURICO = Path("/data/haokun_test/neurico")
ENV_FILE = HERE.parent / ".env"
KEY_VAR = "OPENROUTER_API_DEV_KEY"  # the dev / heavy-testing key, not the live prod one

# Judges come from families that did not write any of the papers (the papers
# are by Anthropic and OpenAI models), so no judge can favour its own writing.
JUDGES = [
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.7",
    "deepseek/deepseek-v4-pro",
]

CRITERIA = {
    "addresses_idea": "Answers the research question it was given, including the controls the idea asks for.",
    "rigor": "Experimental design: controls, baselines, sample sizes, statistics, handling of confounds.",
    "evidence": "Conclusions are supported by the reported results; no overclaiming; limitations stated honestly.",
    "insight": "How much a reader learns: depth of analysis and whether the findings are informative.",
    "clarity": "Organisation and writing; methods described well enough to reproduce.",
    "length": "Length fits the content: enough room for methods, results and analysis, without padding or repetition.",
}

SYSTEM = """You are an experienced machine learning reviewer comparing two research papers \
that were written independently to investigate the same research idea. Decide which paper is \
the better piece of research.

Score each paper from 1 to 10 on these criteria:
{criteria}

Rules:
- You see text extracted from the PDFs. Figures are missing and tables may be misaligned. \
Ignore extraction artefacts, the template, the layout and the author line.
- Length is a criterion, in both directions. A paper too short to describe its methods, report \
its results in full or analyse them is weaker. A longer paper is better only if the extra \
length carries substance; padding and repetition count against it. Word counts are provided.
- Judge the research and the write-up as presented. You cannot check the numbers against code.
- Do not favour a paper for being presented first or second.

Reply with a single JSON object and nothing else:
{{"analysis": "<3-6 sentences comparing the papers>",
  "scores": {{"A": {{{keys}}}, "B": {{{keys}}}}},
  "winner": "A" | "B" | "tie"}}
Use "tie" only when the papers are truly indistinguishable in quality."""

USER = """# Research idea both papers were given

{idea}

# Paper A ({words_a} words)

{paper_a}

# Paper B ({words_b} words)

{paper_b}

Which paper is better? Reply with the JSON object only."""


def load_key() -> str:
    if os.environ.get(KEY_VAR):
        return os.environ[KEY_VAR]
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith(KEY_VAR + "="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"{KEY_VAR} not found in environment or {ENV_FILE}")


def load_manifest(refresh: bool) -> list[dict]:
    if refresh:
        subprocess.run(
            ["uv", "run", "python", "scripts/results_manifest.py", "--json"],
            cwd=NEURICO, capture_output=True, check=False,
        )
    return json.loads((NEURICO / "logs/batch/manifest.json").read_text())["runs"]


def idea_text(idea: str) -> str:
    y = yaml.safe_load((NEURICO / f"ideas/arena_candidates/{idea}.yaml").read_text())["idea"]
    parts = [f"Title: {y['title']}", f"Hypothesis:\n{y['hypothesis'].strip()}"]
    desc = (y.get("background") or {}).get("description")
    if desc:
        parts.append(f"Background:\n{desc.strip()}")
    return "\n\n".join(parts)


def tex_title(tex_path: str | None) -> str | None:
    if not tex_path or not Path(tex_path).exists():
        return None
    m = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", Path(tex_path).read_text(errors="ignore"))
    if not m:
        return None
    src, depth, i = Path(tex_path).read_text(errors="ignore"), 1, m.end()
    start = i
    while i < len(src) and depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    t = src[start:i - 1]
    t = re.sub(r"\\\\|\\(?:newline|vspace|hspace)\b(?:\{[^}]*\})?", " ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?\s*", "", t).replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", t.replace("\\", " ")).strip() or None


def paper_text(run: dict, main_only: bool = False) -> dict:
    """Extract blinded text: title + everything from the abstract on.

    The block between title and abstract is dropped because the author line
    names the method ("... and NeuriCo", "Autonomous research study", ...).
    """
    pdf = Path(run["paper_pdf"])
    doc = pymupdf.open(pdf)
    text = "\n".join(page.get_text("text", sort=False) for page in doc)
    m = re.search(r"^\s*Abstract\b", text, flags=re.M | re.I)
    header, body = (text[:m.start()], text[m.start():]) if m else ("", text)
    title = tex_title(run.get("paper_tex")) or " ".join(header.split("\n")[:2]).strip()
    body = re.sub(r"neurico", "[redacted]", body, flags=re.I)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    refs = re.search(r"^\s*References\s*$", body, flags=re.M)
    main_words = len(body[:refs.start()].split()) if refs else len(body.split())
    if main_only and refs:  # drop references and any appendix after them
        body = body[:refs.start()].strip()
    return {
        "text": f"Title: {title}\n\n{body}",
        "words": main_words,
        "pages": doc.page_count,
        "sha": hashlib.sha256(pdf.read_bytes()).hexdigest()[:16],
    }


def parse_verdict(content: str) -> dict:
    m = re.search(r"\{.*\}", content, flags=re.S)
    v = json.loads(m.group(0) if m else content)
    w = str(v.get("winner", "")).strip().lower()
    if w not in {"a", "b", "tie"}:
        raise ValueError(f"bad winner: {v.get('winner')!r}")
    v["winner"] = "tie" if w == "tie" else w.upper()
    return v


async def ask(client: httpx.AsyncClient, key: str, model: str, system: str, user: str) -> tuple[dict, dict]:
    last = None
    for attempt in range(4):
        try:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "max_tokens": 12000,
                },
            )
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(str(data["error"])[:300])
            return parse_verdict(data["choices"][0]["message"]["content"] or ""), data.get("usage", {})
        except Exception as e:  # retry on network, provider and parse errors
            last = e
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{model}: {last!r}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", nargs="+", default=JUDGES)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--no-refresh", action="store_true", help="use the manifest on disk as is")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--main-only", action="store_true",
                    help="judge the main body only (cut at the references); results get a _main suffix")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    suffix = "_main" if args.main_only else ""
    runs = load_manifest(refresh=not args.no_refresh)

    papers: dict[tuple[str, str], dict] = {}
    for r in runs:
        if r["outcome"] == "paper":
            papers[(r["idea"], r["label"])] = paper_text(r, args.main_only)

    # Snapshot of what exists, for elo.py (which never touches the PDFs).
    snapshot = [
        {k: r.get(k) for k in ("idea", "method", "provider", "model", "label", "outcome")}
        | {k: papers[(r["idea"], r["label"])][k] for k in ("words", "pages", "sha") if (r["idea"], r["label"]) in papers}
        for r in runs
    ]
    (RESULTS / f"papers{suffix}.json").write_text(json.dumps(snapshot, indent=1))

    out = RESULTS / f"judgments{suffix}.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            j = json.loads(line)
            done.add((j["idea"], j["first"], j["second"], j["sha_first"], j["sha_second"], j["judge"]))

    criteria = "\n".join(f"- {k}: {v}" for k, v in CRITERIA.items())
    system = SYSTEM.format(criteria=criteria, keys=", ".join(f'"{k}": <1-10>' for k in CRITERIA))

    todo = []
    for idea in sorted({i for i, _ in papers}):
        labels = sorted(l for i, l in papers if i == idea)
        for x, y in itertools.combinations(labels, 2):
            for first, second in ((x, y), (y, x)):  # both orders
                for judge in args.judges:
                    pa, pb = papers[(idea, first)], papers[(idea, second)]
                    if (idea, first, second, pa["sha"], pb["sha"], judge) not in done:
                        todo.append((idea, first, second, judge))

    n_papers = len(papers)
    print(f"{n_papers} finished papers, {len(done)} judgments cached, {len(todo)} to run")
    if args.dry_run or not todo:
        return

    key = load_key()
    sem = asyncio.Semaphore(args.concurrency)
    ideas = {i: idea_text(i) for i in {t[0] for t in todo}}
    lock = asyncio.Lock()
    failed = 0

    async with httpx.AsyncClient(timeout=600) as client:
        async def one(idea: str, first: str, second: str, judge: str) -> None:
            nonlocal failed
            pa, pb = papers[(idea, first)], papers[(idea, second)]
            user = USER.format(idea=ideas[idea], words_a=pa["words"], words_b=pb["words"],
                               paper_a=pa["text"], paper_b=pb["text"])
            async with sem:
                try:
                    verdict, usage = await ask(client, key, judge, system, user)
                except Exception as e:
                    failed += 1
                    print(f"FAILED {idea} {first} vs {second}: {e}")
                    return
            winner = {"A": first, "B": second, "tie": "tie"}[verdict["winner"]]
            rec = {"idea": idea, "first": first, "second": second, "judge": judge,
                   "sha_first": pa["sha"], "sha_second": pb["sha"], "winner": winner,
                   "verdict": verdict, "cost": usage.get("cost")}
            async with lock:
                with out.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
            print(f"{idea:28s} {judge.split('/')[-1]:24s} {first} vs {second} -> {winner}")

        await asyncio.gather(*(one(*t) for t in todo))

    print(f"done; {failed} failed" + (" (rerun to retry them)" if failed else ""))


if __name__ == "__main__":
    asyncio.run(main())
