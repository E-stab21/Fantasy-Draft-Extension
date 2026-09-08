"""Blend ESPN league-adjusted projections with public second sources.

Recommendation (see docs/PREDICTION_MODELS.md): do not train a custom model
first. Use ESPN projections as the primary source because they already apply
this league's scoring. Overlay Sleeper weekly projections when available.
"""

from __future__ import annotations

from typing import Any

from league_manager.sleeper import (
    as_projection_map,
    index_players_by_name,
    nfl_state,
    normalize_name,
    players as sleeper_players,
    projection_points,
    projections as sleeper_projections,
    remaining_week_totals,
)


def attach_sleeper_projections(
    espn_players: list[dict[str, Any]],
    *,
    season: int | None = None,
    week: int | None = None,
    scoring: str = "ppr",
    http_get=None,
    player_map: dict[str, Any] | None = None,
    projection_map: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if season is None or week is None:
        state = nfl_state(http_get=http_get)
        season = season or int(state.get("league_season") or state.get("season"))
        week = week or int(state.get("week") or state.get("display_week") or 1)
    if player_map is None:
        player_map = sleeper_players(http_get=http_get)
    if projection_map is None:
        projection_map = sleeper_projections(season, week, http_get=http_get)
    projection_map = as_projection_map(projection_map)
    by_name = index_players_by_name(player_map)
    enriched = []
    for player in espn_players:
        row = dict(player)
        sleeper = by_name.get(normalize_name(str(player.get("name") or "")))
        if sleeper:
            sleeper_id = sleeper.get("player_id")
            row["sleeper_id"] = sleeper_id
            row["sleeper_projected_points"] = projection_points(
                projection_map.get(str(sleeper_id), {}),
                scoring=scoring,
            )
            row["sleeper_injury_status"] = sleeper.get("injury_status")
        else:
            row["sleeper_projected_points"] = None
        enriched.append(row)
    return enriched


def attach_sleeper_ros(
    espn_players: list[dict[str, Any]],
    *,
    season: int | None = None,
    current_week: int | None = None,
    through: int = 17,
    scoring: str = "ppr",
    http_get=None,
    player_map: dict[str, Any] | None = None,
    week_maps: dict[int, Any] | None = None,
) -> list[dict[str, Any]]:
    """Sum Sleeper weekly projections for the remaining fantasy weeks."""
    players = espn_players
    if not any(player.get("sleeper_id") for player in players):
        players = attach_sleeper_projections(
            players,
            season=season,
            week=current_week,
            scoring=scoring,
            http_get=http_get,
            player_map=player_map,
        )
    if season is None or current_week is None:
        state = nfl_state(http_get=http_get)
        season = season or int(state.get("league_season") or state.get("season"))
        current_week = current_week or int(state.get("week") or state.get("display_week") or 1)
    totals = remaining_week_totals(
        int(season),
        int(current_week),
        through,
        scoring=scoring,
        http_get=http_get,
        week_maps=week_maps,
    )
    enriched = []
    for player in players:
        row = dict(player)
        sleeper_id = str(row.get("sleeper_id") or "")
        if sleeper_id and sleeper_id in totals:
            row["sleeper_ros_points"] = round(float(totals[sleeper_id]), 2)
        enriched.append(row)
    return enriched


def league_scoring(league: Any | None) -> str:
    raw = str(getattr(getattr(league, "settings", None), "scoring_type", "") or "ppr").lower()
    if "half" in raw:
        return "half"
    if raw in {"std", "standard", "non-ppr", "nonppr"}:
        return "std"
    return "ppr"


def primary_projection(player: dict[str, Any]) -> float:
    for key in ("projected_points", "sleeper_projected_points", "points"):
        value = player.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0
