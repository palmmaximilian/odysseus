#!/usr/bin/env bash
# Rebuild the social-viz snapshot from the upstream repo.
# Runs on the gh-pages branch (locally or in the GitHub Action).
# Needs: gh (authenticated via GH_TOKEN), python3, git.
set -euo pipefail
UP="${UPSTREAM:-pewdiepie-archdaemon/odysseus}"
cd "$(dirname "$0")"
mkdir -p data

echo "Pulling PRs + issues from $UP ..."
gh pr list   -R "$UP" --state all --limit 4000 \
  --json number,author,createdAt,mergedAt,closedAt,state,baseRefName,additions,deletions,isDraft,labels,title,updatedAt > data/prs.json
gh issue list -R "$UP" --state all --limit 4000 \
  --json number,author,createdAt,closedAt,state,labels,title > data/issues.json

echo "Cloning $UP for commit history ..."
rm -rf .upstream
git clone --quiet "https://github.com/$UP.git" .upstream
git -C .upstream log --all --date=format:'%Y-%m-%dT%H:%M:%S%z' \
  --pretty=format:'%H%x09%an%x09%ae%x09%ad%x09%s' > data/commits.tsv
rm -rf .upstream

echo "Processing ..."
python3 process.py
printf 'window.DATA=' > data.js && cat data.json >> data.js && echo ';' >> data.js
echo "Done: $(jq -r '.meta.generated' data.json)"
