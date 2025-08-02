"""Test CLI main execution."""

import subprocess
import sys


def test_cli_main_execution():
    """Test that the CLI can be executed as a module."""
    # Run the CLI module as __main__
    result = subprocess.run(
        [sys.executable, "-m", "agentsystems_sdk.cli", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "AgentSystems SDK" in result.stdout
