"""Run a command once for each configured cluster."""

import json
import os
import shlex
import subprocess
from pathlib import Path

import click


def load_config(path: Path) -> list[str]:
    """Read and validate the cluster list."""
    try:
        with path.open(encoding="utf-8") as config_file:
            data = json.load(config_file)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Configuration file not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("clusters"), list):
        raise click.ClickException("Configuration must contain a 'clusters' array.")
    clusters = data["clusters"]
    if not all(isinstance(cluster, str) and cluster.strip() for cluster in clusters):
        raise click.ClickException("Every cluster must be a non-empty string.")
    return clusters


def execute(cluster: str, command: str, dryrun: bool) -> None:
    full_command = f"kubie exec {shlex.quote(cluster)} default {command}"
    if dryrun:
        click.echo(full_command)
        return
    env = os.environ.copy()
    env["CLUSTER_WALK_CLUSTER"] = cluster
    try:
        result = subprocess.run(full_command, shell=True, env=env, check=False)
    except OSError as exc:
        raise click.ClickException(f"Could not start shell for {cluster}: {exc}") from exc
    if result.returncode:
        raise click.ClickException(f"Command failed for {cluster} with exit status {result.returncode}.")


@click.group()
@click.option("--config", "config_path", type=click.Path(path_type=Path, dir_okay=False),
              default=Path("config.json"), show_default=True, help="Path to the JSON configuration file.")
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    """Run commands for configured clusters."""
    ctx.obj = config_path


@main.command("launch")
@click.option("--dryrun", is_flag=True, help="Show commands without running them.")
@click.argument("command", type=str)
@click.pass_obj
def launch(path: Path, command: str, dryrun: bool) -> None:
    if not command.strip():
        raise click.BadParameter("Command must not be empty.", param_hint="COMMAND")
    for cluster in load_config(path):
        execute(cluster, command, dryrun)


if __name__ == "__main__":
    main()
