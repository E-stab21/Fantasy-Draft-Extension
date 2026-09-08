# Player data and prediction models

Question: should this repo train its own fantasy prediction models, or use public ones?

**Use public projections first. Do not build a custom model unless this league's scoring or decision process outgrows them.**

## What we already get for free

### ESPN (primary)

The unofficial fantasy API returns **league-scoring-adjusted** projected points on rosters and free agents. That is the most important number for start/sit and waivers because PPR vs standard, bonus yards, TE premium, and custom scoring are already applied.

`league lineup-advice` and `league waiver-advice` use these ESPN projections by default.

### Sleeper (secondary, no auth)

Public endpoints:

- `https://api.sleeper.app/v1/state/nfl` — current season/week
- `https://api.sleeper.app/v1/players/nfl` — player directory (cache daily)
- `https://api.sleeper.app/v1/players/nfl/trending/add` — add/drop heat
- `https://api.sleeper.app/projections/nfl/{season}/{week}` — weekly projections (`pts_ppr`, `pts_half_ppr`, `pts_std`)

Pass `--sleeper` to overlay these onto ESPN players by normalized name. Stay under Sleeper's 1000 requests/minute guidance.

### nflverse / nflreadpy (historical context)

Open, analysis-grade NFL data (CC-BY 4.0 for most files):

- Weekly and seasonal player stats
- Snap counts, depth charts, injuries, schedules
- Next Gen Stats
- FantasyPros rankings redistributed as `load_ff_rankings()`
- Expected yards / fantasy points as `load_ff_opportunity()`

Install with `pip install 'league-manager[research]'` when an agent needs historical research. Not required for weekly lineup management.

### FantasyPros

Official paid REST API (`https://api.fantasypros.com/public/v2/json`) for consensus rankings and projections across 130+ experts. There is no supported free API. This repo does **not** scrape FantasyPros HTML.

`FANTASYPROS_API_KEY` is used when present. The official REST API (`https://api.fantasypros.com/public/v2/json`, `x-api-key` header) is the first ROS source for trade value. This repo does not scrape FantasyPros HTML. Without a key, valuation falls through to Sleeper remaining weeks (`--sleeper`) and ESPN season remainder.

### Paid sports-data APIs

SportsDataIO, FantasyData, 4for4, and similar sell projections and injuries. Useful only if you want vendor SLAs. Not needed to manage one league.

## Custom models: when they help, when they do not

Open-source weekly fantasy models (XGBoost / LightGBM / small nets on nflverse features) routinely land **close to, not clearly better than**, industry consensus. Published hobby benchmarks often trail a paid/consensus projection by a few percent of MAE, and beat only naive baselines (last week / season average).

A custom model is worth building only if at least one of these is true:

- The league uses unusual scoring that ESPN projections handle poorly
- You want season-long simulation, draft capital, or dynasty values ESPN does not expose
- You will maintain weekly feature pipelines (Vegas lines, injuries, depth-chart changes)

Otherwise a custom model is extra training cost, weekly breakage, and worse injury-news reaction than ESPN/Sleeper/FantasyPros already bake in.

## What this repo does

1. **Start/sit with ESPN this-week projections** (league scoring). `lineup-advice` stays here.
2. **Cross-check with Sleeper** when asked (`--sleeper`).
3. **Use simple optimizers**, not ML: greedy slot fill for lineups; projection delta vs your worst bench piece for waivers.
4. **Redraft trade value** (`league values`, `league trade-grade`): short-term VORP over the next few weeks, rest-of-season VORP through the fantasy playoffs. LT is **not** just this week × weeks left. Order: FantasyPros ROS → Sleeper remaining-week sum → ESPN `projected_total_points − points already scored` → weekly rate × remaining games. Replacement is the third-best free agent at the position. Contender / bubble / rebuilder weights change how ST and LT mix. A stud tax stops 2-for-1 depth from looking even with an elite starter.
5. **Trade search** (`league trade-search`): enumerate 1:1, 2:1, and 1:2 packages against other rosters (hundreds to tens of thousands). Keep deals that are +EV for us on ROS VORP and close-to-even on ESPN face value (weekly × remaining games), so the other manager can say yes.
6. **Buy-low / sell-high** (`league opportunities`): last 1–3 actual games vs those weeks’ ESPN projections (the number other managers anchored on). Cold + still-positive ROS VORP on someone else’s roster is a buy-low. A heater on our roster is a sell-high. Injury with remaining ROS value is also a buy-low. Snap share and recent averages are **not** mixed into our forward value again; they are already inside the projection.

If a later agent is asked to build a weekly point model, start from nflverse weekly stats + ESPN scoring settings, and score it against ESPN/Sleeper holdout weeks before replacing the public numbers.
