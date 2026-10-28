# Prop Curves

Market-implied fantasy football projections built from Kalshi's NFL player and team markets,
benchmarked against Sleeper and ESPN weekly projections.

Published page: https://claude.ai/artifact/FT28fCA23cVAbqGaJizTax

## Layout

- `app/prop-curves.html` — the page. Static HTML; all curve fitting and simulation runs in the browser.
  It loads `data/kalshi-nfl.json` relative to itself.
- `scripts/snapshot.py` — pulls every open Kalshi NFL player ladder and game market plus the Sleeper and
  ESPN projections for the current week, and writes one compact JSON file.
- `app/data/` — snapshot output (ignored by git; it is published alongside the page instead).

## Refreshing the board

    python3 -I scripts/snapshot.py app/data

Takes about four minutes: Kalshi rate-limits to roughly one request per second. Then republish
`app/prop-curves.html` to the artifact URL above with `app/data/kalshi-nfl.json` attached as the
published file `data/kalshi-nfl.json`.

A scheduled task does the same thing on a fixed cadence (see "Refresh schedule" below). The page shows
an amber dot in the top bar when its snapshot is more than six hours old.

## Refresh schedule

A scheduled task refreshes the board once a day at 8:44am Eastern on Wednesday, Thursday, Friday and
Saturday. There are no automatic runs Sunday through Tuesday, since lineups are locked by then; run the
task by hand from the scheduled tasks list in the Claude app whenever fresher numbers are wanted.

The scheduled task does not use this repository. Its prompt carries a copy of `scripts/snapshot.py`,
because sessions started by a scheduled task are not allowed to run code from a freshly cloned repo. If
the script changes here, update the task's prompt to match.

## Why not live?

Kalshi's API returns 403 to any request carrying a browser `Origin` header, so the page cannot call it
directly. The page's "Refresh live" button works only through a relay set under "Live data settings";
a tiny Cloudflare Worker that forwards to Kalshi and adds CORS headers is enough.

## Method

Each strike's yes price (mid of bid and ask) is read as P(stat >= strike). Strikes quoted wider than 30c
are ignored. Yardage ladders get a Weibull or lognormal survival fit (whichever sits closer under
weighted least squares); count ladders (receptions, touchdowns) are read directly. Fantasy points are
scored from the implied means, and the points distribution and touchdown scenarios come from sampling
each stat independently, which understates the spread a little.
