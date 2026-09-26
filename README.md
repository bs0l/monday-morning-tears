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


- A Python collector (built on [`espn-api`](https://github.com/cwendt94/espn-api)) fetches every season's league data and computes stats into a set of JSON files
- A static HTML/JS frontend reads those JSON files and renders the site — no backend, no database
- Data refreshes automatically on a weekly cron job and is published via GitHub Pages

This repo holds the frontend (HTML/JS/CSS) that's deployed to GitHub Pages. The data collector runs separately on a home server and pushes updated JSON here.

## A note on data completeness

ESPN's API has real gaps and quirks in older seasons (some years lack reliable keeper, transaction, or bench data). Where the underlying data isn't trustworthy, this site labels it as such or shows it as N/A rather than guessing — accuracy over completeness.

## Tech

- Python (data collection) + `espn-api`
- Vanilla HTML/CSS/JS, Chart.js for visualizations
- Hosted on GitHub Pages

---

## Operations (for maintainers)

The collector script and a couple of credential/config files are **not** part of this repo — they're excluded via `.gitignore` because they contain private league data (real names, ESPN auth cookies) and live only on the home server that runs the collector. Only the generated `output/*.json` files and the frontend get pushed here.

### Pulling frontend changes before testing

The scheduled job already does a `git fetch` + hard reset before every run, so scheduled runs are always on the latest committed frontend/output. For a manual test run, pull first so you're not testing against a stale checkout:

```bash
ssh pi@<server-ip>
cd /home/pi/fantasystats/mmt
git fetch
git reset --hard origin/main
```

### Running the collector manually

```bash
ssh pi@<server-ip>
source ~/fantasy-env/bin/activate
cd /home/pi/fantasystats/mmt
python mmt_collector.py
```

Add `--skip-bench` to skip the (slower) bench-points calculation while testing other changes:

```bash
python mmt_collector.py --skip-bench
```

Output JSON lands in `output/*.json` in that directory. A manual run does **not** commit or push — that only happens via the scheduled wrapper script described below. Diff the output against what's already committed before pushing anything by hand.

### Files that must be manually copied to the server

These are intentionally gitignored and never travel with a normal `git pull` — they have to be copied over by hand (e.g. via `scp`) whenever they change:

| File | Purpose |
|---|---|
| `mmt_collector.py` | The collector script itself |
| `mmt_keepers.py` | Keeper identities, point overrides, and notes — contains real owner/player names |
| `.env` | ESPN auth cookies, shared across leagues this server runs |

```bash
scp mmt_collector.py pi@<server-ip>:/home/pi/fantasystats/mmt
scp mmt_keepers.py pi@<server-ip>:/home/pi/fantasystats/mmt
```

The `.env` file should be `chmod 600` on the server since it holds auth cookies.

### Scheduling

A cron job runs a wrapper shell script weekly during the season, which:
1. `git fetch` + `git reset --hard origin/main` in the league directory
2. Runs the collector via the venv Python
3. On success, commits/pushes the updated `output/*.json` and sends a success notification
4. On failure (collector error or push failure), sends a failure notification with the trailing log lines instead

Logs append indefinitely to a dedicated log file.

### Configuration notes

- `END_YEAR` in the collector is computed dynamically (current year from September onward, previous year otherwise) — no manual bump needed each season
- Auth cookies are read from environment variables at runtime rather than hardcoded in the script
- If the ESPN session cookies expire, the collector exits with a distinct error code and triggers a targeted "cookies expired" notification rather than a generic failure email

---

*This is a personal project for a private fantasy football league — not affiliated with ESPN.*