from league_manager.value import (
    LeagueContext,
    infer_window,
    replacement_baselines,
    value_player,
    weekly_rate,
)


def _ctx(**overrides) -> LeagueContext:
    data = dict(
        current_week=10,
        season_end_week=17,
        regular_season_end=14,
        playoff_team_count=4,
        team_count=10,
        short_term_weeks=3,
        wins=6,
        losses=3,
        standing=3,
    )
    data.update(overrides)
    return LeagueContext(**data)


def test_window_from_record():
    assert infer_window(_ctx(standing=1, wins=7, losses=2)) == "contender"
    assert infer_window(_ctx(standing=5, wins=5, losses=4, playoff_team_count=4)) == "bubble"
    assert infer_window(_ctx(standing=9, wins=2, losses=7, playoff_team_count=4)) == "rebuilder"
    assert infer_window(_ctx(), override="rebuilder") == "rebuilder"


def test_bye_and_injury_cut_short_term():
    baselines = {"RB": 8.0}
    healthy = value_player(
        {
            "id": 1,
            "name": "Workhorse",
            "position": "RB",
            "projected_points": 16,
            "bye_week": 11,
        },
        _ctx(),
        baselines,
        window="bubble",
    )
    assert healthy.st_games == 2  # weeks 10,12; 11 is bye
    assert healthy.lt_games == 7  # 10-17 minus bye
    assert healthy.st_vorp == round(16 * 2 - 8 * 2, 2)

    out = value_player(
        {
            "id": 2,
            "name": "Hurt",
            "position": "RB",
            "projected_points": 16,
            "injury_status": "OUT",
        },
        _ctx(),
        baselines,
        window="contender",
    )
    assert out.st_points == 0
    assert out.st_vorp < 0
    assert out.lt_points > 0


def test_replacement_uses_third_best_fa():
    agents = [
        {"position": "WR", "projected_points": 14},
        {"position": "WR", "projected_points": 12},
        {"position": "WR", "projected_points": 9},
        {"position": "WR", "projected_points": 4},
        {"position": "QB", "projected_points": 18},
    ]
    baselines = replacement_baselines(agents)
    assert baselines["WR"] == 9
    assert baselines["QB"] == 18
    assert weekly_rate({"projected_points": 0, "projected_avg_points": 11.5}) == 11.5
