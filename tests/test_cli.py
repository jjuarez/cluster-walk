import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cluster_walk.__main__ import main


@pytest.fixture
def runner():
    def invoke(args):
        return CliRunner().invoke(main, args)

    return invoke


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"clusters": ["first", "second cluster", "first"]}))
    return path


def test_dry_run_preserves_order_and_quotes_clusters(config_file, monkeypatch, runner):
    def unexpected_run(*args, **kwargs):
        pytest.fail("dry run must not execute commands")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", unexpected_run)
    result = runner(["--config", str(config_file), "launch", "--dry-run", "echo hello"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "(dry-run): 'kubie exec first default echo hello'",
        "(dry-run): 'kubie exec 'second cluster' default echo hello'",
        "(dry-run): 'kubie exec first default echo hello'",
    ]


def test_launch_stops_on_failure_and_sets_cluster_environment(config_file, monkeypatch, runner):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1 if len(calls) == 2 else 0)

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "echo hello"])

    assert result.exit_code != 0
    assert "Command failed for second cluster with exit status 1" in result.output
    assert [call[1]["env"]["CLUSTER_WALK_CLUSTER"] for call in calls] == ["first", "second cluster"]
    assert all(call[1]["shell"] and call[1]["check"] is False for call in calls)


def test_plain_output_labels_each_cluster_before_its_output(config_file, monkeypatch, runner):
    def run(command, **kwargs):
        print(f"output for {kwargs['env']['CLUSTER_WALK_CLUSTER']}", end="")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "echo hello"])
    assert result.exit_code == 0
    assert result.stdout == (
        "Cluster: first\noutput for first\n"
        "Cluster: second cluster\noutput for second cluster\n"
        "Cluster: first\noutput for first"
    )


def test_json_results_preserve_order_and_capture_output(config_file, monkeypatch, runner):
    calls = []

    def run(command, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=0, stdout=f"hello {kwargs['env']['CLUSTER_WALK_CLUSTER']}\n", stderr="warning\n")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "--json", "echo hello"])
    assert result.exit_code == 0
    records = json.loads(result.stdout)
    assert [record["cluster"] for record in records] == ["first", "second cluster", "first"]
    assert records[1] == {"cluster": "second cluster", "command": "echo hello", "output": "hello second cluster\n", "stderr": "warning\n", "exit_code": 0}
    assert all(call["capture_output"] and call["text"] for call in calls)


def test_json_failure_returns_partial_results(config_file, monkeypatch, runner):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=3 if len(calls) == 2 else 0, stdout="output", stderr="failed" if len(calls) == 2 else "")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "--json", "echo hello"])
    records = json.loads(result.stdout)
    assert result.exit_code == 1
    assert len(records) == 2
    assert records[1]["exit_code"] == 3
    assert records[1]["stderr"] == "failed"


@pytest.mark.parametrize("output, expected", [('{"items": [1, 2]}', {"items": [1, 2]}), ("[true, null]", [True, None]), ('"text"', "text")])
def test_parse_json_output(config_file, monkeypatch, runner, output, expected):
    monkeypatch.setattr("cluster_walk.utils.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""))
    result = runner(["--config", str(config_file), "launch", "--json", "--parse-json-output", "kubectl get pods -o json"])
    assert result.exit_code == 0
    assert [record["output"] for record in json.loads(result.stdout)] == [expected] * 3


@pytest.mark.parametrize("output", ["not json", "NaN", "1e999"])
def test_parse_json_invalid_output_stops_and_preserves_results(config_file, monkeypatch, runner, output):
    calls = []

    def run(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout='{"ok": true}' if len(calls) == 1 else output, stderr="")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", run)
    result = runner(["--config", str(config_file), "launch", "--json", "--parse-json-output", "example"])
    records = json.loads(result.stdout)
    assert result.exit_code == 1
    assert len(records) == 2
    assert records[0]["output"] == {"ok": True}
    assert records[1]["output"] == output
    assert "Invalid JSON output for cluster second cluster" in result.stderr


def test_parse_json_requires_json(runner):
    result = runner(["launch", "--parse-json-output", "example"])
    assert result.exit_code == 2
    assert "requires --json" in result.output


def test_parse_json_dry_run(config_file, monkeypatch, runner):
    def unexpected_run(*args, **kwargs):
        pytest.fail("dry run must not execute commands")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", unexpected_run)
    result = runner(["--config", str(config_file), "launch", "--json", "--parse-json-output", "--dry-run", "example"])
    assert result.exit_code == 0
    assert all(record["output"] == "" for record in json.loads(result.stdout))


def test_parse_json_command_failure_preserves_raw_output(config_file, monkeypatch, runner):
    monkeypatch.setattr("cluster_walk.utils.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="not json", stderr="failed"))
    result = runner(["--config", str(config_file), "launch", "--json", "--parse-json-output", "example"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)[0]["output"] == "not json"
    assert "Invalid JSON" not in result.stderr


def test_json_dry_run_does_not_execute(config_file, monkeypatch, runner):
    def unexpected_run(*args, **kwargs):
        pytest.fail("dry run must not execute commands")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", unexpected_run)
    result = runner(["--config", str(config_file), "launch", "--json", "--dry-run", "echo hello"])
    assert result.exit_code == 0
    records = json.loads(result.stdout)
    assert len(records) == 3
    assert all(record["exit_code"] is None and record["output"] == "" and record["stderr"] == "" for record in records)


def test_json_shell_start_failure_returns_partial_results(config_file, monkeypatch, runner):
    def fail(*args, **kwargs):
        raise OSError("shell unavailable")

    monkeypatch.setattr("cluster_walk.utils.subprocess.run", fail)
    result = runner(["--config", str(config_file), "launch", "--json", "echo hello"])
    records = json.loads(result.stdout)
    assert result.exit_code == 1
    assert len(records) == 1
    assert records[0]["exit_code"] is None
    assert "shell unavailable" in records[0]["stderr"]


@pytest.mark.parametrize("content", ["{}", '{"clusters": ["ok", " "]}', "not json"])
def test_invalid_configuration_is_reported(tmp_path, content, runner):
    path = tmp_path / "config.json"
    path.write_text(content)
    result = runner(["--config", str(path), "launch", "--dry-run", "echo hello"])

    assert result.exit_code != 0
    assert "Error:" in result.output


def test_missing_configuration_is_reported(tmp_path, runner):
    result = runner(["--config", str(tmp_path / "missing.json"), "launch", "--dry-run", "echo hello"])

    assert result.exit_code == 1
    assert "Configuration file not found" in result.output


@pytest.mark.parametrize(
    "args, expected",
    [
        ([], "Usage:"),
        (["launch"], "Missing argument 'SHELL_COMMAND'"),
        (["launch", "   "], "must not be empty"),
        (["unknown"], "No such command"),
        (["--unknown"], "No such option"),
        (["--cluster", "example", "launch", "echo hello"], "No such option"),
    ],
)
def test_invalid_arguments(runner, args, expected):
    result = runner(args)
    assert result.exit_code == 2
    assert expected in result.output


@pytest.mark.parametrize(
    "args, expected",
    [
        (["--help"], "--config"),
        (["launch", "--help"], "SHELL_COMMAND"),
    ],
)
def test_help(runner, args, expected):
    result = runner(args)
    assert result.exit_code == 0
    assert expected in result.output


def test_module_entry_point(config_file):
    result = subprocess.run(
        [sys.executable, "-m", "cluster_walk", "--config", str(config_file), "launch", "--dry-run", "echo hello"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "(dry-run): 'kubie exec first default echo hello'",
        "(dry-run): 'kubie exec 'second cluster' default echo hello'",
        "(dry-run): 'kubie exec first default echo hello'",
    ]
