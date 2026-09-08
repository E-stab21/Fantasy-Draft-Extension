from league_manager.trades import concentration_penalty, grade_trade, letter_grade
from league_manager.value import LeagueContext, PlayerValue


def _ctx(window_team="contender") -> LeagueContext:
    if window_team == "contender":
        return LeagueContext(
            current_week=10,
            season_end_week=17,
            wins=7,
            losses=2,
            standing=2,
            playoff_team_count=4,
            team_count=10,
        )
    return LeagueContext(
        current_week=10,
        season_end_week=17,
        wins=2,
        losses=7,
        standing=9,
        playoff_team_count=4,
        team_count=10,
    )


def _players() -> dict[int, dict]:
    return {
        1: {
            "id": 1,
            "name": "Stud RB",
            "position": "RB",
            "projected_points": 20,
            "is_starter": True,
        },
        2: {
            "id": 2,
            "name": "Mid WR",
            "position": "WR",
            "projected_points": 11,
            "is_starter": False,
        },
        3: {
            "id": 3,
            "name": "Streamer WR",
            "position": "WR",
            "projected_points": 10,
            "is_starter": False,
        },
        4: {
            "id": 4,
            "name": "WR1",
            "position": "WR",
            "projected_points": 19,
            "is_starter": True,
        },
        5: {
            "id": 5,
            "name": "RB1b",
            "position": "RB",
            "projected_points": 20,
            "is_starter": True,
        },
    }


def test_even_one_for_one_is_near_even():
    baselines = {"RB": 8.0, "WR": 8.0}
    result = grade_trade(
        send_ids=[1],
        receive_ids=[5],
        players=_players(),
        context=_ctx(),
        baselines=baselines,
        window="bubble",
    )
    assert result["verdict"] == "even"
    assert result["delta_st"] == 0
    assert result["delta_lt"] == 0
    assert result["lineup_hole_penalty"] == 0
    assert "summary" in result


def test_selling_stud_for_parts_taxes_a_contender():
    baselines = {"RB": 8.0, "WR": 8.0}
    parts = grade_trade(
        send_ids=[1],
        receive_ids=[2, 3],
        players=_players(),
        context=_ctx("contender"),
        baselines=baselines,
        window="contender",
    )
    assert parts["stud_tax"] > 0
    assert parts["lineup_hole_penalty"] > 0
    assert any("hole" in note.lower() or "Stud tax" in note for note in parts["notes"])
    assert parts["blended"] < 0
    assert parts["grade"] in {"C", "C-", "D", "F"}


def test_consolidating_depth_gets_a_bonus():
    send = [
        PlayerValue(
            id=2, name="A", position="WR", weekly_rate=10, replacement_weekly=8,
            st_games=3, lt_games=8, st_points=30, lt_points=80, st_vorp=6, lt_vorp=16,
            blended=10, window="bubble",
        ),
        PlayerValue(
            id=3, name="B", position="WR", weekly_rate=9, replacement_weekly=8,
            st_games=3, lt_games=8, st_points=27, lt_points=72, st_vorp=3, lt_vorp=8,
            blended=5, window="bubble",
        ),
    ]
    recv = [
        PlayerValue(
            id=4, name="Stud", position="WR", weekly_rate=19, replacement_weekly=8,
            st_games=3, lt_games=8, st_points=57, lt_points=152, st_vorp=33, lt_vorp=88,
            blended=50, window="bubble",
        )
    ]
    assert concentration_penalty(send, recv) < 0
    assert letter_grade(12) == "A+"
    assert letter_grade(-9) == "F"


def test_rebuilder_weights_rest_of_season_more():
    baselines = {"RB": 8.0, "WR": 8.0}
    # Slightly worse now, better ROS is invented via injury: receive a currently OUT star
    players = _players()
    players[4] = {
        "id": 4,
        "name": "Injured WR1",
        "position": "WR",
        "projected_points": 19,
        "injury_status": "OUT",
        "is_starter": True,
    }
    rebuild = grade_trade(
        send_ids=[2],
        receive_ids=[4],
        players=players,
        context=_ctx("rebuilder"),
        baselines=baselines,
        window="rebuilder",
    )
    contend = grade_trade(
        send_ids=[2],
        receive_ids=[4],
        players=players,
        context=_ctx("contender"),
        baselines=baselines,
        window="contender",
    )
    assert rebuild["weights"]["lt"] > contend["weights"]["lt"]
    assert rebuild["blended"] > contend["blended"]
