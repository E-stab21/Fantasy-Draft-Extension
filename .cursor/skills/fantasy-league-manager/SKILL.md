---
name: fantasy-league-manager
description: Manage the user's ESPN fantasy league with the league CLI, credentials from environment secrets, and public projection sources. Use whenever the user asks about their roster, lineup, waivers, trades, standings, or player decisions.
---

# Fantasy league manager

## Credentials

Required environment secrets:

- `ESPN_S2`
- `ESPN_SWID` (keep curly braces)
- `ESPN_LEAGUE_ID`

Optional: `ESPN_TEAM_ID`, `ESPN_SEASON`, `ESPN_SPORT`.

```bash
python3 -m league_manager auth-status
python3 -m league_manager ping
```

If auth fails with 401, the ESPN cookies expired. Ask the user to refresh secrets using `docs/CREDENTIALS.md`.

## Weekly loop

```bash
python3 -m league_manager status
python3 -m league_manager roster
python3 -m league_manager matchup
python3 -m league_manager lineup-advice
python3 -m league_manager waiver-advice
python3 -m league_manager values
```

Add `--sleeper` when you want a second projection source.

## Trades (redraft)

```bash
python3 -m league_manager values --window auto --sleeper
python3 -m league_manager trade-search --sleeper
python3 -m league_manager trade-grade --send 111,222 --receive 333 --sleeper
```

`--window` can be `auto`, `contender`, `bubble`, or `rebuilder`. Auto uses record and standings. ST is the next `--horizon` weeks (default 3). LT prefers FantasyPros ROS, Sleeper remaining weeks, or ESPN season remainder over flattening this week. `trade-search` walks 1:1 / 2:1 / 1:2 against every roster and keeps packages that are +EV for us and close on ESPN face value. Grade before proposing; `league trade` attaches the same grade on preview.

```bash
python3 -m league_manager opportunities
```

Buy-lows are on other rosters (cold stretch or injury, ROS VORP still positive). Sell-highs are on our roster (heater vs weekly projection). Pairings are suggested; always `trade-grade` before offering. Recency is the *market* signal, not a second projection.

## Writes

Preview first. Example:

```bash
python3 -m league_manager set-lineup --move 3139477:BE:RB
python3 -m league_manager add --player 123 --drop 456
python3 -m league_manager claim --player 123 --drop 456 --bid 5
```

Submit only when the user says to execute, then add `--confirm`. Live posts also need `ESPN_WRITES_ENABLED=true` and `ESPN_DRY_RUN=false`.

## Projections

Do not train a model unless asked. Start/sit uses ESPN this-week projections. Trade ROS uses FantasyPros (official API + `FANTASYPROS_API_KEY` only — do not scrape), Sleeper remaining weeks (`--sleeper`), or ESPN season projection minus points scored. Research notes live in `docs/PREDICTION_MODELS.md`.
