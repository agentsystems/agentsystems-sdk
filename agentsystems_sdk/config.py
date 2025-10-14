"""Load and validate the `agentsystems-config.yml` marketplace configuration.

This is intentionally lightweight (no pydantic dependency) – we only
validate the fields we currently rely on in the SDK.  The schema can
evolve and remain back-compatible by bumping the `config_version` field
and adding new optional keys.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Any

import yaml

CONFIG_FILENAME = "agentsystems-config.yml"


class IndexConnection:  # pragma: no cover – tiny helper class
    """A single index connection entry from the YAML file."""

    def __init__(self, name: str, data: Dict[str, Any]) -> None:
        self.name: str = name
        self.url: str = data["url"]
        self.enabled: bool = data.get("enabled", False)
        self.description: str = data.get("description", "")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"IndexConnection(name={self.name}, url={self.url}, enabled={self.enabled})"
        )


class Registry:  # pragma: no cover – tiny helper class
    """A single registry entry from the YAML file."""

    def __init__(self, name: str, data: Dict[str, Any]) -> None:
        self.name: str = name
        self.url: str = data["url"]
        self.enabled: bool = data.get("enabled", True)
        self.auth: Dict[str, Any] = data.get("auth", {})

    # Convenience helpers -------------------------------------------------
    def login_method(self) -> str:
        return self.auth.get("method", "none")

    def username_env(self) -> Optional[str]:  # only for basic auth
        return self.auth.get("username_env")

    def password_env(self) -> Optional[str]:  # only for basic auth
        return self.auth.get("password_env")

    def token_env(self) -> Optional[str]:  # bearer / token auth
        return self.auth.get("token_env")

    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"Registry(name={self.name}, url={self.url}, enabled={self.enabled})"


class Agent:
    """Represents an agent container the operator wants to run.

    Two declaration styles are supported:
    1. Explicit *image* string (legacy):
       ```yaml
       - name: foo
         image: docker.io/agentsystems/foo:latest
       ```
    2. Shorthand *repo* / *tag* with *registry* key pointing to `registries` entry:
       ```yaml
       - name: foo
         registry: dockerhub
         repo: agentsystems/foo
         tag: latest  # optional, defaults to latest
       ```
    """

    def __init__(self, data: Dict[str, Any], registries: Dict[str, "Registry"]) -> None:
        # ----- required keys ------------------------------------------------
        try:
            self.name: str = data["name"]
        except KeyError as exc:
            raise ValueError(f"Agent entry missing required key: {exc}") from None

        # ----- declaration variants ----------------------------------------
        if "image" in data:
            # Legacy / explicit image reference
            self.image: str = data["image"]
            self.registry: Optional[str] = data.get("registry")
        else:
            # Shorthand form – need registry + repo, optional tag
            try:
                reg_key: str = data["registry_connection"]
                repo: str = data["repo"]
            except KeyError:
                raise ValueError(
                    f"Agent '{self.name}' must specify 'image' or ('registry_connection' and 'repo')"
                ) from None
            if reg_key not in registries:
                raise ValueError(
                    f"Agent '{self.name}' references unknown registry '{reg_key}'."
                )
            reg_url = registries[reg_key].url.rstrip("/")
            tag = data.get("tag", "latest")
            self.image = f"{reg_url}/{repo}:{tag}"
            self.registry = reg_key

        # ----- optional keys -----------------------------------------------
        self.labels: Dict[str, str] = data.get("labels", {})
        self.overrides: Dict[str, Any] = data.get("overrides", {})
        # List of allowed outbound URL patterns for gateway proxy
        self.egress_allowlist: List[str] = data.get("egress_allowlist", [])

        # ----- artifact permissions -----------------------------------------
        perms: Dict[str, Any] = data.get("artifact_permissions", {})

        # Agents may specify readers/writers as list[str] or "*" wildcard
        def _normalize(val: Any) -> List[str]:
            if val == "*":
                return ["*"]
            return val or []

        self.artifact_readers: List[str] = _normalize(perms.get("readers"))
        self.artifact_writers: List[str] = _normalize(perms.get("writers"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"Agent(name={self.name}, image={self.image})"


class Config:
    """Top-level config object loaded from YAML."""

    def __init__(self, path: pathlib.Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        self.path = path
        self.version: int = raw.get("config_version", 1)

        if self.version != 1:
            raise ValueError(f"Unsupported config_version {self.version}")

        if "registry_connections" not in raw:
            raise ValueError(
                "Config must declare 'registry_connections' at the top level."
            )
        reg_dict = raw["registry_connections"]
        self.registries: Dict[str, Registry] = {
            name: Registry(name, data) for name, data in reg_dict.items()
        }

        # Parse index connections (optional)
        index_dict = raw.get("index_connections", {})
        self.indexes: Dict[str, IndexConnection] = {
            name: IndexConnection(name, data) for name, data in index_dict.items()
        }

        self.agents: List[Agent] = [
            Agent(a, self.registries) for a in raw.get("agents", [])
        ]

        # Basic validation -------------------------------------------------
        # Allow empty registries and agents for clean onboarding experience

    # ------------------------------------------------------------------
    def enabled_registries(self) -> List[Registry]:
        """Return registries flagged as enabled.

        Filters the registries dictionary to return only those
        with enabled=True.
        """
        enabled = [r for r in self.registries.values() if r.enabled]
        return enabled

    # ------------------------------------------------------------------
    def enabled_indexes(self) -> List[IndexConnection]:
        """Return index connections flagged as enabled.

        Filters the indexes dictionary to return only those
        with enabled=True.
        """
        enabled = [idx for idx in self.indexes.values() if idx.enabled]
        return enabled

    # ------------------------------------------------------------------
    def images(self) -> List[str]:
        """List of full image references for all agents.

        Returns a list of fully qualified container image references
        for all configured agents.
        """
        images_list = [agent.image for agent in self.agents]
        return images_list

    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"Config(version={self.version}, registries={list(self.registries)}, indexes={list(self.indexes)}, agents={len(self.agents)})"
