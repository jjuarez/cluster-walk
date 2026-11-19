import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from cluster_walk.__main__ import main


@pytest.fixture
def runner(capsys):
    def invoke(args):
        try:
            exit_code = main(args)
        except SystemExit as exc:
            exit_code = exc.code
        captured = capsys.readouterr()
        return SimpleNamespace(exit_code=exit_code, output=captured.out + captured.err)

    return invoke


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"clusters": ["first", "second cluster", "first"]}))
    return path


def test_dryrun_preserves_order_and_quotes_clusters(config_file, monkeypatch, runner):
    def unexpected_run(*args, **kwargs):
        pytest.fail("dry run must not execute commands")

    monkeypatch.setattr("cluster_walk.__main__.subprocess.run", unexpected_run)
    result = runner(["--config", str(config_file), "launch", "--dryrun", "echo hello"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "kubie exec first default echo hello",
        "kubie exec 'second cluster' default echo hello",
        "kubie exec first default echo hello",
    ]


def test_launch_stops_on_failure_and_sets_cluster_environment(config_file, monkeypatch, runner):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1 if len(calls) == 2 else 0)

    monkeypatch.setattr("cluster_walk.__main__.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "echo hello"])

    assert result.exit_code != 0
    assert "Command failed for second cluster with exit status 1" in result.output
    assert [call[1]["env"]["CLUSTER_WALK_CLUSTER"] for call in calls] == ["first", "second cluster"]
    assert all(call[1]["shell"] and call[1]["check"] is False for call in calls)


@pytest.mark.parametrize("content", ["{}", '{"clusters": ["ok", " "]}', "not json"])
def test_invalid_configuration_is_reported(tmp_path, content, runner):
    path = tmp_path / "config.json"
    path.write_text(content)
    result = runner(["--config", str(path), "launch", "--dryrun", "echo hello"])

    assert result.exit_code != 0
    assert "Error:" in result.output


def test_selected_cluster_overrides_configuration(config_file, runner):
    result = runner(["--config", str(config_file), "--cluster", "chosen cluster", "launch", "--dryrun", "echo hello"])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["kubie exec 'chosen cluster' default echo hello"]


def test_selected_cluster_does_not_require_configuration(tmp_path, runner):
    result = runner(["--config", str(tmp_path / "missing.json"), "--cluster", "chosen", "launch", "--dryrun", "echo hello"])

    assert result.exit_code == 0
    assert result.output.strip() == "kubie exec chosen default echo hello"


@pytest.mark.parametrize("cluster", ["", "   "])
def test_selected_cluster_must_not_be_empty(cluster, runner):
    result = runner(["--cluster", cluster, "launch", "--dryrun", "echo hello"])

    assert result.exit_code != 0
    assert "must not be empty" in result.output


@pytest.mark.parametrize(
    "args, expected",
    [
        ([], "required: COMMAND"),
        (["launch"], "required: SHELL_COMMAND"),
        (["launch", "   "], "must not be empty"),
        (["unknown"], "invalid choice"),
        (["--unknown"], "required: COMMAND"),
    ],
)
def test_invalid_arguments(runner, args, expected):
    result = runner(args)
    assert result.exit_code == 2
    assert expected in result.output


@pytest.mark.parametrize(
    "args, expected",
    [
        (["--help"], "--cluster"),
        (["launch", "--help"], "SHELL_COMMAND"),
    ],
)
def test_help(runner, args, expected):
    result = runner(args)
    assert result.exit_code == 0
    assert expected in result.output


def test_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "cluster_walk", "--cluster", "example", "launch", "--dryrun", "echo hello"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "kubie exec example default echo hello"
