"""Sample SiLA client: read and print the current robot pose.

Connects to a running bcap-sila2 server and calls the RobotService commands to
print the current pose. By default it prints the joint angles
(RobotService.GetJointAngles -> "CurJnt"); pass --cartesian to also print the
Cartesian position (RobotService.GetCartesianPosition -> "CurPos"). It only
reads; it does not move the robot.

Start the server first, e.g.:

    uv run python -m bcap_sila2 --config config.toml --insecure

then run this sample:

    uv run python samples/get_pose_example.py --host 127.0.0.1 --port 50052
"""

from __future__ import annotations

import argparse

from sila2.client import SilaClient
from sila2.framework.errors.defined_execution_error import DefinedExecutionError


def _print_values(label: str, values: list) -> None:
    print(f"{label} ({len(values)} values):")
    for i, v in enumerate(values):
        print(f"    [{i}] {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=50052, help="server port")
    parser.add_argument(
        "--cartesian",
        action="store_true",
        help="also print the Cartesian position (CurPos), not just the joint angles",
    )
    args = parser.parse_args()

    # Connect without encryption (matches `--insecure` on the server).
    client = SilaClient(args.host, args.port, insecure=True)

    try:
        angles = client.RobotService.GetJointAngles().JointAngles
        _print_values("Joint angles (CurJnt)", angles)

        if args.cartesian:
            position = client.RobotService.GetCartesianPosition().Position
            _print_values("Cartesian position (CurPos)", position)
    except DefinedExecutionError as e:
        # ControllerConnectionError (controller unreachable) or RobotAccessError.
        print(f"Failed to read pose [{e.identifier}]: {e.message}")


if __name__ == "__main__":
    main()
