"""Run a command once for each configured cluster."""

import json
import math
from pathlib import Path

import click

from cluster_walk.config import ConfigError, JSONConfig
from cluster_walk.utils import ExecutionError, Executor


def non_empty(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise click.BadParameter("must not be empty")
    return value


@click.group()
@click.option("--config", type=click.Path(path_type=Path), default=Path("config.json"), show_default=True, help="JSON configuration file.")
@click.pass_context
def main(ctx: click.Context, config: Path) -> None:
    """Run commands for configured clusters."""
    ctx.obj = {"config": config}


@main.command()
@click.option("--dry-run", is_flag=True, help="Show commands without running them.")
@click.option("--json", "json_output", is_flag=True, help="Return results as a JSON array.")
@click.option("--parse-json-output", is_flag=True, help="Parse successful command output as JSON (requires --json).")
@click.argument("command", metavar="SHELL_COMMAND", callback=non_empty)
@click.pass_context
def launch(ctx: click.Context, dry_run: bool, json_output: bool, parse_json_output: bool, command: str) -> None:
    """Run a shell command for each configured cluster."""
    if parse_json_output and not json_output:
        raise click.UsageError("--parse-json-output requires --json.")
    try:
        clusters = JSONConfig.load(ctx.obj["config"])
        if json_output:
            records = []
            failed = False
            parse_error = None
            for cluster in clusters:
                record = Executor.capture(cluster, command, dry_run)
                records.append(record)
                if not dry_run and record["exit_code"] != 0:
                    failed = True
                    break
                if parse_json_output and not dry_run:
                    try:
                        record["output"] = json.loads(record["output"], parse_constant=_reject_json_constant, parse_float=_finite_float)
                    except ValueError as exc:
                        parse_error = f"Invalid JSON output for cluster {cluster}: {exc}"
                        failed = True
                        break
            click.echo(json.dumps(records, ensure_ascii=False, indent=2))
            if failed:
                if parse_error:
                    click.echo(f"Error: {parse_error}", err=True)
                ctx.exit(1)
            return
        for index, cluster in enumerate(clusters):
            if not dry_run:
                click.echo(f"{'\n' if index else ''}Cluster: {cluster}")
            Executor.execute(cluster, command, dry_run)
    except (ConfigError, ExecutionError) as exc:
        raise click.ClickException(str(exc)) from exc


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"JSON number out of range: {value}")
    return number


if __name__ == "__main__":
    main()
