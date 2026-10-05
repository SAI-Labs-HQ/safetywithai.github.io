"""Draw the ratings figure in the SAI blog style (results/elo.html and elo.png).

    .venv/bin/python plot.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
BLOG_FIGURES = Path("/data/haokunliu/veritas-workspace/ICML2026-SAI-demo/blog/figures.html")

# Blog palette: green for our system, purple and grey for the comparisons.
COLOR = {"NeuriCo · Claude": "#005f5a", "NeuriCo · GPT": "#78c4af", "Claude Code": "#4b47b5", "Codex": "#9a9a9a"}
MODEL = {"claude-opus-5-5": "Opus 5.5", "claude-fable-5-1": "Fable 5.1",
         "gpt-5-6-sol": "GPT-5.6-sol", "gpt-6-astra": "GPT-6-Astra"}

CSS = """
:root{--bg:#ffffff;--surface:#fafaf8;--ink:#1e1e1e;--ink2:#3d3d3d;--muted:#757575;
  --line:#d9d9d9;--baseline:#cfcfca;
  --font:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;line-height:1.5}
.wrap{max-width:960px;margin:0 auto;padding:24px}
.fig{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:30px 32px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.fig h2{margin:0 0 14px;font-size:25px;letter-spacing:-.02em;font-weight:600;line-height:1.22}
.note{margin:18px 0 0;color:var(--ink2);font-size:16px;line-height:1.5;font-weight:500}
svg{display:block;width:100%;height:auto}
text{font-family:var(--font)}
.axl{fill:var(--muted);font-size:15px}
.val{fill:var(--ink);font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.lbl{fill:var(--ink);font-size:17px}
.sub{fill:var(--muted)}
.sec{fill:var(--ink);font-size:17px;font-weight:600}
"""


def inter_font_face() -> str:
    """Reuse the Inter font embedded in the blog's figures page."""
    if BLOG_FIGURES.exists():
        m = re.search(r"@font-face\{[^}]*\}", BLOG_FIGURES.read_text())
        if m:
            return m.group(0)
    return ""


def method_name(label: str) -> str:
    for slug, name in MODEL.items():
        if label.endswith(slug):
            return name
    return label


def build_svg(data: dict, categories_only: bool = False) -> str:
    cats, methods = data["categories"], data["methods"]
    W, X0, X1, ROW = 894, 250, 800, 46
    rows = cats if categories_only else cats + methods
    lo = min(r["lo"] for r in rows)
    hi = max(r["hi"] for r in rows)
    lo, hi = (lo // 200) * 200, -(-hi // 200) * 200
    x = lambda v: X0 + (v - lo) / (hi - lo) * (X1 - X0)

    out, y = [], 0

    def section(title: str, items: list[dict], label) -> None:
        nonlocal y
        top = y + (34 if title else 0)
        if title:
            out.append(f'<text class="sec" x="0" y="{y + 18}">{title}</text>')
        bottom = top + ROW * len(items)
        for t in range(lo, hi + 1, 200):
            out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top}" y2="{bottom}" stroke="var(--line)" '
                       f'stroke-width="1"{"" if t != 1000 else " stroke-dasharray=\"4 4\" stroke=\"#b3b3b3\""}/>')
        for i, r in enumerate(items):
            cy = top + ROW * i + ROW / 2
            c = COLOR[r.get("category", r["name"])]
            out.append(f'<text class="lbl" x="0" y="{cy + 6}">{label(r)}</text>')
            out.append(f'<line x1="{x(r["lo"]):.1f}" x2="{x(r["hi"]):.1f}" y1="{cy}" y2="{cy}" stroke="{c}" '
                       f'stroke-width="6" stroke-linecap="round" opacity=".3"/>')
            out.append(f'<circle cx="{x(r["elo"]):.1f}" cy="{cy}" r="9" fill="{c}"/>')
            out.append(f'<text class="val" x="{W}" y="{cy + 6}" text-anchor="end">{r["elo"]}</text>')
        y = bottom

    if categories_only:
        section("", cats, lambda r: r["name"])
    else:
        section("By category", cats, lambda r: r["name"])
        y += 26
        section("By method", methods,
                lambda r: f'{r["category"].split(" · ")[0]} <tspan class="sub">· {method_name(r["name"])}</tspan>')
    y += 24
    for t in range(lo, hi + 1, 200):
        out.append(f'<text class="axl" x="{x(t):.1f}" y="{y}" text-anchor="middle">{t}</text>')
    y += 26
    out.append(f'<text class="axl" x="{(X0 + X1) / 2}" y="{y}" text-anchor="middle">Elo rating (1000 = average)</text>')
    return f'<svg viewBox="0 0 {W} {y + 6}" role="img">{"".join(out)}</svg>'


def build_bars(data: dict) -> str:
    """Methods only, as horizontal bars from zero, no intervals."""
    methods = data["methods"]
    W, X0, X1, ROW, BAR = 894, 250, 800, 44, 22
    hi = -(-max(r["elo"] for r in methods) // 200) * 200
    x = lambda v: X0 + v / hi * (X1 - X0)
    out = []
    top = 6
    bottom = top + ROW * len(methods)
    for t in range(0, hi + 1, 200):
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top}" y2="{bottom}" stroke="var(--line)" stroke-width="1"/>')
    out.append(f'<line x1="{x(1000):.1f}" x2="{x(1000):.1f}" y1="{top}" y2="{bottom}" stroke="#b3b3b3" stroke-width="1" stroke-dasharray="4 4"/>')
    for i, r in enumerate(methods):
        cy = top + ROW * i + ROW / 2
        c = COLOR[r["category"]]
        out.append(f'<text class="lbl" x="0" y="{cy + 6}">{r["category"].split(" · ")[0]} '
                   f'<tspan class="sub">· {method_name(r["name"])}</tspan></text>')
        out.append(f'<rect x="{X0}" y="{cy - BAR / 2}" width="{x(r["elo"]) - X0:.1f}" height="{BAR}" rx="4" fill="{c}"/>')
        out.append(f'<text class="val" x="{x(r["elo"]) + 10:.1f}" y="{cy + 6}">{r["elo"]}</text>')
    y = bottom + 24
    for t in range(0, hi + 1, 200):
        out.append(f'<text class="axl" x="{x(t):.1f}" y="{y}" text-anchor="middle">{t}</text>')
    y += 26
    out.append(f'<text class="axl" x="{(X0 + X1) / 2}" y="{y}" text-anchor="middle">Elo rating (1000 = average)</text>')
    return f'<svg viewBox="0 0 {W} {y + 6}" role="img">{"".join(out)}</svg>'


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", default="ratings.json", help="input file in results/")
    ap.add_argument("--name", default="elo", help="output base name in results/")
    args = ap.parse_args()
    data = json.loads((RESULTS / args.ratings).read_text())
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1008, "height": 800}, device_scale_factor=2)
        variants = ((args.name, build_svg(data)), (f"{args.name}-category", build_svg(data, True)),
                    (f"{args.name}-bars", build_bars(data)))
        for name, svg in variants:
            html = f"""<!doctype html><meta charset="utf-8"><title>Paper Elo</title>
<style>{inter_font_face()}{CSS}</style>
<div class="wrap"><section class="fig">
{"" if name.endswith("-bars") else "<h2>Which method writes the better paper?</h2>"}
{svg}
</section></div>"""
            (RESULTS / f"{name}.html").write_text(html)
            page.goto((RESULTS / f"{name}.html").as_uri())
            page.evaluate("document.fonts.ready")
            page.locator(".wrap").screenshot(path=str(RESULTS / f"{name}.png"))
            print("wrote", RESULTS / f"{name}.png")
        browser.close()


if __name__ == "__main__":
    main()
