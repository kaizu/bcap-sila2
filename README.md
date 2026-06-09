# bcap-sila2

A **SiLA 2 server** that exposes DENSO robot controller functions over ORiN
b-CAP, wrapping the [orin_bcap](https://github.com/DENSORobot/orin_bcap) Python
client. The server is stateless: each command connects, operates, and
disconnects.

> ⚠️ **Disclaimer**: This software is under active development. It comes with
> **no warranty** and the authors accept **no liability** for any results or
> damages. Use at your own risk, and verify safety before connecting to real
> hardware.

## Features (v1)

- **VariableService**: `ReadVariable`, `WriteVariable`, `GetVariableNames`
- **TaskService**: `RunTask` (one-cycle, observable), `GetTaskNames`

## Requirements

Python >= 3.11, [uv](https://docs.astral.sh/uv/), and a DENSO controller
(default type `RC9`; the server also starts without hardware).

## Setup

`orin_bcap` is a git submodule, so clone recursively:

```bash
git clone --recurse-submodules git@github.com:kaizu/bcap-sila2.git
cd bcap-sila2
uv sync
```

Already cloned: `git submodule update --init && uv sync`.

## Configuration

Connection settings are given in a TOML file (not as command arguments). Copy
and edit the example:

```bash
cp config.example.toml config.toml
```

See [config.example.toml](config.example.toml) for all keys (`[controller]`
host/port/type/option, `[task]` run_wait_seconds, `[server]` host/port).

## Run the server

```bash
uv run python -m bcap_sila2 --config config.toml --insecure
```

`--insecure` disables encryption. Listen address/port come from `[server]`;
override with `-a/--ip-address` and `-p/--port`. See `--help` for TLS options.

## Run the sample client

With the server running, in another terminal:

```bash
uv run python samples/client_example.py --host 127.0.0.1 --port 50052
```

It lists features, variable names and task names, and reads the first variable.
Write/run commands are included as commented-out examples.

## License

[MIT](LICENSE) © 2026 Kazunari Kaizu
