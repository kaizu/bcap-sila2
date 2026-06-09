"""Example SiLA client for the b-CAP SiLA2 server.

Connects to a running server and exercises the read-only commands
(GetVariableNames, GetTaskNames, ReadVariable). Write and run commands
(WriteVariable, RunTask) are shown as commented-out examples so this script is
safe to run against a live controller without changing its state.

Start the server first, e.g.:

    uv run python -m bcap_sila2 --config config.toml --insecure

then run this sample:

    uv run python samples/client_example.py --host 127.0.0.1 --port 50052
"""

from __future__ import annotations

import argparse

from sila2.client import SilaClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=50052, help="server port")
    args = parser.parse_args()

    # Connect without encryption (matches `--insecure` on the server).
    client = SilaClient(args.host, args.port, insecure=True)

    print("Implemented features:")
    for feature in sorted(client.SiLAService.ImplementedFeatures.get()):
        print(f"  - {feature}")

    # --- read-only commands (executed) --------------------------------------
    variable_names = client.VariableService.GetVariableNames().VariableNames
    print(f"\nVariable names ({len(variable_names)}):")
    for name in variable_names:
        print(f"  - {name}")

    task_names = client.TaskService.GetTaskNames().TaskNames
    print(f"\nTask names ({len(task_names)}):")
    for name in task_names:
        print(f"  - {name}")

    # Read the first available variable, if any.
    if variable_names:
        first = variable_names[0]
        response = client.VariableService.ReadVariable(first)
        print(f"\nReadVariable({first!r}) -> value={response.Value!r}, type={response.DataType}")
    else:
        print("\nNo variables available to read.")

    # --- write / run commands (examples, commented out) ---------------------
    # These change controller state, so they are left commented out.
    #
    # Write a value to a variable (value is a string, with an explicit DataType):
    # client.VariableService.WriteVariable("I100", "1", "Boolean")
    # client.VariableService.WriteVariable("MyInt", "42", "Integer")
    #
    # Run a task by name (observable command). RunTask returns a command
    # instance; get_responses() blocks until the command completes:
    # task = client.TaskService.RunTask("Pro1")
    # result = task.get_responses()
    # print("RunTask started:", result.Started)


if __name__ == "__main__":
    main()
