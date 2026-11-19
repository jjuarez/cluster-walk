import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cluster_walk.__main__ import main


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"clusters": ["first", "second cluster", "first"]}))
    return path


def test_dryrun_preserves_order_and_quotes_clusters(config_file, monkeypatch):
    def unexpected_run(*args, **kwargs):
        pytest.fail("dry run must not execute commands")

    monkeypatch.setattr("cluster_walk.__main__.subprocess.run", unexpected_run)
    result = CliRunner().invoke(main, ["--config", str(config_file), "launch", "--dryrun", "echo hello"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "kubie exec first default echo hello",
        "kubie exec 'second cluster' default echo hello",
        "kubie exec first default echo hello",
    ]


def test_launch_stops_on_failure_and_sets_cluster_environment(config_file, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1 if len(calls) == 2 else 0)

    monkeypatch.setattr("cluster_walk.__main__.subprocess.run", run)
    result = CliRunner().invoke(main, ["--config", str(config_file), "launch", "echo hello"])

    assert result.exit_code != 0
    assert "Command failed for second cluster with exit status 1" in result.output
    assert [call[1]["env"]["CLUSTER_WALK_CLUSTER"] for call in calls] == ["first", "second cluster"]
    assert all(call[1]["shell"] and call[1]["check"] is False for call in calls)


@pytest.mark.parametrize("content", ['{}', '{"clusters": ["ok", " "]}', 'not json'])
def test_invalid_configuration_is_reported(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    result = CliRunner().invoke(main, ["--config", str(path), "launch", "--dryrun", "echo hello"])

    assert result.exit_code != 0
    assert "Error:" in result.output
