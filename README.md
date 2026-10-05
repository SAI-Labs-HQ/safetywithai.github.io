# safetywithai.github.io

Public site for the SAI Labs paper arena: six automated research methods,
five research ideas, every pair of papers judged blind by three LLM judges.

The site is static and generated. Do not edit `index.html`, `method.html`,
`ideas/`, `papers/` or `assets/` by hand; they are overwritten by the build.

```bash
cd paper-elo
.venv/bin/python judge.py                                   # judge new papers
.venv/bin/python elo.py --exclude fable --out ratings_nofable.json
.venv/bin/python build_site.py                              # regenerate the site
```

`paper-elo/README.md` describes the judge and rating method;
`paper-elo/FINDINGS.md` has the results and analysis so far.
