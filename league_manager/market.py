"""Find buy-low / sell-high spots from recency bias vs our assigned value.

Other managers tend to anchor on the last few games. Our value uses ESPN's
forward projection (usage and form already inside it) plus ST/LT VORP.
A cold stretch against that projection is a buy-low; a heater is a sell-high.
We do not blend snap share or last-3 averages into the projection again.
"""

from __future__ import annotations

from typing import Any

from league_manager.value import INJURY_ST_FACTOR, PlayerValue, weekly_rate

DEFAULT_LOOKBACK = 3
BUY_GAP = -3.0
SELL_GAP = 4.0
MIN_BUY_LT_VORP = 2.0


def _week_entry(weekly: dict[Any, Any], week: int) -> dict[str, Any] | None:
    entry = weekly.get(week)
    if entry is None:
        entry = weekly.get(str(week))
    return entry if isinstance(entry, dict) else None


def recent_games(
    player: dict[str, Any],
    *,
    current_week: int,
    lookback: int = DEFAULT_LOOKBACK,
) -> list[dict[str, Any]]:
    weekly = player.get("weekly_stats") or {}
    bye = player.get("bye_week")
    games = []
    start = max(1, int(current_week) - int(lookback))
    for week in range(start, int(current_week)):
        if bye is not None and int(week) == int(bye):
            continue
        entry = _week_entry(weekly, week)
        if not entry:
            continue
        actual = entry.get("points")
        projected = entry.get("projected_points")
        if actual is None:
            continue
        try:
            actual_f = float(actual)
        except (TypeError, ValueError):
            continue
        projected_f = None
        if projected is not None:
            try:
                projected_f = float(projected)
            except (TypeError, ValueError):
                projected_f = None
        # Bye/inactive: no projection and no points.
        if actual_f == 0 and not projected_f:
            continue
        games.append(
            {
                "week": week,
                "points": actual_f,
                "projected_points": projected_f,
                "miss": None if projected_f is None else round(actual_f - projected_f, 2),
            }
        )
    return games


def recency_gap(player: dict[str, Any], games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {
            "games": 0,
            "recent_ppg": None,
            "expected_ppg": weekly_rate(player),
            "gap_vs_expected": None,
            "gap_vs_weekly_proj": None,
        }
    recent_ppg = sum(game["points"] for game in games) / len(games)
    expected = weekly_rate(player)
    misses = [game["miss"] for game in games if game.get("miss") is not None]
    vs_proj = sum(misses) / len(misses) if misses else None
    return {
        "games": len(games),
        "recent_ppg": round(recent_ppg, 2),
        "expected_ppg": round(expected, 2),
        "gap_vs_expected": round(recent_ppg - expected, 2),
        "gap_vs_weekly_proj": None if vs_proj is None else round(vs_proj, 2),
    }


def _anchor_gap(recency: dict[str, Any]) -> float | None:
    """How far recent scoring sits from what managers likely expected."""
    if recency.get("gap_vs_weekly_proj") is not None:
        return float(recency["gap_vs_weekly_proj"])
    if recency.get("gap_vs_expected") is not None:
        return float(recency["gap_vs_expected"])
    return None


def _injury_buy(player: dict[str, Any], valued: PlayerValue) -> bool:
    status = str(player.get("injury_status") or "").upper()
    if player.get("injured") or status in INJURY_ST_FACTOR:
        return valued.lt_vorp >= MIN_BUY_LT_VORP
    return False


def find_opportunities(
    players: list[dict[str, Any]],
    valued: dict[Any, PlayerValue],
    *,
    our_team_id: Any,
    current_week: int,
    lookback: int = DEFAULT_LOOKBACK,
    limit: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    buy: list[dict[str, Any]] = []
    sell: list[dict[str, Any]] = []
    for player in players:
        player_id = player.get("id")
        value = valued.get(player_id)
        if value is None:
            continue
        games = recent_games(player, current_week=current_week, lookback=lookback)
        recency = recency_gap(player, games)
        gap = _anchor_gap(recency)
        on_ours = player.get("team_id") == our_team_id
        injury_buy = _injury_buy(player, value)
        cold = gap is not None and gap <= BUY_GAP and value.lt_vorp >= MIN_BUY_LT_VORP
        hot = gap is not None and gap >= SELL_GAP
        if (cold or injury_buy) and not on_ours:
            reasons = []
            if cold:
                reasons.append(
                    f"Last {recency['games']} games averaged {recency['recent_ppg']} "
                    f"vs {recency['expected_ppg']} expected ({gap:+.1f})."
                )
            if injury_buy:
                reasons.append(
                    f"{player.get('injury_status') or 'injured'}; ROS VORP still {value.lt_vorp}."
                )
            buy.append(
                _row(player, value, recency, "buy_low", reasons, gap if gap is not None else -abs(value.lt_vorp))
            )
        if hot and on_ours:
            reasons = [
                f"Last {recency['games']} games averaged {recency['recent_ppg']} "
                f"vs {recency['expected_ppg']} expected ({gap:+.1f})."
            ]
            sell.append(_row(player, value, recency, "sell_high", reasons, gap))

    buy.sort(key=lambda row: (row["gap"] if row["gap"] is not None else 0, -row["lt_vorp"]))
    sell.sort(key=lambda row: (-(row["gap"] or 0), -row["lt_vorp"]))
    buy = buy[:limit]
    sell = sell[:limit]
    for item in buy:
        item["suggested_sends"] = _suggested_sends(item, sell)
    return {
        "buy_low": buy,
        "sell_high": sell,
        "notes": [
            "Buy-low: other managers likely anchoring on a cold stretch or injury; our ROS value is still positive.",
            "Sell-high: our player is on a heater versus the weekly projection other managers saw.",
            "Forward value still uses ESPN projections (usage already inside). Recency is only the market signal.",
        ],
    }


def _row(
    player: dict[str, Any],
    value: PlayerValue,
    recency: dict[str, Any],
    kind: str,
    reasons: list[str],
    gap: float | None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": player.get("id"),
        "name": player.get("name"),
        "position": value.position,
        "team_id": player.get("team_id"),
        "team_name": player.get("team_name"),
        "st_vorp": value.st_vorp,
        "lt_vorp": value.lt_vorp,
        "blended": value.blended,
        "weekly_rate": value.weekly_rate,
        "injury_status": player.get("injury_status"),
        "gap": None if gap is None else round(float(gap), 2),
        "recency": recency,
        "reasons": reasons,
    }


def _suggested_sends(buy: dict[str, Any], sell_highs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair a buy-low with our closest sell-high by blended value."""
    target = float(buy.get("blended") or 0.0)
    ranked = sorted(sell_highs, key=lambda item: abs(float(item.get("blended") or 0.0) - target))
    suggestions = []
    for item in ranked[:2]:
        suggestions.append(
            {
                "id": item["id"],
                "name": item["name"],
                "blended": item["blended"],
                "note": (
                    f"Similar blended value ({item['blended']} vs {buy['blended']}). "
                    "Grade with trade-grade before offering."
                ),
            }
        )
    return suggestions
