# Odysseus — social autopsy

An interactive, GitHub-Pages-ready dashboard on the *social* shape of this repo:
the PR firehose, PR mortality, who actually contributes (Gini/Lorenz), what the
maintainer does, and how the project taught itself a commit grammar.

## Files
- `index.html` — the dashboard (Chart.js via CDN). Self-contained.
- `data.js` — `window.DATA = {...}` snapshot consumed by the page. **Only thing you regenerate.**
- `data.json` — same payload, for inspection / other tools.
- `process.py` — turns the raw exports in `data/` into `data.json` + (re-emit `data.js`).
- `data/` — raw exports: `prs.json`, `issues.json`, `commits.tsv`.

## Regenerate the data
```bash
cd social-viz
R=pewdiepie-archdaemon/odysseus
gh pr list   -R $R --state all  --limit 4000 \
  --json number,author,createdAt,mergedAt,closedAt,state,baseRefName,additions,deletions,isDraft,labels,title,updatedAt > data/prs.json
gh issue list -R $R --state all --limit 4000 \
  --json number,author,createdAt,closedAt,state,labels,title > data/issues.json
git log --all --date=format:'%Y-%m-%dT%H:%M:%S%z' \
  --pretty=format:'%H%x09%an%x09%ae%x09%ad%x09%s' > data/commits.tsv
python3 process.py
printf 'window.DATA=' > data.js && cat data.json >> data.js && echo ';' >> data.js
```

## Preview locally
`file://` is blocked for the inline data load, so serve over HTTP:
```bash
cd social-viz && python3 -m http.server 8770
# open http://localhost:8770/index.html
```

## Deploy to GitHub Pages
Only `index.html` + `data.js` are needed. Either:
- copy both into a `/docs` folder on a Pages-enabled branch, or
- push this `social-viz/` folder to a `gh-pages` branch and point Pages at it.

## Notes / caveats
- Snapshot is a single point in time; counts drift as the repo moves.
- "Decided" PRs = merged or closed-unmerged (open PRs excluded from mortality).
- Convention match: `(feat|fix|docs|refactor|test|chore|ci|perf|build|style|revert)(scope)!: `.
- Gini is computed on the per-contributor distribution of PRs opened.
- Maintainer identity is matched by name/login `pewdiepie-archdaemon`.
