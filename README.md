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

A scheduled task does exactly this on game days (see "Refresh schedule" below). The page shows an amber
dot in the top bar when its snapshot is more than six hours old, which is the signal that a refresh
failed.

## Refresh schedule

Kickoff windows in Eastern time:

- Sundays, hourly from 8am to 11pm
- Mondays and Thursdays, hourly from 5pm to 11pm
- Tuesday through Saturday, once at about 8:45am

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
