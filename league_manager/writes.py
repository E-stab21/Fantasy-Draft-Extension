"""Unofficial ESPN fantasy write payloads with a preview-first safety gate.

ESPN does not document write endpoints. These shapes match community-verified
requests used by the ESPN site (`lm-api-writes.fantasy.espn.com`). Payloads can
change without notice. Live posts require ESPN_WRITES_ENABLED=true,
ESPN_DRY_RUN=false, and an explicit --confirm flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from league_manager.config import Settings

WRITE_BASE = "https://lm-api-writes.fantasy.espn.com/apis/v3/games"


class WriteBlocked(RuntimeError):
    """A write was requested but safety gates are closed."""


@dataclass
class WriteResult:
    executed: bool
    dry_run: bool
    status_code: int | None
    message: str
    payload: dict[str, Any]
    response: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "executed": self.executed,
            "dry_run": self.dry_run,
            "status_code": self.status_code,
            "message": self.message,
            "payload": self.payload,
            "response": self.response,
        }
        data.update(self.extra)
        return data


def lineup_payload(
    *,
    team_id: int,
    swid: str,
    scoring_period_id: int,
    moves: list[dict[str, int]],
) -> dict[str, Any]:
    items = []
    for move in moves:
        items.append(
            {
                "playerId": int(move["player_id"]),
                "type": "LINEUP",
                "fromLineupSlotId": int(move["from_slot"]),
                "toLineupSlotId": int(move["to_slot"]),
            }
        )
    return {
        "isLeagueManager": False,
        "teamId": int(team_id),
        "type": "ROSTER",
        "memberId": swid,
        "scoringPeriodId": int(scoring_period_id),
        "executionType": "EXECUTE",
        "items": items,
    }


def add_drop_payload(
    *,
    team_id: int,
    swid: str,
    scoring_period_id: int,
    add_player_id: int | None = None,
    drop_player_id: int | None = None,
    waiver: bool = False,
    bid_amount: int = 0,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if add_player_id is not None:
        items.append(
            {
                "playerId": int(add_player_id),
                "type": "ADD",
                "toTeamId": int(team_id),
            }
        )
    if drop_player_id is not None:
        items.append(
            {
                "playerId": int(drop_player_id),
                "type": "DROP",
                "fromTeamId": int(team_id),
            }
        )
    if not items:
        raise ValueError("Need at least one of add_player_id or drop_player_id")
    payload: dict[str, Any] = {
        "isLeagueManager": False,
        "teamId": int(team_id),
        "type": "WAIVER" if waiver else "FREEAGENT",
        "memberId": swid,
        "scoringPeriodId": int(scoring_period_id),
        "executionType": "EXECUTE",
        "items": items,
    }
    if waiver:
        payload["bidAmount"] = int(bid_amount)
    return payload


def trade_payload(
    *,
    team_id: int,
    receiving_team_id: int,
    swid: str,
    scoring_period_id: int,
    send_player_ids: list[int],
    receive_player_ids: list[int],
    comment: str = "",
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for player_id in send_player_ids:
        items.append(
            {
                "playerId": int(player_id),
                "type": "TRADE",
                "fromTeamId": int(team_id),
                "toTeamId": int(receiving_team_id),
            }
        )
    for player_id in receive_player_ids:
        items.append(
            {
                "playerId": int(player_id),
                "type": "TRADE",
                "fromTeamId": int(receiving_team_id),
                "toTeamId": int(team_id),
            }
        )
    return {
        "isLeagueManager": False,
        "teamId": int(team_id),
        "type": "TRADE_PROPOSAL",
        "memberId": swid,
        "scoringPeriodId": int(scoring_period_id),
        "executionType": "EXECUTE",
        "items": items,
        "comment": comment,
    }


def transaction_url(settings: Settings) -> str:
    return (
        f"{WRITE_BASE}/{settings.espn_sport_code}/seasons/{settings.season}"
        f"/segments/0/leagues/{settings.league_id}/transactions/"
    )


def post_transaction(
    *,
    settings: Settings,
    payload: dict[str, Any],
    confirm: bool,
    scoring_period_id: int,
    http_post=None,
) -> WriteResult:
    url = transaction_url(settings)
    if not confirm:
        return WriteResult(
            executed=False,
            dry_run=True,
            status_code=None,
            message="Preview only. Re-run with --confirm to attempt the write.",
            payload=payload,
            extra={"url": url, "scoring_period_id": scoring_period_id},
        )
    if not settings.writes_enabled or settings.dry_run:
        return WriteResult(
            executed=False,
            dry_run=True,
            status_code=None,
            message=(
                "Confirm received, but writes are gated. Set ESPN_WRITES_ENABLED=true "
                "and ESPN_DRY_RUN=false to send this to ESPN."
            ),
            payload=payload,
            extra={"url": url, "scoring_period_id": scoring_period_id},
        )

    poster = http_post or requests.post
    response = poster(
        url,
        params={"scoringPeriodId": scoring_period_id},
        json=payload,
        cookies=settings.cookies,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text
    ok = 200 <= response.status_code < 300
    return WriteResult(
        executed=ok,
        dry_run=False,
        status_code=response.status_code,
        message="ESPN accepted the transaction." if ok else "ESPN rejected the transaction.",
        payload=payload,
        response=body,
        extra={"url": url, "scoring_period_id": scoring_period_id},
    )
