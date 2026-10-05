const D = JSON.parse(document.getElementById('data').textContent);
const byLabel = Object.fromEntries(D.papers.map(p => [p.label, p]));
const selA = document.getElementById('selA'), selB = document.getElementById('selB');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function setPane(side, label) {
  const p = byLabel[label];
  document.getElementById('pdf' + side).src = '../' + p.pdf + '#view=FitH';
  document.getElementById('title' + side).textContent = p.name + ' — ' + p.title;
  document.getElementById('dl' + side).href = '../' + p.pdf;
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
  tally.innerHTML = `<div class="t"><span class="dot" style="background:${D.colors[pa.category]}"></span><b>${esc(pa.name)}</b> ${wa}</div>` +
    (t ? `<div class="t muted">tie ${t}</div>` : '') +
    `<div class="t"><span class="dot" style="background:${D.colors[pb.category]}"></span><b>${esc(pb.name)}</b> ${wb}</div>` +
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
selA.selectedIndex = 0; selB.selectedIndex = Math.min(1, D.papers.length - 1);
render();
