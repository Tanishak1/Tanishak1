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


# Self-hosted contribution heatmap: generated from the same authenticated GitHub API.
import calendar as monthcalendar
from collections import defaultdict

cell = 12
gap = 3
origin_x, origin_y = 55, 88
weeks = calendar["weeks"]
heat = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="265" viewBox="0 0 900 265" role="img" aria-label="GitHub contribution heatmap for the last year">',
'<rect width="900" height="265" rx="18" fill="#101a32"/>',
'<text x="30" y="39" fill="#f2f6ff" font-family="Arial" font-weight="bold" font-size="23">Contribution Activity</text>',
'<text x="870" y="38" fill="#9baed2" font-family="Arial" font-size="14" text-anchor="end">Last 365 days</text>']
palette = ["#182943", "#145d54", "#1b9a74", "#36cb8d", "#70f5aa"]
for wi, week in enumerate(weeks):
    for day in week["contributionDays"]:
        date = dt.date.fromisoformat(day["date"])
        count = day["contributionCount"]
        x = origin_x + wi * (cell + gap)
        y = origin_y + date.weekday() * (cell + gap)
        level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4
        heat.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{palette[level]}"><title>{date.isoformat()}: {count} contributions</title></rect>')
for label, weekday in [("Mon",0),("Wed",2),("Fri",4)]:
    heat.append(f'<text x="14" y="{origin_y + weekday*(cell+gap)+11}" font-family="Arial" font-size="11" fill="#9baed2">{label}</text>')
heat.append(f'<text x="450" y="234" text-anchor="middle" font-family="Arial" font-size="13" fill="#9baed2">{calendar["totalContributions"]:,} contributions in the last 365 days  •  Updated {html.escape(stamp)}</text></svg>')
Path("assets/contribution-graph.svg").write_text("".join(heat), encoding="utf-8")

# Achievement-style tiles based on measured activity; not official GitHub trophies.
awards = [
    ("CONTRIBUTOR", f'{calendar["totalContributions"]:,}', "Contributions · 365 days"),
    ("CODE AUTHOR", f'{collection["totalCommitContributions"]:,}', "Commits · 365 days"),
    ("PULL REQUESTS", str(user["pullRequests"]["totalCount"]), "Opened · all time"),
    ("REPOSITORY STARS", str(stars), "Received · public repos"),
]
trophy = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="175" viewBox="0 0 900 175" role="img" aria-label="GitHub achievements from live statistics">',
'<rect width="900" height="175" rx="18" fill="#101a32"/>']
for i, (name, count, subtitle) in enumerate(awards):
    x = 20 + i * 222
    trophy.extend([
        f'<rect x="{x}" y="20" width="210" height="132" rx="14" fill="#172541" stroke="#2c4267"/>',
        f'<circle cx="{x+26}" cy="46" r="11" fill="#f0bd59"/>',
        f'<text x="{x+46}" y="51" font-family="Arial" font-weight="bold" font-size="13" fill="#b5c9e7">{html.escape(name)}</text>',
        f'<text x="{x+20}" y="103" font-family="Arial" font-weight="bold" font-size="37" fill="#f2f6ff">{html.escape(count)}</text>',
        f'<text x="{x+20}" y="133" font-family="Arial" font-size="12" fill="#9baed2">{html.escape(subtitle)}</text>'
    ])
trophy.append('</svg>')
Path("assets/github-trophies.svg").write_text("".join(trophy), encoding="utf-8")
print("Generated self-hosted contribution graph and achievement tiles")
