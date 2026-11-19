"""Run a command once for each configured cluster."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


class ClusterWalkError(Exception):
    """An error encountered while loading configuration or running a command."""


def load_config(path: Path) -> list[str]:
    """Read and validate the cluster list."""
    try:
        with path.open(encoding="utf-8") as config_file:
            data = json.load(config_file)
    except FileNotFoundError as exc:
        raise ClusterWalkError(f"Configuration file not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClusterWalkError(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("clusters"), list):
        raise ClusterWalkError("Configuration must contain a 'clusters' array.")
    clusters = data["clusters"]
    if not all(isinstance(cluster, str) and cluster.strip() for cluster in clusters):
        raise ClusterWalkError("Every cluster must be a non-empty string.")
    return clusters


def execute(cluster: str, command: str, dryrun: bool) -> None:
    full_command = f"kubie exec {shlex.quote(cluster)} default {command}"
    if dryrun:
        print(full_command)
        return
    env = os.environ.copy()
    env["CLUSTER_WALK_CLUSTER"] = cluster
    try:
        result = subprocess.run(full_command, shell=True, env=env, check=False)
    except OSError as exc:
        raise ClusterWalkError(f"Could not start shell for {cluster}: {exc}") from exc
    if result.returncode:
        raise ClusterWalkError(f"Command failed for {cluster} with exit status {result.returncode}.")


def non_empty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run commands for configured clusters or a specified cluster.")
    parser.add_argument("--config", type=Path, default=Path("config.json"), metavar="PATH", help="JSON configuration file (default: config.json)")
    parser.add_argument("--cluster", type=non_empty, metavar="NAME", help="run for one cluster, ignoring the configuration file")
    subparsers = parser.add_subparsers(dest="action", required=True, metavar="COMMAND")
    launch_parser = subparsers.add_parser("launch", help="run a shell command for each selected cluster")
    launch_parser.add_argument("--dryrun", action="store_true", help="show commands without running them")
    launch_parser.add_argument("command", type=non_empty, metavar="SHELL_COMMAND", help="shell command to run (quote commands containing spaces)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        clusters = [args.cluster] if args.cluster is not None else load_config(args.config)
        for cluster in clusters:
            execute(cluster, args.command, args.dryrun)
    except ClusterWalkError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
