# cluster-walk

Run a command once for each cluster in a JSON configuration file. Python 3.14
or newer is required. Install with `uv sync` or `pip install .`.

The default configuration is `config.json` in the current directory; use
`--config PATH` before `launch` to select another file. It must contain an
object with a `clusters` array of non-empty strings.

```sh
cluster-walk --config config.json launch --dryrun 'echo hello'
cluster-walk --config config.json launch 'kubectl get pods'
```

Each invocation runs `kubie CLUSTER exec default COMMAND`, inherits the
environment, and receives the cluster name in `CLUSTER_WALK_CLUSTER`. Commands run
in configuration order, including duplicates, and stop on the first failure.
Earlier invocations may already have completed.

The formatted command is executed through a shell. Shell operators and expansions
in the supplied command run locally, so only use trusted command strings. Cluster
names are quoted before insertion. `--dryrun` prints the complete command without
executing it. `kubie` and the commands it runs must be installed and configured.

Install the development dependencies and use [Task](https://taskfile.dev/) to
run lint checks and tests:

```sh
uv sync --dev
task lint
task test
task check  # Run both
```
