#!/usr/bin/env python3
"""Generate an animated GitHub profile card using GitHub's authenticated GraphQL API."""
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

USER = "Tanishak1"
TOKEN = os.environ["GITHUB_TOKEN"]
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
      totalCommitContributions
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes { stargazerCount }
      pageInfo { hasNextPage }
    }
  }
}
"""
def request(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
                 "User-Agent": "Tanishak1-profile-card"})
    with urllib.request.urlopen(req, timeout=30) as res:
        result = json.load(res)
    if result.get("errors"):
        raise RuntimeError(str(result["errors"]))
    return result["data"]

now = dt.datetime.now(dt.timezone.utc)
year = now.year
year_start = now - dt.timedelta(days=365)
user = request(QUERY, {"login": USER, "from": year_start.isoformat(), "to": now.isoformat()})["user"]
if not user:
    raise RuntimeError("GitHub user not found")
collection = user["contributionsCollection"]
calendar = collection["contributionCalendar"]
days = sorted((d for w in calendar["weeks"] for d in w["contributionDays"]), key=lambda d: d["date"])
# A streak counts consecutive contribution days; allow today to be unfinished.
today = dt.datetime.now(dt.timezone.utc).date()
by_day = {dt.date.fromisoformat(d["date"]): d["contributionCount"] for d in days}
cursor = today if by_day.get(today, 0) else today - dt.timedelta(days=1)
streak = 0
while by_day.get(cursor, 0) > 0:
    streak += 1
    cursor -= dt.timedelta(days=1)

stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
# GraphQL first 100 repositories only: fetch all remaining repository pages if needed.
if user["repositories"]["pageInfo"]["hasNextPage"]:
    cursor = None
    stars = 0
    while True:
        page = request("""query($login:String!,$after:String) {
          user(login:$login) { repositories(first:100,after:$after,ownerAffiliations:OWNER,privacy:PUBLIC) {
            nodes { stargazerCount } pageInfo { hasNextPage endCursor } } } }""",
            {"login": USER, "after": cursor})["user"]["repositories"]
        stars += sum(r["stargazerCount"] for r in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

values = [
    ("CONTRIBUTIONS", calendar["totalContributions"], "last 365 days"),
    ("COMMITS", collection["totalCommitContributions"], "last 365 days"),
    ("PULL REQUESTS", user["pullRequests"]["totalCount"], "all time"),
    ("ISSUES", user["issues"]["totalCount"], "all time"),
    ("STARS", stars, "public owned repos"),
    ("ACTIVE STREAK", streak, "days"),
]
stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC")
parts = ["""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="360" viewBox="0 0 900 360" role="img" aria-label="Live GitHub analytics">
<defs>
  <linearGradient id="bg" x2="1" y2="1"><stop stop-color="#101a32"/><stop offset="1" stop-color="#0a1021"/></linearGradient>
  <linearGradient id="accent"><stop stop-color="#33d6ff"/><stop offset="1" stop-color="#9c79ff"/></linearGradient>
  <style>
    .title{font:700 27px Arial,sans-serif;fill:#f2f6ff}
    .label{font:600 13px Arial,sans-serif;fill:#9baed2;letter-spacing:1px}
    .num{font:700 39px Arial,sans-serif;fill:#f2f6ff}
    .note{font:12px Arial,sans-serif;fill:#8296bc}
    .pulse{animation:pulse 3s ease-in-out infinite}
    .tile{animation:rise .7s ease-out both}
    @keyframes pulse{50%{opacity:.35}}
    @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    @media(prefers-reduced-motion:reduce){.pulse,.tile{animation:none}}
  </style>
</defs>
<rect width="900" height="360" rx="22" fill="url(#bg)" stroke="#304166"/>
<rect x="28" y="28" width="6" height="34" rx="3" fill="url(#accent)"/>
<text x="49" y="54" class="title">Tanishak's GitHub Analytics</text>
<circle cx="846" cy="44" r="6" fill="#35e4a0" class="pulse"/>
<text x="819" y="49" class="label" text-anchor="end">AUTO</text>
"""]
for i, (label, value, note) in enumerate(values):
    col, row = i % 3, i // 3
    x, y = 28 + col * 287, 84 + row * 119
    parts.append(f'<g class="tile" style="animation-delay:{i * 90}ms">'
                 f'<rect x="{x}" y="{y}" width="269" height="106" rx="14" fill="#172541" stroke="#2c4267"/>'
                 f'<text x="{x+18}" y="{y+27}" class="label">{html.escape(label)}</text>'
                 f'<text x="{x+18}" y="{y+74}" class="num">{value:,}</text>'
                 f'<text x="{x+251}" y="{y+89}" class="note" text-anchor="end">{html.escape(note)}</text></g>')
parts.append(f'<text x="450" y="344" class="note" text-anchor="middle">Source: GitHub API  •  Metrics may exclude private activity  •  Updated {html.escape(stamp)}  •  Scheduled refresh every 6 hours</text></svg>')
Path("assets").mkdir(exist_ok=True)
Path("assets/github-analytics.svg").write_text("".join(parts), encoding="utf-8")
print("Generated assets/github-analytics.svg", values)
