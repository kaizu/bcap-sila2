"""Stateless b-CAP execution helpers.

The SiLA server keeps no session state between commands. Every operation opens
a fresh b-CAP connection, acquires the handle it needs, performs the operation,
then releases the handle and disconnects. These helpers encapsulate that
``connect -> operate -> release -> disconnect`` lifecycle so the feature
implementations can stay focused on data conversion.

The connection is held only for the duration of a single operation (a single
``with`` block); no handle or socket survives between calls.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, Tuple

from bcapclient import BCAPClient

from .config import ControllerConfig

# Task execution status returned by task_execute(handle, "GetStatus") (VT_I4).
TASK_NON_EXISTENT = 0  # the task does not exist
TASK_SUSPEND = 1  # hold-stopped
TASK_READY = 2  # ready (idle); a one-cycle run that finished cleanly ends here
TASK_RUN = 3  # running
TASK_STEPSTOP = 4  # step-stopped

_GET_STATUS = "GetStatus"
# task_stop mode used when forcibly stopping a task that exceeded its timeout:
# 4 = initialized stop (halt execution and reset the program to its initial state).
_INITIALIZED_STOP = 4


class RobotUnavailableError(Exception):
    """No robot could be found on the controller to acquire."""


class TaskRunError(Exception):
    """Base class for task-run failures other than connection/ORiN errors."""


class TaskTimeoutError(TaskRunError):
    """The task did not finish within the configured completion timeout."""


class TaskAbnormalStopError(TaskRunError):
    """The task left the running state without completing one cycle cleanly."""


@contextmanager
def controller_session(cfg: ControllerConfig) -> Iterator[Tuple[BCAPClient, Any]]:
    """Open a b-CAP service and controller connection for the duration of the block.

    On entry: create the socket, start the b-CAP service, and connect to the
    controller. On exit: disconnect the controller, stop the service, and close
    the socket. Yields the connected client and the controller handle.
    """
    client = BCAPClient(cfg.host, cfg.port, cfg.timeout)
    service_started = False
    controller_handle = None
    try:
        client.service_start("")
        service_started = True
        controller_handle = client.controller_connect(
            cfg.name, cfg.provider, cfg.machine, cfg.option
        )
        yield client, controller_handle
    finally:
        if controller_handle is not None:
            try:
                client.controller_disconnect(controller_handle)
            except Exception:
                pass
        if service_started:
            try:
                client.service_stop()
            except Exception:
                pass
        # BCAPClient closes its socket in __del__; drop the only reference.
        del client


@contextmanager
def _variable(
    client: BCAPClient, controller_handle: Any, name: str, option: str = ""
) -> Iterator[Any]:
    """Acquire a controller variable handle, releasing it on exit."""
    handle = client.controller_getvariable(controller_handle, name, option)
    try:
        yield handle
    finally:
        try:
            client.variable_release(handle)
        except Exception:
            pass


@contextmanager
def _task(
    client: BCAPClient, controller_handle: Any, name: str, option: str = ""
) -> Iterator[Any]:
    """Acquire a controller task handle, releasing it on exit."""
    handle = client.controller_gettask(controller_handle, name, option)
    try:
        yield handle
    finally:
        try:
            client.task_release(handle)
        except Exception:
            pass


@contextmanager
def _robot(
    client: BCAPClient, controller_handle: Any, name: str, option: str = ""
) -> Iterator[Any]:
    """Acquire a controller robot handle, releasing it on exit."""
    handle = client.controller_getrobot(controller_handle, name, option)
    try:
        yield handle
    finally:
        try:
            client.robot_release(handle)
        except Exception:
            pass


def _resolve_robot_name(client: BCAPClient, controller_handle: Any, name: str) -> str:
    """Return ``name`` if given, else the first robot reported by the controller."""
    if name:
        return name
    names = client.controller_getrobotnames(controller_handle, "")
    if not names:
        raise RobotUnavailableError("No robot is available on the controller.")
    return names[0]


def read_variable(cfg: ControllerConfig, name: str) -> Any:
    """Read a controller variable and return its native value."""
    with controller_session(cfg) as (client, ctrl):
        with _variable(client, ctrl, name) as var:
            return client.variable_getvalue(var)


def write_variable(cfg: ControllerConfig, name: str, value: Any) -> None:
    """Write a native value to a controller variable."""
    with controller_session(cfg) as (client, ctrl):
        with _variable(client, ctrl, name) as var:
            client.variable_putvalue(var, value)


def get_variable_names(cfg: ControllerConfig) -> list[str]:
    """List the names of all controller variables."""
    with controller_session(cfg) as (client, ctrl):
        return client.controller_getvariablenames(ctrl, "")


def run_task(
    cfg: ControllerConfig,
    name: str,
    *,
    mode: int = 1,
    poll_interval: float,
    start_timeout: float,
    completion_timeout: float,
    on_running: Optional[Callable[[], None]] = None,
    on_poll: Optional[Callable[[int], None]] = None,
) -> int:
    """Start a controller task by name and wait for it to finish.

    The connection is held for the whole run (allowed within a single command):
    after ``task_start`` the task status is polled every ``poll_interval`` seconds
    in two phases.

    1. Wait up to ``start_timeout`` seconds for the task to enter ``TASK_RUN``.
       ``on_running`` (if given) is called once the running state is observed.
    2. Wait for the task to leave ``TASK_RUN``. A clean one-cycle completion
       (``TASK_READY``) returns that status; any other state raises
       :class:`TaskAbnormalStopError`. If ``completion_timeout`` (> 0) elapses
       first, the task is stopped (initialized stop) and :class:`TaskTimeoutError`
       is raised.

    ``on_poll`` (if given) is called with the current status on every poll. It is
    a hook for future cancellation support; v1 does not act on it.

    Returns the final task status (always ``TASK_READY`` on success).
    """
    with controller_session(cfg) as (client, ctrl):
        with _task(client, ctrl, name) as task:
            client.task_start(task, mode, "")

            # Phase 1: wait for the task to actually start running, so a task that
            # has not spun up yet is not mistaken for one that already finished.
            deadline = time.monotonic() + start_timeout
            while True:
                status = client.task_execute(task, _GET_STATUS)
                if on_poll is not None:
                    on_poll(status)
                if status == TASK_RUN:
                    break
                if time.monotonic() >= deadline:
                    raise TaskTimeoutError(
                        f"Task {name!r} did not reach the running state within "
                        f"{start_timeout} s (last status {status})."
                    )
                time.sleep(poll_interval)

            if on_running is not None:
                on_running()

            # Phase 2: wait for the running task to finish.
            deadline = time.monotonic() + completion_timeout
            while True:
                status = client.task_execute(task, _GET_STATUS)
                if on_poll is not None:
                    on_poll(status)
                if status != TASK_RUN:
                    break
                if completion_timeout > 0 and time.monotonic() >= deadline:
                    try:
                        client.task_stop(task, _INITIALIZED_STOP, "")
                    except Exception:
                        pass
                    raise TaskTimeoutError(
                        f"Task {name!r} did not complete within {completion_timeout} s; "
                        "the task was stopped (initialized stop)."
                    )
                time.sleep(poll_interval)

            if status != TASK_READY:
                raise TaskAbnormalStopError(
                    f"Task {name!r} stopped abnormally instead of completing one "
                    f"cycle (final status {status})."
                )
            return status


def get_task_names(cfg: ControllerConfig) -> list[str]:
    """List the names of all controller tasks."""
    with controller_session(cfg) as (client, ctrl):
        return client.controller_gettasknames(ctrl, "")


def _robot_execute_floats(cfg: ControllerConfig, command: str, robot_name: str = "") -> list[float]:
    """Acquire a robot and return ``robot_execute(robot, command)`` as a float list.

    The robot defaults to the first one reported by the controller. b-CAP pose
    commands ("CurJnt", "CurPos", ...) return a numeric array, which the b-CAP
    client decodes as a Python list; this coerces the elements to ``float``.
    """
    with controller_session(cfg) as (client, ctrl):
        name = _resolve_robot_name(client, ctrl, robot_name)
        with _robot(client, ctrl, name) as robot:
            value = client.robot_execute(robot, command)
    return [float(v) for v in value]


def get_joint_angles(cfg: ControllerConfig, robot_name: str = "") -> list[float]:
    """Return the current joint angles via robot_execute(robot, "CurJnt")."""
    return _robot_execute_floats(cfg, "CurJnt", robot_name)


def get_cartesian_position(cfg: ControllerConfig, robot_name: str = "") -> list[float]:
    """Return the current Cartesian position via robot_execute(robot, "CurPos")."""
    return _robot_execute_floats(cfg, "CurPos", robot_name)
