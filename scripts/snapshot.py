#!/usr/bin/env python3
"""Snapshot Kalshi's open NFL markets plus benchmark projections into one compact JSON file.

Usage: python3 -I snapshot.py OUT_DIR
Writes OUT_DIR/kalshi-nfl.json
"""
import json, sys, time, urllib.request, urllib.parse, os, re
from datetime import datetime, timezone

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = "Mozilla/5.0 (Macintosh)"
# player series: ticker -> (stat key, label, kind)  kind: yds | count | single
SERIES = {
    "KXNFLRECYDS":  ("rec_yds",  "Receiving yards",       "yds"),
    "KXNFLRSHYDS":  ("rush_yds", "Rushing yards",         "yds"),
    "KXNFLPASSYDS": ("pass_yds", "Passing yards",         "yds"),
    "KXNFLRRYDS":   ("rr_yds",   "Rush + receiving yards","yds"),
    "KXNFLREC":     ("rec",      "Receptions",            "count"),
    "KXNFLPASSCOMP":("pass_cmp", "Completions",           "count"),
    "KXNFLPASSATT": ("pass_att", "Pass attempts",         "count"),
    "KXNFLRSHATT":  ("rush_att", "Rush attempts",         "count"),
    "KXNFLPASSTDS": ("pass_td",  "Passing TDs",           "count"),
    "KXNFLPASSINT": ("pass_int", "Interceptions thrown",  "count"),
    "KXNFLTD":      ("td",       "Touchdowns",            "count"),
    "KXNFLFFPTS":   ("ff_pts",   "Fantasy points",        "yds"),
    "KXNFLLONGREC": ("long_rec", "Longest reception",     "yds"),
    "KXNFLLONGRSH": ("long_rush","Longest rush",          "yds"),
    "KXNFLFIRSTTD": ("first_td", "First TD scorer",       "single"),
}
# game/team series: ticker -> (key, label)
TEAM_SERIES = {
    "KXNFLGAME":      ("win",      "Win probability"),
    "KXNFLTOTAL":     ("total",    "Game total points"),
    "KXNFLTEAMTOTAL": ("team_pts", "Team points"),
    "KXNFLTEAMYDS":   ("team_yds", "Team total yards"),
}
KALSHI_TO_STD = {"LA": "LAR", "JAC": "JAX", "WSH": "WAS"}
PAUSE = 1.0

def get(path, params, base=BASE, headers=None):
    url = base + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(6):
        h = {"User-Agent": UA, "Accept": "application/json"}
        if headers: h.update(headers)
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            if base == BASE:
                time.sleep(PAUSE)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 * (attempt + 1)
                print(f"  429 on {path}, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("gave up on " + url)

def fnum(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None

def norm_name(n):
    n = n.lower().replace("'", "").replace(".", "")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"[^a-z]", "", n)

def price_fields(m):
    return {
        "b": fnum(m.get("yes_bid_dollars")), "a": fnum(m.get("yes_ask_dollars")),
        "l": fnum(m.get("last_price_dollars")),
        "bs": fnum(m.get("yes_bid_size_fp")), "as": fnum(m.get("yes_ask_size_fp")),
        "v": fnum(m.get("volume_fp")), "c": m.get("close_time"),
    }

def fetch_events(ser, events):
    ev = get("/events", {"series_ticker": ser, "status": "open", "limit": 200})
    for e in ev.get("events", []):
        sub = e.get("sub_title") or ""
        m = re.match(r"([A-Z]{2,3}) vs ([A-Z]{2,3})", sub)
        teams = [m.group(1), m.group(2)] if m else []
        events[e["event_ticker"]] = {
            "title": e.get("title"), "sub": sub, "teams": teams,
            "teams_std": [KALSHI_TO_STD.get(t, t) for t in teams],
        }

def fetch_markets(ser):
    cursor = None
    while True:
        params = {"series_ticker": ser, "status": "open", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get("/markets", params)
        for m in d.get("markets", []):
            yield m
        cursor = d.get("cursor")
        if not cursor:
            break

def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    events = {}
    markets = []
    team_markets = []
    for ser, (key, label, kind) in SERIES.items():
        fetch_events(ser, events)
        n = 0
        for m in fetch_markets(ser):
            sub = m.get("yes_sub_title") or m.get("title") or ""
            player = sub.split(":")[0].strip()
            evt = m.get("event_ticker", "")
            seg = m["ticker"].split("-")
            pseg = seg[2] if len(seg) > 2 else ""
            teams = events.get(evt, {}).get("teams", [])
            team = next((t for t in sorted(teams, key=len, reverse=True) if pseg.startswith(t)), None)
            rec = {"t": m["ticker"], "s": key, "e": evt, "p": player,
                   "tm": KALSHI_TO_STD.get(team, team), "k": m.get("floor_strike")}
            rec.update(price_fields(m))
            markets.append(rec)
            n += 1
        print(f"{ser}: {n} markets", file=sys.stderr)
    for ser, (key, label) in TEAM_SERIES.items():
        fetch_events(ser, events)
        n = 0
        for m in fetch_markets(ser):
            evt = m.get("event_ticker", "")
            seg = m["ticker"].split("-")
            pseg = seg[2] if len(seg) > 2 else ""
            teams = events.get(evt, {}).get("teams", [])
            team = next((t for t in sorted(teams, key=len, reverse=True) if pseg.startswith(t)), None)
            rec = {"t": m["ticker"], "s": key, "e": evt, "tm": KALSHI_TO_STD.get(team, team),
                   "k": m.get("floor_strike"), "title": m.get("yes_sub_title") or m.get("title")}
            rec.update(price_fields(m))
            team_markets.append(rec)
            n += 1
        print(f"{ser}: {n} markets", file=sys.stderr)

    # ---- benchmark projections ----
    bench = {"sources": {}, "players": {}}
    try:
        state = get("/v1/state/nfl", None, base="https://api.sleeper.app")
        week, season = state["week"], state["season"]
        rows = get(f"/projections/nfl/{season}/{week}",
                   {"season_type": "regular", "position[]": ["QB", "RB", "WR", "TE"]},
                   base="https://api.sleeper.app")
        n = 0
        for r in rows:
            p = r.get("player") or {}
            st = r.get("stats") or {}
            if not st.get("pts_ppr") and not st.get("pass_yd"):
                continue
            name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            key = norm_name(name)
            entry = bench["players"].setdefault(key, {"name": name})
            entry.update({"pos": p.get("position"), "team": r.get("team"), "opp": r.get("opponent"),
                          "injury": p.get("injury_status")})
            entry["sleeper"] = {k: st.get(k) for k in [
                "pts_ppr", "pts_half_ppr", "pts_std", "rec", "rec_yd", "rec_td", "rec_tgt",
                "rush_att", "rush_yd", "rush_td", "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int"]
                if st.get(k) is not None}
            n += 1
        bench["sources"]["sleeper"] = {"label": "Sleeper (Rotowire)", "week": week, "season": season, "n": n}
        print(f"sleeper: {n} projections for week {week}", file=sys.stderr)
    except Exception as e:
        print("sleeper failed:", e, file=sys.stderr)
        week = None
    try:
        if week is None:
            raise RuntimeError("no week")
        flt = json.dumps({"players": {"limit": 2000, "sortPercOwned": {"sortAsc": False, "sortPriority": 1},
                                      "filterStatsForCurrentSeasonScoringPeriodId": {"value": [week]}}})
        d = get(f"/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3", {"view": "kona_player_info"},
                base="https://lm-api-reads.fantasy.espn.com", headers={"X-Fantasy-Filter": flt})
        POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
        TEAM = {1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC",
                13: "LV", 14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT",
                24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU"}
        SID = {"3": "pass_yd", "4": "pass_td", "20": "pass_int", "0": "pass_att", "1": "pass_cmp",
               "23": "rush_att", "24": "rush_yd", "25": "rush_td", "53": "rec", "42": "rec_yd", "43": "rec_td", "58": "rec_tgt"}
        n = 0
        for row in d.get("players", []):
            p = row.get("player") or {}
            pos = POS.get(p.get("defaultPositionId"))
            if not pos:
                continue
            proj = next((s for s in p.get("stats", []) if s.get("scoringPeriodId") == week and s.get("statSourceId") == 1), None)
            if not proj or not proj.get("appliedTotal"):
                continue
            name = p.get("fullName", "")
            key = norm_name(name)
            entry = bench["players"].setdefault(key, {"name": name})
            entry.setdefault("pos", pos); entry.setdefault("team", TEAM.get(p.get("proTeamId")))
            if p.get("injuryStatus") and p.get("injuryStatus") != "ACTIVE":
                entry.setdefault("injury", p.get("injuryStatus"))
            comp = {SID[k]: round(v, 2) for k, v in (proj.get("stats") or {}).items() if k in SID}
            comp["pts_ppr"] = round(proj["appliedTotal"], 2)
            entry["espn"] = comp
            n += 1
        bench["sources"]["espn"] = {"label": "ESPN", "week": week, "season": season, "n": n}
        print(f"espn: {n} projections", file=sys.stderr)
    except Exception as e:
        print("espn failed:", e, file=sys.stderr)

    snap = {
        "taken_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week": week,
        "source": "Kalshi public API, mid of yes bid/ask",
        "stats": {k: {"label": v[0], "kind": v[1], "series": s} for s, (k, *v) in SERIES.items()},
        "team_stats": {k: {"label": v, "series": s} for s, (k, v) in TEAM_SERIES.items()},
        "events": events,
        "markets": markets,
        "team_markets": team_markets,
        "bench": bench,
    }
    with open(os.path.join(out_dir, "kalshi-nfl.json"), "w") as f:
        json.dump(snap, f, separators=(",", ":"))
    print(f"wrote {len(markets)} player markets, {len(team_markets)} team markets, {len(events)} events, {len(bench['players'])} bench players", file=sys.stderr)

if __name__ == "__main__":
    main()
