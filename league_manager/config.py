"""Load ESPN credentials from environment secrets or a local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

SPORT_CODES = {
    "nfl": "ffl",
    "football": "ffl",
    "ffl": "ffl",
    "nba": "fba",
    "basketball": "fba",
    "fba": "fba",
    "mlb": "flb",
    "baseball": "flb",
    "flb": "flb",
    "nhl": "fhl",
    "hockey": "fhl",
    "fhl": "fhl",
}


class ConfigError(RuntimeError):
    """Missing or invalid league-manager configuration."""


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    league_id: int
    espn_s2: str
    swid: str
    season: int
    sport: str = "nfl"
    team_id: int | None = None
    writes_enabled: bool = False
    dry_run: bool = True
    fantasypros_api_key: str | None = None

    @property
    def espn_sport_code(self) -> str:
        try:
            return SPORT_CODES[self.sport.lower()]
        except KeyError as exc:
            raise ConfigError(
                f"Unsupported ESPN_SPORT={self.sport!r}. "
                f"Use one of: {', '.join(sorted(set(SPORT_CODES)))}"
            ) from exc

    @property
    def cookies(self) -> dict[str, str]:
        return {"espn_s2": self.espn_s2, "SWID": self.swid}

    def missing_auth_fields(self) -> list[str]:
        missing = []
        if not self.espn_s2:
            missing.append("ESPN_S2")
        if not self.swid:
            missing.append("ESPN_SWID")
        if not self.league_id:
            missing.append("ESPN_LEAGUE_ID")
        return missing


def load_dotenv_files() -> None:
    """Load repo-root .env if present. Existing process env wins."""
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env", override=False)


def auth_status() -> dict[str, object]:
    """Report which credential env vars are present without validating them."""
    load_dotenv_files()
    present = {
        "ESPN_S2": bool(os.getenv("ESPN_S2", "").strip()),
        "ESPN_SWID": bool(os.getenv("ESPN_SWID", "").strip()),
        "ESPN_LEAGUE_ID": bool(os.getenv("ESPN_LEAGUE_ID", "").strip()),
        "ESPN_TEAM_ID": bool(os.getenv("ESPN_TEAM_ID", "").strip()),
        "ESPN_SEASON": bool(os.getenv("ESPN_SEASON", "").strip()),
    }
    required = ["ESPN_S2", "ESPN_SWID", "ESPN_LEAGUE_ID"]
    return {
        "ready": all(present[name] for name in required),
        "present": present,
        "missing": [name for name in required if not present[name]],
        "writes_enabled": _truthy(os.getenv("ESPN_WRITES_ENABLED")),
        "dry_run": _truthy(os.getenv("ESPN_DRY_RUN"), default=True),
    }


def load_settings() -> Settings:
    load_dotenv_files()
    league_raw = os.getenv("ESPN_LEAGUE_ID", "").strip()
    espn_s2 = os.getenv("ESPN_S2", "").strip()
    swid = os.getenv("ESPN_SWID", "").strip()
    missing = [
        name
        for name, value in (
            ("ESPN_LEAGUE_ID", league_raw),
            ("ESPN_S2", espn_s2),
            ("ESPN_SWID", swid),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            "Missing required ESPN credentials: "
            + ", ".join(missing)
            + ". Add them as Cloud Agent environment secrets or a local .env file. "
            "See docs/CREDENTIALS.md."
        )
    try:
        league_id = int(league_raw)
    except ValueError as exc:
        raise ConfigError(f"ESPN_LEAGUE_ID must be an integer, got {league_raw!r}") from exc

    season = _optional_int("ESPN_SEASON") or date.today().year
    sport = os.getenv("ESPN_SPORT", "nfl").strip() or "nfl"
    return Settings(
        league_id=league_id,
        espn_s2=espn_s2,
        swid=swid,
        season=season,
        sport=sport,
        team_id=_optional_int("ESPN_TEAM_ID"),
        writes_enabled=_truthy(os.getenv("ESPN_WRITES_ENABLED")),
        dry_run=_truthy(os.getenv("ESPN_DRY_RUN"), default=True),
        fantasypros_api_key=os.getenv("FANTASYPROS_API_KEY", "").strip() or None,
    )
