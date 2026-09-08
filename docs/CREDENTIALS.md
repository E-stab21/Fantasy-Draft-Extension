# ESPN credentials

ESPN has no official public fantasy API. Private leagues are accessed with the same session cookies the ESPN website uses.

Never commit these values. Put them in Cloud Agent environment secrets or a local `.env` file (see `.env.example`).

## Required secrets

| Secret | What it is |
| --- | --- |
| `ESPN_S2` | Long `espn_s2` cookie |
| `ESPN_SWID` | `SWID` cookie, including `{curly braces}` |
| `ESPN_LEAGUE_ID` | Number from the league URL (`leagueId=`) |

## Optional secrets

| Secret | What it is |
| --- | --- |
| `ESPN_TEAM_ID` | Your team number if SWID matching fails |
| `ESPN_SEASON` | Season year; defaults to the current calendar year |
| `ESPN_SPORT` | `nfl` (default), `nba`, `mlb`, or `nhl` |
| `ESPN_WRITES_ENABLED` | Set `true` only when you want live lineup/waiver/trade posts |
| `ESPN_DRY_RUN` | Defaults to `true`. Set `false` with writes enabled to actually submit |
| `FANTASYPROS_API_KEY` | Optional paid FantasyPros key. When set, ROS trade value uses their official REST API (never HTML scrape) |

## How to copy cookies

1. Sign in at [fantasy.espn.com](https://fantasy.espn.com) and open your league.
2. Copy `leagueId` from the address bar.
3. Open DevTools → Application → Cookies.
4. Look under `espn.com` or `fantasy.espn.com`.
5. Copy `espn_s2` and `SWID`.

Cookies expire. A 401 from `league ping` means refresh them.

## Cloud Agents

Add the secrets on the Cloud Agent environment that this repo uses. After they are saved, newly spawned agents can run `league ping` without a local `.env`.
