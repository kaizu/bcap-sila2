"""Server configuration loaded from a TOML file.

Controller connection parameters (host, port, timeout, type, provider, machine,
option) are supplied at startup via a TOML file rather than as SiLA command
parameters, so the commands stay free of connection details.
"""

from __future__ import annotations

import dataclasses
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when the configuration file is missing, invalid, or incomplete."""


DEFAULT_CONTROLLER_TYPE = "RC9"

# Known controller types -> default b-CAP provider string.
# Only RC9 is confirmed; for other types the provider must be set explicitly.
_PROVIDER_BY_TYPE = {
    "RC9": "CaoProv.DENSO.VRC9",
}


@dataclass
class ControllerConfig:
    """b-CAP connection parameters for the robot controller."""

    host: str
    port: int
    timeout: float = 5.0
    type: str = DEFAULT_CONTROLLER_TYPE
    name: str = "b-CAP"
    provider: str = ""
    machine: str = "localhost"
    option: str = ""

    def __post_init__(self) -> None:
        # Derive the provider from the controller type when not given explicitly.
        if not self.provider:
            try:
                self.provider = _PROVIDER_BY_TYPE[self.type]
            except KeyError:
                raise ConfigError(
                    f"No default provider known for controller type {self.type!r}; "
                    "set [controller].provider explicitly in the configuration file."
                )


@dataclass
class TaskConfig:
    """Task execution settings."""

    # v1: RunTask only starts the task and waits this fixed interval before
    # completing (placeholder for future real completion detection).
    run_wait_seconds: float = 10.0


@dataclass
class ServerConfig:
    """SiLA server listening settings."""

    host: str = "0.0.0.0"
    port: int = 50052


@dataclass
class Config:
    controller: ControllerConfig
    task: TaskConfig = field(default_factory=TaskConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def _build(cls: type, data: dict[str, Any], section: str) -> Any:
    """Construct a config dataclass, rejecting unknown keys to catch typos."""
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(
            f"Unknown key(s) in [{section}]: {', '.join(sorted(unknown))}"
        )
    return cls(**data)


def load_config(path: str | Path) -> Config:
    """Load and validate the server configuration from a TOML file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    with path.open("rb") as f:
        data: dict[str, Any] = tomllib.load(f)

    controller_data = data.get("controller")
    if not isinstance(controller_data, dict):
        raise ConfigError("Missing required [controller] section in configuration file.")
    for key in ("host", "port"):
        if key not in controller_data:
            raise ConfigError(
                f"Missing required [controller].{key} in configuration file."
            )

    controller = _build(ControllerConfig, controller_data, "controller")
    task = _build(TaskConfig, data.get("task", {}), "task")
    server = _build(ServerConfig, data.get("server", {}), "server")
    return Config(controller=controller, task=task, server=server)
