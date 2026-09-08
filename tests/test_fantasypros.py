from league_manager.fantasypros import attach_fantasypros, classify_scope, parse_players
from league_manager.projections import attach_sleeper_ros
from league_manager.sleeper import as_projection_map, remaining_week_totals


def test_parse_and_classify_season_totals():
    payload = {
        "week": "0",
        "players": [
            {
                "fpid": 1,
                "name": "Bijan Robinson",
                "position_id": "RB",
                "stats": {"points": 220, "points_ppr": 260},
            },
            {
                "fpid": 2,
                "name": "Ja'Marr Chase",
                "position_id": "WR",
                "stats": {"points_ppr": 240},
            },
        ],
    }
    parsed = parse_players(payload, scoring="PPR")
    assert parsed["bijanrobinson"]["fpts"] == 260
    assert classify_scope(parsed, params={"week": 0}, response_week="0") == "season"


def test_attach_subtracts_scored_from_season_totals():
    fetched = {
        "ok": True,
        "scope": "season",
        "players": {
            "bijanrobinson": {"name": "Bijan Robinson", "fpid": 1, "fpts": 260, "position": "RB"}
        },
    }
    rows = attach_fantasypros(
        [{"id": 9, "name": "Bijan Robinson", "points": 80}],
        api_key="unused",
        season=2026,
        fetched=fetched,
    )
    assert rows[0]["fantasypros_ros_points"] == 180


def test_attach_ros_does_not_subtract_again():
    fetched = {
        "ok": True,
        "scope": "ros",
        "players": {
            "bijanrobinson": {"name": "Bijan Robinson", "fpid": 1, "fpts": 140, "position": "RB"}
        },
    }
    rows = attach_fantasypros(
        [{"id": 9, "name": "Bijan Robinson", "points": 80}],
        api_key="unused",
        season=2026,
        fetched=fetched,
    )
    assert rows[0]["fantasypros_ros_points"] == 140


def test_sleeper_remaining_weeks_sum():
    week_maps = {
        10: [{"player_id": "4016", "stats": {"pts_ppr": 20}}],
        11: [{"player_id": "4016", "stats": {"pts_ppr": 0}}],
        12: [{"player_id": "4016", "stats": {"pts_ppr": 18}}],
    }
    totals = remaining_week_totals(2026, 10, 12, week_maps=week_maps)
    assert totals["4016"] == 38
    assert as_projection_map(week_maps[10])["4016"]["stats"]["pts_ppr"] == 20

    rows = attach_sleeper_ros(
        [{"id": 1, "name": "Ja'Marr Chase", "sleeper_id": "4016"}],
        season=2026,
        current_week=10,
        through=12,
        week_maps=week_maps,
    )
    assert rows[0]["sleeper_ros_points"] == 38
