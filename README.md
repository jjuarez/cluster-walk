# cluster-walk

Run a command once for each cluster in a JSON configuration file.
Python 3.14 or newer is required. Install with
`uv sync` or `pip install .`.

The default configuration is `config.json` in the current directory; use
`--config PATH` before `launch` to select another file. It must contain an
object with a `clusters` array of non-empty strings.

```sh
cluster-walk --config config.json launch --dry-run 'echo "Do nothing"'
cluster-walk --config config.json launch 'kubectl get pods'
cluster-walk --config config.json launch --json 'kubectl get pods'
cluster-walk --config config.json launch --json --parse-json-output 'kubectl get pods -o json'
```

Use `cluster-walk --help` or `cluster-walk launch --help` for argument details.
Pass the shell command as one quoted argument; use `--` before it if it begins
with a dash.

Each invocation runs `kubie exec CLUSTER default COMMAND`, inherits the
environment, and receives the cluster name in `CLUSTER_WALK_CLUSTER`. Commands run
in configuration order, including duplicates, and stop on the first failure.
Earlier invocations may already have completed.
For plain-text output, the CLI prints `Cluster: NAME` before each command's
output so the results can be distinguished.

With `--json`, output is captured and printed as a JSON array after execution.
Each entry has `cluster`, `command` (the supplied shell command), `output`
(standard output), `stderr`, and `exit_code`. The array preserves cluster order
and duplicates. On failure it includes the failing result and earlier results,
then exits with status 1. If the shell cannot start, `exit_code` is `null` and
`stderr` describes the error. With `--json --dry-run`, each configured cluster
is listed with empty output and stderr and a `null` exit code; nothing is run.
Configuration errors are reported on standard error before any JSON is printed.

Add `--parse-json-output` with `--json` to embed each successful command's
standard output as a JSON value instead of a string. If parsing fails, execution
stops, the original output is preserved in the result, an error identifying the
cluster is printed to standard error, and the process exits with status 1.
Failed commands retain their original output without parsing. Dry runs do not
parse output.

The formatted command is executed through a shell. Shell operators and expansions
in the supplied command run locally, so only use trusted command strings. Cluster
names are quoted before insertion. `--dry-run` prints the complete command with a
`(dry-run):` prefix without executing it. `kubie` and the commands it runs must be
installed and configured.

Install the development dependencies and use [Task](https://taskfile.dev/) to
run lint checks and tests:

```sh
uv sync --dev
task lint
task test
task check  # Run both
```
