#!/usr/bin/env python3
"""Process gh/git exports into a compact data.json for the social-viz dashboard."""
import json, re, statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
MAINTAINER_LOGINS = {"pewdiepie-archdaemon"}
MAINTAINER_NAMES = {"pewdiepie-archdaemon", "pewdiepie"}
CONV = re.compile(r"^(feat|fix|docs|refactor|test|chore|ci|perf|build|style|revert)(\([^)]*\))?!?:\s", re.I)


def parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def day(dt):
    return dt.date().isoformat()


def week(dt):
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ---- load ----
prs = json.loads((DATA / "prs.json").read_text())
issues = json.loads((DATA / "issues.json").read_text())
commit_rows = [l.split("\t") for l in (DATA / "commits.tsv").read_text().splitlines() if l]

# ---- PR lifecycle ----
pr_daily = defaultdict(lambda: {"opened": 0, "merged": 0, "closed": 0})
# cohort: bucket each PR by the day it was CREATED, track eventual fate + convention
pr_cohort = defaultdict(lambda: {"opened": 0, "merged": 0, "closed": 0, "conv": 0})
pr_weekly = defaultdict(lambda: {"opened": 0, "merged": 0, "closed": 0, "conv": 0, "merge_hours": []})
contrib = defaultdict(lambda: {"opened": 0, "merged": 0, "closed": 0, "additions": 0, "deletions": 0})
types = Counter()
base_branch = Counter()

for pr in prs:
    login = (pr.get("author") or {}).get("login") or "(unknown)"
    created = parse(pr["createdAt"])
    merged = parse(pr.get("mergedAt"))
    closed = parse(pr.get("closedAt"))
    state = pr["state"]
    title = pr.get("title") or ""
    conv = bool(CONV.match(title))
    base_branch[pr.get("baseRefName") or "?"] += 1

    pr_daily[day(created)]["opened"] += 1
    coh = pr_cohort[day(created)]
    coh["opened"] += 1
    if conv:
        coh["conv"] += 1
    w = pr_weekly[week(created)]
    w["opened"] += 1
    if conv:
        w["conv"] += 1
        m = CONV.match(title)
        types[m.group(1).lower()] += 1

    c = contrib[login]
    c["opened"] += 1
    c["additions"] += pr.get("additions") or 0
    c["deletions"] += pr.get("deletions") or 0

    if state == "MERGED" and merged:
        pr_daily[day(merged)]["merged"] += 1
        pr_cohort[day(created)]["merged"] += 1
        pr_weekly[week(merged)]["merged"] += 1
        pr_weekly[week(merged)]["merge_hours"].append((merged - created).total_seconds() / 3600)
        c["merged"] += 1
    elif state == "CLOSED" and closed:
        pr_daily[day(closed)]["closed"] += 1
        pr_cohort[day(created)]["closed"] += 1
        pr_weekly[week(closed)]["closed"] += 1
        c["closed"] += 1

# ---- contributors sorted, mortality, gini ----
contributors = []
for login, d in contrib.items():
    decided = d["merged"] + d["closed"]
    contributors.append({
        "login": login,
        "opened": d["opened"],
        "merged": d["merged"],
        "closed": d["closed"],
        "mergeRate": round(d["merged"] / decided, 3) if decided else None,
        "additions": d["additions"],
        "deletions": d["deletions"],
        "isMaintainer": login in MAINTAINER_LOGINS,
    })
contributors.sort(key=lambda x: x["opened"], reverse=True)

# Gini on PRs-opened distribution
counts = sorted(c["opened"] for c in contributors)
n = len(counts)
tot = sum(counts)
gini = (sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(counts)) / (n * tot)) if tot else 0

# Lorenz curve (cumulative share of PRs by cumulative share of contributors)
lorenz = [{"p": 0.0, "share": 0.0}]
cum = 0
for i, x in enumerate(counts):
    cum += x
    lorenz.append({"p": round((i + 1) / n, 4), "share": round(cum / tot, 4)})

# ---- weekly series assembled ----
weeks = sorted(pr_weekly.keys())
pr_weekly_out = []
for wk in weeks:
    d = pr_weekly[wk]
    decided = d["merged"] + d["closed"]
    mh = d["merge_hours"]
    pr_weekly_out.append({
        "week": wk,
        "opened": d["opened"],
        "merged": d["merged"],
        "closed": d["closed"],
        "mergeRate": round(d["merged"] / decided, 3) if decided else None,
        "convRate": round(d["conv"] / d["opened"], 3) if d["opened"] else None,
        "medianMergeHours": round(statistics.median(mh), 1) if mh else None,
    })

pr_daily_out = [{"date": k, **v} for k, v in sorted(pr_daily.items())]

# ---- issues daily ----
iss_daily = defaultdict(lambda: {"opened": 0, "closed": 0})
for it in issues:
    created = parse(it["createdAt"])
    iss_daily[day(created)]["opened"] += 1
    closed = parse(it.get("closedAt"))
    if closed:
        iss_daily[day(closed)]["closed"] += 1
issues_daily_out = [{"date": k, **v} for k, v in sorted(iss_daily.items())]
issues_open = sum(1 for it in issues if it["state"] == "OPEN")

# ---- commits: maintainer activity + conventional adoption (DAILY, repo is days old) ----
commit_weekly = defaultdict(lambda: {"total": 0, "conv": 0, "maint": 0, "revert": 0})
commit_daily = defaultdict(lambda: {"total": 0, "conv": 0, "maint": 0, "revert": 0})
commit_authors = Counter()
maint_commits = 0
for h, name, email, date, subject in commit_rows:
    dt = parse(date)
    if dt is None:
        continue
    cw = commit_weekly[week(dt)]
    cd = commit_daily[day(dt)]
    cw["total"] += 1
    cd["total"] += 1
    if CONV.match(subject):
        cw["conv"] += 1
        cd["conv"] += 1
    if subject.lower().startswith("revert"):
        cw["revert"] += 1
        cd["revert"] += 1
    is_maint = name in MAINTAINER_NAMES or any(m in email for m in MAINTAINER_NAMES)
    if is_maint:
        cw["maint"] += 1
        cd["maint"] += 1
        maint_commits += 1
    commit_authors[name] += 1

commit_weekly_out = [{
    "week": wk, "total": commit_weekly[wk]["total"],
    "convRate": round(commit_weekly[wk]["conv"] / commit_weekly[wk]["total"], 3) if commit_weekly[wk]["total"] else None,
    "maint": commit_weekly[wk]["maint"], "revert": commit_weekly[wk]["revert"],
} for wk in sorted(commit_weekly)]

commit_daily_out = [{
    "date": dk, "total": commit_daily[dk]["total"],
    "convRate": round(commit_daily[dk]["conv"] / commit_daily[dk]["total"], 3) if commit_daily[dk]["total"] else None,
    "maint": commit_daily[dk]["maint"], "revert": commit_daily[dk]["revert"],
} for dk in sorted(commit_daily)]

# ---- PR cohort daily: of PRs created on day X, eventual fate + convention ----
pr_cohort_out = []
for dk in sorted(pr_cohort):
    d = pr_cohort[dk]
    decided = d["merged"] + d["closed"]
    pr_cohort_out.append({
        "date": dk, "opened": d["opened"], "merged": d["merged"], "closed": d["closed"],
        "open": d["opened"] - decided,
        "mergeRate": round(d["merged"] / decided, 3) if decided else None,
        "convRate": round(d["conv"] / d["opened"], 3) if d["opened"] else None,
    })

# maintainer PR participation
maint_prs = sum(c["opened"] for c in contributors if c["login"] in MAINTAINER_LOGINS)

# ---- headline numbers ----
merged = sum(1 for p in prs if p["state"] == "MERGED")
closed = sum(1 for p in prs if p["state"] == "CLOSED")
opened = sum(1 for p in prs if p["state"] == "OPEN")
decided = merged + closed

out = {
    "meta": {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": "pewdiepie-archdaemon/odysseus",
        "totalPRs": len(prs),
        "merged": merged,
        "closedUnmerged": closed,
        "open": opened,
        "mortalityOfDecided": round(closed / decided, 3) if decided else None,
        "openShare": round(opened / len(prs), 3),
        "totalIssues": len(issues),
        "openIssues": issues_open,
        "totalCommits": len(commit_rows),
        "maintainerCommits": maint_commits,
        "maintainerPRs": maint_prs,
        "contributorCount": n,
        "gini": round(gini, 3),
        "topContributor": contributors[0]["login"] if contributors else None,
        "topContributorPRs": contributors[0]["opened"] if contributors else None,
        "baseBranches": dict(base_branch),
        "firstCommit": min((parse(r[3]).isoformat() for r in commit_rows if parse(r[3])), default=None),
    },
    "prDaily": pr_daily_out,
    "prCohortDaily": pr_cohort_out,
    "prWeekly": pr_weekly_out,
    "commitDaily": commit_daily_out,
    "contributors": contributors,
    "lorenz": lorenz,
    "types": [{"type": t, "count": c} for t, c in types.most_common()],
    "issuesDaily": issues_daily_out,
    "commitWeekly": commit_weekly_out,
}

(HERE / "data.json").write_text(json.dumps(out, separators=(",", ":")))
print("wrote data.json")
print(f"  PRs {len(prs)}  merged {merged}  closed {closed}  open {opened}")
print(f"  mortality(of decided) {out['meta']['mortalityOfDecided']}  gini {gini:.3f}  contributors {n}")
print(f"  maintainer: {maint_commits} direct commits, {maint_prs} PRs opened")
print(f"  top: {contributors[0]['login']} ({contributors[0]['opened']} PRs, merge rate {contributors[0]['mergeRate']})")
print(f"  types: {dict(types.most_common(6))}")
