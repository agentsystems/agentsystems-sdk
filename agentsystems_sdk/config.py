"""Load and validate the `agentsystems-config.yml` marketplace configuration.

This is intentionally lightweight (no pydantic dependency) – we only
validate the fields we currently rely on in the SDK.  The schema can
evolve and remain back-compatible by bumping the `config_version` field
and adding new optional keys.
"""
from __future__ import annotations

import os
import pathlib
from typing import Dict, List

import yaml

CONFIG_FILENAME = "agentsystems-config.yml"


class Registry:  # pragma: no cover – tiny helper class
    """A single registry entry from the YAML file."""

    def __init__(self, name: str, data: Dict):
        self.name: str = name
        self.url: str = data["url"]
        self.enabled: bool = data.get("enabled", True)
        self.auth: Dict = data.get("auth", {})

    # Convenience helpers -------------------------------------------------
    def login_method(self) -> str:
        return self.auth.get("method", "none")

    def username_env(self) -> str | None:  # only for basic auth
        return self.auth.get("username_env")

    def password_env(self) -> str | None:  # only for basic auth
        return self.auth.get("password_env")

    def token_env(self) -> str | None:  # bearer / token auth
        return self.auth.get("token_env")

    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"Registry(name={self.name}, url={self.url}, enabled={self.enabled})"


class Agent:
    """Represents an agent container the operator wants to run."""

    def __init__(self, data: Dict):
        try:
            self.name: str = data["name"]
            self.image: str = data["image"]
        except KeyError as exc:
            raise ValueError(f"Agent entry missing required key: {exc}") from None
        self.registry: str | None = data.get("registry")  # optional – may be implicit
        self.labels: Dict[str, str] = data.get("labels", {})
        self.overrides: Dict = data.get("overrides", {})

    def __repr__(self) -> str:  # pragma: no cover
        return f"Agent(name={self.name}, image={self.image})"


class Config:
    """Top-level config object loaded from YAML."""

    def __init__(self, path: pathlib.Path):
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        self.path = path
        self.version: int = raw.get("config_version", 1)

        if self.version != 1:
            raise ValueError(f"Unsupported config_version {self.version}")

        reg_dict = raw.get("registries", {})
        self.registries: Dict[str, Registry] = {name: Registry(name, data) for name, data in reg_dict.items()}
        self.agents: List[Agent] = [Agent(a) for a in raw.get("agents", [])]

        # Basic validation -------------------------------------------------
        if not self.registries:
            raise ValueError("Config must declare at least one registry under 'registries'.")
        if not self.agents:
            raise ValueError("Config must declare at least one agent under 'agents'.")

    # ------------------------------------------------------------------
    def enabled_registries(self) -> List[Registry]:
        """Return registries flagged as enabled."""
        return [r for r in self.registries.values() if r.enabled]

    # ------------------------------------------------------------------
    def images(self) -> List[str]:
        """List of full image references for all agents."""
        return [agent.image for agent in self.agents]

    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"Config(version={self.version}, registries={list(self.registries)}, agents={len(self.agents)})"
