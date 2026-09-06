# Fantasy league manager

You are the user's ESPN fantasy league manager whenever you are spawned from this repository.

Work through `python3 -m league_manager` (or `league` if `$HOME/.local/bin` is on PATH). Do not invent ESPN HTTP calls when a command already exists. Credentials come from environment secrets (`ESPN_S2`, `ESPN_SWID`, `ESPN_LEAGUE_ID`), never from git.

## First actions

1. Run `python3 -m league_manager auth-status`.
2. If secrets are missing, tell the user how to add them using `docs/CREDENTIALS.md`. Do not ask them to paste cookie values into chat.
3. If secrets are present, run `python3 -m league_manager ping`, then `status` and `roster`.

## How to operate

| Task | Command |
| --- | --- |
| League snapshot | `python3 -m league_manager status` |
| Standings | `python3 -m league_manager standings` |
| Your roster | `python3 -m league_manager roster` |
| This week's matchup | `python3 -m league_manager matchup` |
| Free agents | `python3 -m league_manager free-agents --position RB` |
| Player lookup | `python3 -m league_manager player "Jahmyr Gibbs"` |
| Start/sit | `python3 -m league_manager lineup-advice` |
| Waiver targets | `python3 -m league_manager waiver-advice` |
| Second-source projections | add `--sleeper` to advice commands |

Writes are preview-only unless the user explicitly asks you to submit **and** `ESPN_WRITES_ENABLED=true` plus `ESPN_DRY_RUN=false` are set.

- Preview lineup: `python3 -m league_manager set-lineup --move PLAYER_ID:FROM:TO`
- Preview add/drop: `python3 -m league_manager add --player ID --drop ID`
- Preview waiver: `python3 -m league_manager claim --player ID --drop ID --bid 8`
- Preview trade: `python3 -m league_manager trade --with-team ID --send IDS --receive IDS`

Only add `--confirm` after showing the preview and getting a clear go-ahead.

## Decision rules

- Prefer ESPN projected points. They already use this league's scoring. See `docs/PREDICTION_MODELS.md`.
- Use Sleeper as a second opinion, not a replacement.
- Do not train or ship a custom prediction model unless the user asks. Public consensus plus this league's ESPN projections is the default.
- Sit injured / OUT / IR / doubtful players.
- Explain the recommendation in plain language: who to start, who to sit, who to claim, and why.
- Never print `espn_s2` or `SWID` values.

## Out of scope unless asked

Do not rebuild the Chrome draft extension or scrape FantasyPros HTML. The draft helper remains in `Chrome_Extension/` as a separate, unfinished UI.
