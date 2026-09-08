from league_manager.search import search_trades
from league_manager.value import LeagueContext


def _ctx() -> LeagueContext:
    return LeagueContext(
        current_week=10,
        season_end_week=17,
        wins=6,
        losses=3,
        standing=3,
        playoff_team_count=4,
        team_count=10,
    )


def test_search_keeps_plus_ev_close_face_one_for_one():
    # Same ESPN weekly face. We send the player whose season remainder is nearly
    # spent and get the one with a lot of ROS left.
    ours = {
        "id": 1,
        "name": "Our Spent RB",
        "position": "RB",
        "projected_points": 12,
        "projected_total_points": 100,
        "points": 70,
        "is_starter": True,
        "team_id": 7,
    }
    theirs = {
        "id": 2,
        "name": "Their ROS WR",
        "position": "WR",
        "projected_points": 12,
        "projected_total_points": 220,
        "points": 40,
        "is_starter": True,
        "team_id": 8,
    }
    filler = {
        "id": 3,
        "name": "Their Bench",
        "position": "WR",
        "projected_points": 6,
        "is_starter": False,
        "team_id": 8,
    }
    result = search_trades(
        our_team_id=7,
        teams=[
            {"id": 7, "name": "Us", "roster": [ours]},
            {"id": 8, "name": "Them", "roster": [theirs, filler]},
        ],
        players={1: ours, 2: theirs, 3: filler},
        context=_ctx(),
        baselines={"RB": 8.0, "WR": 8.0},
        window="bubble",
        kinds=("1:1",),
        limit=10,
        min_surplus=1.0,
    )
    assert result["considered"] >= 1
    assert result["trades"]
    top = result["trades"][0]
    assert top["kind"] == "1:1"
    assert top["send_ids"] == [1]
    assert top["receive_ids"] == [2]
    assert top["blended"] > 0
    assert abs(top["their_espn_face_net"]) < 1
    assert top["receive"][0]["ros_source"] == "espn_remainder"


def test_search_drops_lopsided_espn_face():
    cheap = {
        "id": 1,
        "name": "Streamer",
        "position": "RB",
        "projected_points": 8,
        "is_starter": False,
        "team_id": 7,
    }
    star = {
        "id": 2,
        "name": "WR1",
        "position": "WR",
        "projected_points": 20,
        "is_starter": True,
        "team_id": 8,
    }
    result = search_trades(
        our_team_id=7,
        teams=[
            {"id": 7, "name": "Us", "roster": [cheap]},
            {"id": 8, "name": "Them", "roster": [star]},
        ],
        players={1: cheap, 2: star},
        context=_ctx(),
        baselines={"RB": 8.0, "WR": 8.0},
        window="bubble",
        kinds=("1:1",),
    )
    assert result["considered"] == 1
    assert result["trades"] == []
