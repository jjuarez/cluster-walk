import os
import shlex
import subprocess

import click


class ExecutionError(Exception):
    pass


class Executor:
    @classmethod
    def capture(cls, cluster: str, command: str, dry_run: bool) -> dict:
        """Capture one invocation for structured output."""
        record = {"cluster": cluster, "command": command, "output": "", "stderr": "", "exit_code": None}
        if dry_run:
            return record
        full_command = f"kubie exec {shlex.quote(cluster)} default {command}"
        env = os.environ.copy()
        env["CLUSTER_WALK_CLUSTER"] = cluster
        try:
            result = subprocess.run(full_command, shell=True, env=env, check=False, capture_output=True, text=True, errors="replace")
        except OSError as exc:
            record["stderr"] = f"Could not start shell for {cluster}: {exc}"
            return record
        record.update(output=result.stdout, stderr=result.stderr, exit_code=result.returncode)
        return record

    @classmethod
    def execute(cls, cluster: str, command: str, dry_run: bool) -> None:
        full_command = f"kubie exec {shlex.quote(cluster)} default {command}"
        if dry_run:
            click.echo(f"(dry-run): '{full_command}'")
            return
        env = os.environ.copy()
        env["CLUSTER_WALK_CLUSTER"] = cluster
        try:
            result = subprocess.run(full_command, shell=True, env=env, check=False)
        except OSError as exc:
            raise ExecutionError(f"Could not start shell for {cluster}: {exc}") from exc
        if result.returncode:
            raise ExecutionError(f"Command failed for {cluster} with exit status {result.returncode}.")
