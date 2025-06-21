"""AgentSystems SDK root package."""
from importlib import metadata as _metadata

__version__ = _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"

__all__ = ["__version__"]
