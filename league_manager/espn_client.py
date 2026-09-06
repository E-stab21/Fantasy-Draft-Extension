"""Read and write ESPN fantasy league data using the unofficial v3 API."""

from __future__ import annotations

from typing import Any

from league_manager.config import Settings
from league_manager.serialize import matchup_to_dict, player_to_dict, team_to_dict
from league_manager.writes import WriteResult, post_transaction

SPORT_IMPORT = {
    "nfl": "espn_api.football",
    "nba": "espn_api.basketball",
    "mlb": "espn_api.baseball",
    "nhl": "espn_api.hockey",
}


class EspnClient:
    def __init__(self, settings: Settings, league: Any | None = None):
        self.settings = settings
        self._league = league

    @property
    def league(self) -> Any:
        if self._league is None:
            self._league = self._connect()
        return self._league

    def _connect(self) -> Any:
        import importlib

        sport = self.settings.sport.lower()
        if sport in {"ffl", "football"}:
            sport = "nfl"
        elif sport in {"fba", "basketball"}:
            sport = "nba"
        elif sport in {"flb", "baseball"}:
            sport = "mlb"
        elif sport in {"fhl", "hockey"}:
            sport = "nhl"
        module_name = SPORT_IMPORT.get(sport)
        if not module_name:
            raise ValueError(f"Unsupported sport {self.settings.sport!r}")
        module = importlib.import_module(module_name)
        return module.League(
            league_id=self.settings.league_id,
            year=self.settings.season,
            espn_s2=self.settings.espn_s2,
            swid=self.settings.swid,
        )

    def resolve_team_id(self, team_id: int | None = None) -> int:
        if team_id is not None:
            return team_id
        if self.settings.team_id is not None:
            return self.settings.team_id
        swid = self.settings.swid.lower()
        for team in self.league.teams:
            for owner in getattr(team, "owners", []) or []:
                owner_id = owner.get("id") if isinstance(owner, dict) else str(owner)
                if owner_id and str(owner_id).lower() == swid:
                    return team.team_id
        if len(self.league.teams) == 1:
            return self.league.teams[0].team_id
        raise ValueError(
            "Could not determine your team. Set ESPN_TEAM_ID or pass --team-id."
        )

    def get_team(self, team_id: int | None = None) -> Any:
        resolved = self.resolve_team_id(team_id)
        for team in self.league.teams:
            if team.team_id == resolved:
                return team
        raise ValueError(f"No team with id {resolved}")

    def ping(self) -> dict[str, Any]:
        league = self.league
        team = None
        team_error = None
        try:
            team = self.get_team()
        except ValueError as exc:
            team_error = str(exc)
        return {
            "ok": True,
            "league_id": self.settings.league_id,
            "season": self.settings.season,
            "sport": self.settings.sport,
            "name": getattr(league.settings, "name", None),
            "week": getattr(league, "current_week", None),
            "nfl_week": getattr(league, "nfl_week", None),
            "team_count": len(getattr(league, "teams", []) or []),
            "your_team": team_to_dict(team, include_roster=False) if team else None,
            "team_error": team_error,
        }

    def status(self) -> dict[str, Any]:
        league = self.league
        settings = league.settings
        return {
            "league_id": self.settings.league_id,
            "name": getattr(settings, "name", None),
            "season": self.settings.season,
            "week": getattr(league, "current_week", None),
            "nfl_week": getattr(league, "nfl_week", None),
            "scoring_type": getattr(settings, "scoring_type", None)
            or getattr(settings, "reg_season_count", None),
            "team_count": getattr(settings, "team_count", None)
            or len(league.teams),
            "playoff_team_count": getattr(settings, "playoff_team_count", None),
            "your_team": team_to_dict(self.get_team(), include_roster=False),
        }

    def standings(self) -> list[dict[str, Any]]:
        rows = []
        standing_fn = getattr(self.league, "standings", None)
        teams = standing_fn() if callable(standing_fn) else self.league.teams
        for index, team in enumerate(teams, start=1):
            row = team_to_dict(team, include_roster=False)
            row["rank"] = row.get("standing") or index
            rows.append(row)
        return rows

    def roster(self, team_id: int | None = None) -> dict[str, Any]:
        team = self.get_team(team_id)
        return team_to_dict(team, include_roster=True)

    def matchup(self, week: int | None = None, team_id: int | None = None) -> dict[str, Any]:
        resolved = self.resolve_team_id(team_id)
        scoreboard = self.league.scoreboard(week=week)
        for game in scoreboard:
            payload = matchup_to_dict(game)
            if payload.get("home_id") == resolved or payload.get("away_id") == resolved:
                payload["week"] = week or getattr(self.league, "current_week", None)
                return payload
        return {
            "week": week or getattr(self.league, "current_week", None),
            "message": "No matchup found for that team and week.",
        }

    def scoreboard(self, week: int | None = None) -> list[dict[str, Any]]:
        return [matchup_to_dict(game) for game in self.league.scoreboard(week=week)]

    def free_agents(
        self,
        position: str | None = None,
        size: int = 50,
        week: int | None = None,
    ) -> list[dict[str, Any]]:
        players = self.league.free_agents(week=week, size=size, position=position)
        return [player_to_dict(player, include_lineup=False) for player in players]

    def player(self, name: str) -> dict[str, Any]:
        found = self.league.player_info(name=name)
        if not found:
            return {"name": name, "found": False}
        if isinstance(found, list):
            return {"found": True, "players": [player_to_dict(item, include_lineup=False) for item in found]}
        return {"found": True, "player": player_to_dict(found, include_lineup=False)}

    def activity(self, size: int = 25, msg_type: str | None = None) -> list[dict[str, Any]]:
        items = self.league.recent_activity(size=size, msg_type=msg_type)
        rows = []
        for item in items:
            rows.append(
                {
                    "date": str(getattr(item, "date", None)),
                    "actions": [str(action) for action in getattr(item, "actions", []) or []],
                    "raw": str(item),
                }
            )
        return rows

    def submit_transaction(
        self,
        payload: dict[str, Any],
        *,
        confirm: bool,
        scoring_period_id: int | None = None,
    ) -> WriteResult:
        week = scoring_period_id or getattr(self.league, "current_week", None) or 1
        return post_transaction(
            settings=self.settings,
            payload=payload,
            confirm=confirm,
            scoring_period_id=week,
        )
