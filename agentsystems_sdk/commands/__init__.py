"""AgentSystems CLI commands."""

from .init import init_command
from .up import up_command
from .down import down_command
from .logs import logs_command
from .restart import restart_command
from .status import status_command
from .run import run_command
from .artifacts import artifacts_path_command
from .clean import clean_command
from .update import update_command
from .version import version_command, versions_command
from .index import index_commands

__all__ = [
    "init_command",
    "up_command",
    "down_command",
    "logs_command",
    "restart_command",
    "status_command",
    "run_command",
    "artifacts_path_command",
    "clean_command",
    "update_command",
    "version_command",
    "versions_command",
    "index_commands",
]
