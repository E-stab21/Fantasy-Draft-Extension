"""Official FantasyPros REST adapter. Never scrape FantasyPros HTML."""

from __future__ import annotations

import statistics
from typing import Any, Callable

import requests

from league_manager.sleeper import normalize_name

BASE_URL = "https://api.fantasypros.com/public/v2/json"
ALT_BASE_URL = "https://api.fantasypros.com/v2/json"
DEFAULT_POSITIONS = "QB:RB:WR:TE"
HttpGet = Callable[..., Any]


def scoring_points_key(scoring: str) -> str:
    kind = (scoring or "PPR").strip().upper()
    if kind in {"PPR"}:
        return "points_ppr"
    if kind in {"HALF", "HALF_PPR", "HALF-PPR"}:
        return "points_half"
    return "points"


def _player_points(row: dict[str, Any], scoring: str) -> float | None:
    stats = row.get("stats") or row.get("projections") or {}
    if not isinstance(stats, dict):
        stats = {}
    key = scoring_points_key(scoring)
    for candidate in (key, "points_ppr" if key != "points" else "points", "points", "fpts", "FPTS"):
        value = stats.get(candidate)
        if value is None and candidate == key:
            value = row.get(candidate)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def parse_players(payload: dict[str, Any], *, scoring: str = "PPR") -> dict[str, dict[str, Any]]:
    rows = payload.get("players") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("player_name")
        if not name:
            continue
        points = _player_points(row, scoring)
        if points is None:
            continue
        parsed[normalize_name(str(name))] = {
            "name": name,
            "fpid": row.get("fpid") or row.get("player_id"),
            "position": row.get("position_id") or row.get("pos") or row.get("position"),
            "team": row.get("team_id") or row.get("player_team_id"),
            "fpts": points,
        }
    return parsed


def classify_scope(
    parsed: dict[str, dict[str, Any]],
    *,
    params: dict[str, Any],
    response_week: Any = None,
) -> str:
    asked_ros = bool(params.get("restOfSeason") in {True, "true", 1, "1"} or params.get("type") == "ros")
    points = [item["fpts"] for item in parsed.values() if item.get("fpts")]
    skill = [
        item["fpts"]
        for item in parsed.values()
        if item.get("fpts") and str(item.get("position") or "").upper() in {"RB", "WR", "TE", "QB"}
    ]
    sample = skill or points
    try:
        week = int(response_week) if response_week is not None else None
    except (TypeError, ValueError):
        week = None
    if not sample:
        return "weekly"
    median = statistics.median(sample)
    if median >= 50:
        if asked_ros:
            return "ros"
        if week == 0:
            return "season"
        return "ros"
    if asked_ros and median >= 40:
        return "ros"
    return "weekly"


def fetch_nfl_projections(
    api_key: str,
    season: int,
    *,
    scoring: str = "PPR",
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    """Try ROS, then season-long week=0. Fail soft if the key is missing or rejected."""
    if not api_key:
        return {"ok": False, "error": "missing_api_key", "players": {}, "scope": None, "params": None}
    getter = http_get or requests.get
    scoring = (scoring or "PPR").upper()
    if scoring in {"HALF_PPR", "HALF-PPR"}:
        scoring = "HALF"
    attempts = [
        {"restOfSeason": "true", "scoring": scoring, "positions": DEFAULT_POSITIONS},
        {"type": "ros", "scoring": scoring, "positions": DEFAULT_POSITIONS},
        {"week": 0, "scoring": scoring, "positions": DEFAULT_POSITIONS},
    ]
    last_error = None
    for base in (BASE_URL, ALT_BASE_URL):
        for params in attempts:
            try:
                response = getter(
                    f"{base}/nfl/{season}/projections",
                    headers={"x-api-key": api_key},
                    params=params,
                    timeout=30,
                )
            except Exception as exc:  # noqa: BLE001 - optional overlay
                last_error = str(exc)
                continue
            status = getattr(response, "status_code", None)
            if status != 200:
                last_error = f"http_{status}"
                continue
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                continue
            if not isinstance(payload, dict):
                last_error = "unexpected_payload"
                continue
            parsed = parse_players(payload, scoring=scoring)
            if not parsed:
                last_error = "empty_players"
                continue
            scope = classify_scope(parsed, params=params, response_week=payload.get("week"))
            return {
                "ok": True,
                "error": None,
                "players": parsed,
                "scope": scope,
                "params": params,
                "count": len(parsed),
            }
    return {"ok": False, "error": last_error or "unavailable", "players": {}, "scope": None, "params": None}


def attach_fantasypros(
    espn_players: list[dict[str, Any]],
    *,
    api_key: str | None,
    season: int,
    scoring: str = "PPR",
    http_get: HttpGet | None = None,
    fetched: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = fetched if fetched is not None else fetch_nfl_projections(
        api_key or "",
        season,
        scoring=scoring,
        http_get=http_get,
    )
    parsed = payload.get("players") or {}
    scope = payload.get("scope") or "weekly"
    enriched = []
    for player in espn_players:
        row = dict(player)
        match = parsed.get(normalize_name(str(player.get("name") or "")))
        if not match:
            enriched.append(row)
            continue
        fpts = float(match["fpts"])
        row["fantasypros_fpid"] = match.get("fpid")
        row["fantasypros_scope"] = scope
        if scope == "ros":
            row["fantasypros_ros_points"] = round(fpts, 2)
        elif scope == "season":
            scored = 0.0
            try:
                scored = float(player.get("points") or 0.0)
            except (TypeError, ValueError):
                scored = 0.0
            remaining = fpts - scored
            if remaining > 0:
                row["fantasypros_ros_points"] = round(remaining, 2)
            else:
                row["fantasypros_weekly_points"] = round(fpts, 2)
        else:
            row["fantasypros_weekly_points"] = round(fpts, 2)
        enriched.append(row)
    return enriched
