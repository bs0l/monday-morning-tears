# Monday Morning Tears — League Stats

A stats site for **Monday Morning Tears**, a 12-team half-PPR ESPN fantasy football league running continuously since 2013. Built and maintained by the league commissioner.

🔗 **Live site:** https://bs0l.github.io/monday-morning-tears/

## What's here

Every score, matchup, and roster move going back to 2013 is pulled straight from the ESPN Fantasy API and turned into a browsable stats site: standings, head-to-head records, all-time superlatives, season-by-season breakdowns, playoff history, and more.

- **All-time records** — career win/loss, points for/against, championships, playoff appearances, per-owner history across team-name and ownership changes
- **Head-to-head** — every pairing's full history, streaks, and margins
- **Superlatives** — highest/lowest scores, biggest blowouts, closest wins, longest streaks, weekly high/low scorers
- **Season pages** — a dedicated breakdown for every year the league has played
- **Two-week playoff analysis** — how often a week-1 deficit got overturned in week 2
- **Transactions & draft** — trade history, waiver activity, draft-pick retention

## How it works

```
ESPN Fantasy API  →  Python collector  →  JSON  →  static HTML/JS site
```

- A Python collector (built on [`espn-api`](https://github.com/cwendt94/espn-api)) fetches every season's league data and computes stats into a set of JSON files
- A static HTML/JS frontend reads those JSON files and renders the site — no backend, no database
- Data refreshes automatically on a weekly cron job during the season and is published via GitHub Pages

This repo holds the frontend (HTML/JS/CSS) that's deployed to GitHub Pages. The data collector runs separately and pushes updated JSON here.

## A note on data completeness

ESPN's API has real gaps and quirks in older seasons (some years lack reliable keeper, transaction, or bench data). Where the underlying data isn't trustworthy, this site labels it as such or shows it as N/A rather than guessing — accuracy over completeness.

## Tech

- Python (data collection) + `espn-api`
- Vanilla HTML/CSS/JS, Chart.js for visualizations
- Hosted on GitHub Pages

---

*This is a personal project for a private fantasy football league — not affiliated with ESPN.*
