"""Example SiLA client for the b-CAP SiLA2 server.

Connects to a running server and exercises the read-only commands
(GetVariableNames, GetTaskNames, ReadVariable). The WriteVariable example is
left commented out, and RunTask only runs when a task name is passed with
``--run-task``, so by default this script is safe to run against a live
controller without changing its state.

Start the server first, e.g.:

    uv run python -m bcap_sila2 --config config.toml --insecure

then run this sample:

    uv run python samples/client_example.py --host 127.0.0.1 --port 50052

To also start a task and wait for it to finish:

    uv run python samples/client_example.py --run-task Pro1
"""

from __future__ import annotations

import argparse
import time

from sila2.client import SilaClient
from sila2.framework.errors.defined_execution_error import DefinedExecutionError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=50052, help="server port")
    parser.add_argument(
        "--run-task",
        metavar="NAME",
        help="start this task and wait for it to finish (changes controller state)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="how often to print RunTask status while waiting (seconds)",
    )
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

    # --- write example (commented out) --------------------------------------
    # This changes controller state, so it is left commented out.
    #
    # Write a value to a variable (value is a string, with an explicit DataType):
    # client.VariableService.WriteVariable("I100", "1", "Boolean")
    # client.VariableService.WriteVariable("MyInt", "42", "Integer")

    # --- run a task and wait for completion (opt-in) ------------------------
    if args.run_task:
        run_task_and_wait(client, args.run_task, args.poll_interval)


def run_task_and_wait(client: SilaClient, task_name: str, poll_interval: float) -> None:
    """Start a task and wait for the observable command to finish.

    RunTask is an observable command: the server starts the task, polls its
    execution status, and only finishes the command once the task has run one
    cycle (or fails / times out). The client mirrors that by waiting for the
    command instance to reach a terminal state, then requesting the result.
    """
    print(f"\nRunTask({task_name!r}) - starting and waiting for completion...")
    task = client.TaskService.RunTask(task_name)

    # get_responses() does not block; poll until the command is in a terminal
    # state (finishedSuccessfully / finishedWithError).
    while not task.done:
        time.sleep(poll_interval)
        print(f"  status={task.status}")

    try:
        result = task.get_responses()
    except DefinedExecutionError as e:
        # e.g. TaskExecutionTimeout (timed out, task stopped) or TaskAccessError
        # (the task stopped abnormally instead of completing one cycle).
        print(f"RunTask failed [{e.identifier}]: {e.message}")
        return
    print(f"RunTask completed, Started={result.Started}")


if __name__ == "__main__":
    main()
