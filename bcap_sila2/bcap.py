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

from contextlib import contextmanager
from typing import Any, Iterator, Tuple

from bcapclient import BCAPClient

from .config import ControllerConfig


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


def start_task(cfg: ControllerConfig, name: str, mode: int = 1) -> None:
    """Start a controller task by name (default: one-cycle mode)."""
    with controller_session(cfg) as (client, ctrl):
        with _task(client, ctrl, name) as task:
            client.task_start(task, mode, "")


def get_task_names(cfg: ControllerConfig) -> list[str]:
    """List the names of all controller tasks."""
    with controller_session(cfg) as (client, ctrl):
        return client.controller_gettasknames(ctrl, "")
