"""AgentSystems SDK root package."""

from importlib import metadata as _metadata

__version__ = (
    _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"
)


def help() -> str:
    """Return a short help string confirming the SDK import works."""
    return "AgentSystems SDK imported successfully – CLI available via 'agentsystems'."


__all__ = ["__version__", "help"]
