from league_manager.config import Settings
from league_manager.writes import (
    add_drop_payload,
    lineup_payload,
    post_transaction,
    trade_payload,
    transaction_url,
)


def _settings(**overrides) -> Settings:
    data = dict(
        league_id=99,
        espn_s2="s2",
        swid="{SWID}",
        season=2026,
        sport="nfl",
        writes_enabled=False,
        dry_run=True,
    )
    data.update(overrides)
    return Settings(**data)


def test_lineup_and_waiver_payloads():
    lineup = lineup_payload(
        team_id=4,
        swid="{SWID}",
        scoring_period_id=2,
        moves=[{"player_id": 10, "from_slot": 20, "to_slot": 2}],
    )
    assert lineup["type"] == "ROSTER"
    assert lineup["items"][0]["type"] == "LINEUP"
    assert lineup["items"][0]["toLineupSlotId"] == 2

    claim = add_drop_payload(
        team_id=4,
        swid="{SWID}",
        scoring_period_id=2,
        add_player_id=11,
        drop_player_id=12,
        waiver=True,
        bid_amount=7,
    )
    assert claim["type"] == "WAIVER"
    assert claim["bidAmount"] == 7
    assert {item["type"] for item in claim["items"]} == {"ADD", "DROP"}


def test_trade_payload_swaps_teams():
    payload = trade_payload(
        team_id=1,
        receiving_team_id=8,
        swid="{SWID}",
        scoring_period_id=3,
        send_player_ids=[100],
        receive_player_ids=[200],
        comment="need a TE",
    )
    assert payload["type"] == "TRADE_PROPOSAL"
    send = payload["items"][0]
    recv = payload["items"][1]
    assert send["fromTeamId"] == 1 and send["toTeamId"] == 8
    assert recv["fromTeamId"] == 8 and recv["toTeamId"] == 1


def test_preview_does_not_post():
    calls = []
    result = post_transaction(
        settings=_settings(),
        payload={"type": "ROSTER"},
        confirm=False,
        scoring_period_id=1,
        http_post=lambda *args, **kwargs: calls.append((args, kwargs)) or None,
    )
    assert result.executed is False
    assert "Preview only" in result.message
    assert calls == []


def test_confirm_still_gated_without_write_flags():
    calls = []
    result = post_transaction(
        settings=_settings(writes_enabled=True, dry_run=True),
        payload={"type": "FREEAGENT"},
        confirm=True,
        scoring_period_id=1,
        http_post=lambda *args, **kwargs: calls.append(1),
    )
    assert result.executed is False
    assert "gated" in result.message
    assert calls == []


def test_live_write_posts_when_gates_open():
    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True}

    def fake_post(url, **kwargs):
        assert "lm-api-writes.fantasy.espn.com" in url
        assert kwargs["cookies"]["espn_s2"] == "s2"
        return FakeResp()

    result = post_transaction(
        settings=_settings(writes_enabled=True, dry_run=False),
        payload={"type": "ROSTER"},
        confirm=True,
        scoring_period_id=4,
        http_post=fake_post,
    )
    assert result.executed is True
    assert result.status_code == 200
    assert transaction_url(_settings()).endswith("/leagues/99/transactions/")
