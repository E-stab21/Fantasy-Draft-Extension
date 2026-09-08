"""Grade redraft trades using short-term and rest-of-season surplus."""

from __future__ import annotations

from typing import Any

from league_manager.value import (
    LeagueContext,
    PlayerValue,
    infer_window,
    value_player,
    window_weights,
)


def _lookup(players: dict[Any, dict[str, Any]], player_id: int) -> dict[str, Any]:
    if player_id in players:
        return players[player_id]
    for key, player in players.items():
        if str(key) == str(player_id) or str(player.get("id")) == str(player_id):
            return player
    raise KeyError(f"Player {player_id} is not on any roster or the free-agent sample")


def concentration_penalty(send: list[PlayerValue], recv: list[PlayerValue]) -> float:
    """Stud tax: one elite starter is worth more than several mid pieces."""
    if not send or not recv:
        return 0.0
    send_best = max(item.lt_vorp for item in send)
    recv_best = max(item.lt_vorp for item in recv)
    if len(recv) > len(send) and send_best > 1.4 * max(recv_best, 0.01):
        return round(0.18 * send_best, 2)
    if len(send) > len(recv) and recv_best > 1.4 * max(send_best, 0.01):
        return round(-0.08 * recv_best, 2)
    return 0.0


def lineup_hole_penalty(send: list[dict[str, Any]], recv: list[dict[str, Any]]) -> tuple[float, list[str]]:
    notes = []
    penalty = 0.0
    recv_positions = {str(player.get("position") or "") for player in recv}
    for player in send:
        if not player.get("is_starter"):
            continue
        pos = str(player.get("position") or "")
        if pos and pos not in recv_positions:
            penalty += 0.2 * max(float(player.get("weekly_rate") or player.get("projected_points") or 0.0), 0.0)
            notes.append(f"Leaves a starting hole at {pos} ({player.get('name')})")
    return round(penalty, 2), notes


def letter_grade(blended: float) -> str:
    if blended >= 12:
        return "A+"
    if blended >= 8:
        return "A"
    if blended >= 4:
        return "B+"
    if blended >= 1.5:
        return "B"
    if blended >= -1.5:
        return "C"
    if blended >= -4:
        return "C-"
    if blended >= -8:
        return "D"
    return "F"


def verdict(blended: float) -> str:
    if blended >= 4:
        return "accept"
    if blended >= 1.5:
        return "lean_accept"
    if blended >= -1.5:
        return "even"
    if blended >= -4:
        return "lean_reject"
    return "reject"


def grade_valued_trade(
    *,
    send_values: list[PlayerValue],
    recv_values: list[PlayerValue],
    send_players: list[dict[str, Any]],
    recv_players: list[dict[str, Any]],
    context: LeagueContext,
    window: str,
) -> dict[str, Any]:
    st_w, lt_w = window_weights(window)
    send_st = sum(item.st_vorp for item in send_values)
    send_lt = sum(item.lt_vorp for item in send_values)
    recv_st = sum(item.st_vorp for item in recv_values)
    recv_lt = sum(item.lt_vorp for item in recv_values)
    delta_st = recv_st - send_st
    delta_lt = recv_lt - send_lt
    stud_tax = concentration_penalty(send_values, recv_values)
    hole_penalty, hole_notes = lineup_hole_penalty(send_players, recv_players)
    blended = st_w * delta_st + lt_w * delta_lt - stud_tax - hole_penalty
    notes = [
        f"Redraft window is {window} (ST weight {st_w:.0%}, LT weight {lt_w:.0%}).",
        "ST is the next few weeks; LT is rest of this season including playoffs.",
    ]
    if stud_tax > 0:
        notes.append("Stud tax applied: you are breaking up an elite piece for depth.")
    if stud_tax < 0:
        notes.append("Consolidation bonus: you are turning depth into a locked starter.")
    notes.extend(hole_notes)
    if context.current_week >= context.regular_season_end:
        notes.append("Regular season is over or nearly over; playoff schedule dominates.")
    return {
        "window": window,
        "weights": {"st": st_w, "lt": lt_w},
        "grade": letter_grade(blended),
        "verdict": verdict(blended),
        "blended": round(blended, 2),
        "delta_st": round(delta_st, 2),
        "delta_lt": round(delta_lt, 2),
        "stud_tax": stud_tax,
        "lineup_hole_penalty": hole_penalty,
        "send": [item.to_dict() for item in send_values],
        "receive": [item.to_dict() for item in recv_values],
        "send_totals": {"st_vorp": round(send_st, 2), "lt_vorp": round(send_lt, 2)},
        "receive_totals": {"st_vorp": round(recv_st, 2), "lt_vorp": round(recv_lt, 2)},
        "notes": notes,
        "summary": _summary(window, delta_st, delta_lt, blended),
    }


def grade_trade(
    *,
    send_ids: list[int],
    receive_ids: list[int],
    players: dict[Any, dict[str, Any]],
    context: LeagueContext,
    baselines: dict[str, float],
    window: str | None = None,
) -> dict[str, Any]:
    if not send_ids or not receive_ids:
        raise ValueError("Trade grade needs at least one send id and one receive id")
    send_players = [_lookup(players, player_id) for player_id in send_ids]
    recv_players = [_lookup(players, player_id) for player_id in receive_ids]
    resolved_window = infer_window(context, window)
    send_values = [value_player(player, context, baselines, window=resolved_window) for player in send_players]
    recv_values = [value_player(player, context, baselines, window=resolved_window) for player in recv_players]
    return grade_valued_trade(
        send_values=send_values,
        recv_values=recv_values,
        send_players=send_players,
        recv_players=recv_players,
        context=context,
        window=resolved_window,
    )


def _summary(window: str, delta_st: float, delta_lt: float, blended: float) -> str:
    st_dir = "gain" if delta_st >= 0 else "lose"
    lt_dir = "gain" if delta_lt >= 0 else "lose"
    return (
        f"As a {window} you {st_dir} {abs(delta_st):.1f} short-term VORP and "
        f"{lt_dir} {abs(delta_lt):.1f} rest-of-season VORP "
        f"(blended {blended:+.1f})."
    )
