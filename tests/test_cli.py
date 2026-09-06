import json

from league_manager.cli import main
from league_manager.config import Settings
from league_manager.espn_client import EspnClient


class FakePlayer:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeTeam:
    def __init__(self):
        self.team_id = 7
        self.team_name = "Test Squad"
        self.team_abbrev = "TST"
        self.wins = 2
        self.losses = 1
        self.ties = 0
        self.points_for = 240.5
        self.points_against = 210.0
        self.standing = 3
        self.owners = [{"id": "{SWID}"}]
        self.roster = [
            FakePlayer(
                playerId=11,
                name="Starter RB",
                position="RB",
                lineupSlotId=2,
                projected_points=15,
                injured=False,
                proTeam="DET",
            ),
            FakePlayer(
                playerId=12,
                name="Bench RB",
                position="RB",
                lineupSlotId=20,
                projected_points=8,
                injured=False,
                proTeam="CHI",
            ),
        ]


class FakeSettings:
    name = "Agent League"
    team_count = 10
    playoff_team_count = 4
    scoring_type = "ppr"


class FakeLeague:
    def __init__(self):
        self.settings = FakeSettings()
        self.current_week = 3
        self.nfl_week = 3
        self.teams = [FakeTeam()]

    def standings(self):
        return self.teams

    def scoreboard(self, week=None):
        class Game:
            home_team = FakeTeam()
            away_team = FakeTeam()
            home_score = 90
            away_score = 80

        return [Game()]

    def free_agents(self, week=None, size=50, position=None):
        return [
            FakePlayer(
                playerId=99,
                name="FA RB",
                position=position or "RB",
                projected_points=13,
                percent_owned=42,
            )
        ]

    def player_info(self, name=None, playerId=None):
        return FakePlayer(playerId=5, name=name, position="WR", projected_avg_points=11)

    def recent_activity(self, size=25, msg_type=None):
        return []


def test_cli_reads_with_fake_league(monkeypatch, capsys):
    settings = Settings(
        league_id=1,
        espn_s2="s2",
        swid="{SWID}",
        season=2026,
        team_id=7,
    )
    monkeypatch.setattr("league_manager.cli.load_settings", lambda: settings)
    monkeypatch.setattr(
        "league_manager.cli.EspnClient",
        lambda _settings: EspnClient(_settings, league=FakeLeague()),
    )

    assert main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["name"] == "Agent League"
    assert status["your_team"]["id"] == 7

    assert main(["roster"]) == 0
    roster = json.loads(capsys.readouterr().out)
    assert roster["roster"][0]["name"] == "Starter RB"

    assert main(["lineup-advice"]) == 0
    advice = json.loads(capsys.readouterr().out)
    assert "recommended" in advice

    assert main(["add", "--player", "99", "--drop", "12"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["executed"] is False
    assert preview["payload"]["type"] == "FREEAGENT"


def test_cli_auth_status_without_secrets(monkeypatch, capsys):
    monkeypatch.delenv("ESPN_S2", raising=False)
    monkeypatch.delenv("ESPN_SWID", raising=False)
    monkeypatch.delenv("ESPN_LEAGUE_ID", raising=False)
    assert main(["auth-status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is False
