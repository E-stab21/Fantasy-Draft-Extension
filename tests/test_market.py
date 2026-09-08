from league_manager.market import find_opportunities, recent_games, recency_gap
from league_manager.value import LeagueContext, value_player


def test_recent_games_skip_bye_and_score_miss():
    player = {
        "id": 1,
        "projected_points": 16,
        "bye_week": 2,
        "weekly_stats": {
            1: {"points": 8, "projected_points": 16},
            2: {"points": 0, "projected_points": 0},
            3: {"points": 7, "projected_points": 15},
        },
    }
    games = recent_games(player, current_week=4, lookback=3)
    assert [game["week"] for game in games] == [1, 3]
    recency = recency_gap(player, games)
    assert recency["games"] == 2
    assert recency["recent_ppg"] == 7.5
    assert recency["gap_vs_weekly_proj"] == -8.0


def test_buy_low_on_other_roster_sell_high_on_ours():
    context = LeagueContext(current_week=4, season_end_week=17, wins=5, losses=2, standing=3)
    baselines = {"RB": 8.0, "WR": 8.0}
    ours = {
        "id": 10,
        "name": "Heater",
        "position": "RB",
        "projected_points": 14,
        "team_id": 1,
        "team_name": "Us",
        "weekly_stats": {
            1: {"points": 24, "projected_points": 14},
            2: {"points": 22, "projected_points": 14},
            3: {"points": 26, "projected_points": 14},
        },
    }
    theirs = {
        "id": 20,
        "name": "Cold",
        "position": "WR",
        "projected_points": 16,
        "team_id": 2,
        "team_name": "Them",
        "weekly_stats": {
            1: {"points": 6, "projected_points": 16},
            2: {"points": 5, "projected_points": 15},
            3: {"points": 7, "projected_points": 16},
        },
    }
    valued = {
        10: value_player(ours, context, baselines, window="contender"),
        20: value_player(theirs, context, baselines, window="contender"),
    }
    found = find_opportunities(
        [ours, theirs],
        valued,
        our_team_id=1,
        current_week=4,
        lookback=3,
    )
    assert found["sell_high"][0]["id"] == 10
    assert found["buy_low"][0]["id"] == 20
    assert found["buy_low"][0]["suggested_sends"][0]["id"] == 10


def test_injured_star_is_buy_low_without_recent_games():
    context = LeagueContext(current_week=2, season_end_week=17, wins=1, losses=0, standing=2)
    baselines = {"RB": 4.0}
    player = {
        "id": 30,
        "name": "IR Back",
        "position": "RB",
        "projected_points": 18,
        "injury_status": "IR",
        "team_id": 9,
        "weekly_stats": {},
    }
    valued = {30: value_player(player, context, baselines, window="contender")}
    found = find_opportunities([player], valued, our_team_id=1, current_week=2, lookback=3)
    assert found["buy_low"][0]["id"] == 30
    assert any("IR" in reason for reason in found["buy_low"][0]["reasons"])
