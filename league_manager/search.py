"""Enumerate 1-for-1, 2-for-1, and 1-for-2 redraft trades.

Our surplus uses the ROS VORP stack. Their acceptance check uses ESPN face
value (this week's ESPN projection flattened over remaining games) — the
number other managers are most likely anchoring on.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import Any, Iterable

from league_manager.slots import normalize_position
from league_manager.trades import grade_valued_trade
from league_manager.value import (
    LeagueContext,
    PlayerValue,
    espn_face_value,
    infer_window,
    value_player,
    weekly_rate,
)

DEFAULT_KINDS = ("1:1", "2:1", "1:2")
SKIP_POSITIONS = {"K", "D/ST", "DST", "DEF", "PK"}
MIN_WEEKLY = 5.0
MAX_PER_SIDE = 12
MIN_SURPLUS = 1.0
MIN_THEIR_FACE = -3.5
MAX_THEIR_FACE = 10.0
MAX_PER_OPPONENT = 8


def parse_kinds(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_KINDS
    allowed = set(DEFAULT_KINDS)
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    bad = [part for part in parts if part not in allowed]
    if bad:
        raise ValueError(f"Unknown trade kinds {bad}. Use 1:1, 2:1, 1:2.")
    return parts or DEFAULT_KINDS


def _candidates(
    roster: list[dict[str, Any]],
    valued: dict[Any, PlayerValue],
    *,
    max_players: int = MAX_PER_SIDE,
    min_weekly: float = MIN_WEEKLY,
) -> list[dict[str, Any]]:
    rows = []
    for player in roster:
        player_id = player.get("id")
        if player_id is None or player_id not in valued:
            continue
        pos = normalize_position(str(player.get("position") or ""))
        if pos in SKIP_POSITIONS:
            continue
        value = valued[player_id]
        rate = value.weekly_rate or weekly_rate(player)
        if rate < min_weekly and not player.get("is_starter") and value.lt_vorp < 2:
            continue
        rows.append(player)
    rows.sort(key=lambda item: valued[item["id"]].blended, reverse=True)
    return rows[: max(1, int(max_players))]


def _side_summary(players: list[dict[str, Any]], valued: dict[Any, PlayerValue]) -> list[dict[str, Any]]:
    rows = []
    for player in players:
        value = valued[player["id"]]
        rows.append(
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "position": value.position,
                "blended": value.blended,
                "lt_vorp": value.lt_vorp,
                "ros_source": value.ros_source,
            }
        )
    return rows


def _package_score(blended: float, their_face_net: float) -> float:
    if -2.0 <= their_face_net <= 4.0:
        fairness = 3.0 - abs(their_face_net) * 0.4
    else:
        fairness = -abs(their_face_net) * 0.15
    return blended * 1.4 + fairness


def _why(grade: dict[str, Any], their_face_net: float, send: list[dict], recv: list[dict]) -> str:
    send_names = ", ".join(str(player.get("name")) for player in send)
    recv_names = ", ".join(str(player.get("name")) for player in recv)
    return (
        f"Send {send_names} for {recv_names}. We {grade['summary']} "
        f"ESPN face for them is {their_face_net:+.1f} remaining projected points."
    )


def search_trades(
    *,
    our_team_id: Any,
    teams: list[dict[str, Any]],
    players: dict[Any, dict[str, Any]],
    context: LeagueContext,
    baselines: dict[str, float],
    window: str | None = None,
    kinds: Iterable[str] = DEFAULT_KINDS,
    limit: int = 40,
    min_surplus: float = MIN_SURPLUS,
    min_their_face: float = MIN_THEIR_FACE,
    max_their_face: float = MAX_THEIR_FACE,
    max_players_per_side: int = MAX_PER_SIDE,
    with_team_id: Any | None = None,
    max_per_opponent: int = MAX_PER_OPPONENT,
) -> dict[str, Any]:
    resolved = infer_window(context, window)
    valued = {
        player_id: value_player(player, context, baselines, window=resolved)
        for player_id, player in players.items()
    }
    faces = {player_id: espn_face_value(player, context) for player_id, player in players.items()}
    kind_set = tuple(kinds) or DEFAULT_KINDS
    our_team = next((team for team in teams if team.get("id") == our_team_id), None)
    if our_team is None:
        raise ValueError(f"No team with id {our_team_id}")
    our_players = _candidates(our_team.get("roster") or [], valued, max_players=max_players_per_side)
    considered = 0
    kept: list[dict[str, Any]] = []

    def consider(kind: str, other: dict[str, Any], send: list[dict[str, Any]], recv: list[dict[str, Any]]) -> None:
        nonlocal considered
        considered += 1
        send_values = [valued[player["id"]] for player in send]
        recv_values = [valued[player["id"]] for player in recv]
        grade = grade_valued_trade(
            send_values=send_values,
            recv_values=recv_values,
            send_players=send,
            recv_players=recv,
            context=context,
            window=resolved,
        )
        their_face_net = sum(faces[player["id"]] for player in send) - sum(
            faces[player["id"]] for player in recv
        )
        if grade["blended"] < min_surplus:
            return
        if their_face_net < min_their_face or their_face_net > max_their_face:
            return
        score = _package_score(grade["blended"], their_face_net)
        kept.append(
            {
                "kind": kind,
                "with_team": {"id": other.get("id"), "name": other.get("name")},
                "send": _side_summary(send, valued),
                "receive": _side_summary(recv, valued),
                "send_ids": [player["id"] for player in send],
                "receive_ids": [player["id"] for player in recv],
                "grade": grade["grade"],
                "verdict": grade["verdict"],
                "blended": grade["blended"],
                "delta_st": grade["delta_st"],
                "delta_lt": grade["delta_lt"],
                "stud_tax": grade["stud_tax"],
                "lineup_hole_penalty": grade["lineup_hole_penalty"],
                "their_espn_face_net": round(their_face_net, 2),
                "score": round(score, 2),
                "why": _why(grade, their_face_net, send, recv),
            }
        )

    opponents = [
        team
        for team in teams
        if team.get("id") != our_team_id and (with_team_id is None or team.get("id") == with_team_id)
    ]
    for other in opponents:
        theirs = _candidates(other.get("roster") or [], valued, max_players=max_players_per_side)
        if not theirs:
            continue
        if "1:1" in kind_set:
            for send_player, recv_player in product(our_players, theirs):
                consider("1:1", other, [send_player], [recv_player])
        if "2:1" in kind_set and len(our_players) >= 2:
            for send_pair, recv_player in product(combinations(our_players, 2), theirs):
                consider("2:1", other, list(send_pair), [recv_player])
        if "1:2" in kind_set and len(theirs) >= 2:
            for send_player, recv_pair in product(our_players, combinations(theirs, 2)):
                consider("1:2", other, [send_player], list(recv_pair))

    kept.sort(key=lambda item: item["score"], reverse=True)
    picked: list[dict[str, Any]] = []
    per_team: dict[Any, int] = {}
    for row in kept:
        team_id = row["with_team"]["id"]
        if per_team.get(team_id, 0) >= max_per_opponent and len(picked) >= max(limit // 2, 1):
            continue
        picked.append(row)
        per_team[team_id] = per_team.get(team_id, 0) + 1
        if len(picked) >= limit:
            break
    return {
        "window": resolved,
        "kinds": list(kind_set),
        "considered": considered,
        "kept": len(kept),
        "returned": len(picked),
        "filters": {
            "min_surplus": min_surplus,
            "min_their_espn_face": min_their_face,
            "max_their_espn_face": max_their_face,
        },
        "trades": picked,
    }
