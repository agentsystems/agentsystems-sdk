"""Tests for the agentsystems_sdk package __init__."""

import agentsystems_sdk


def test_help_function():
    """Test the help() function."""
    result = agentsystems_sdk.help()
    assert "AgentSystems SDK imported successfully" in result
    assert "CLI available" in result


def test_version_attribute():
    """Test that __version__ is defined."""
    assert hasattr(agentsystems_sdk, "__version__")
    # Version should be a string
    assert isinstance(agentsystems_sdk.__version__, str)


def test_all_exports():
    """Test that __all__ contains expected exports."""
    assert "__version__" in agentsystems_sdk.__all__
    assert "help" in agentsystems_sdk.__all__


def test_main_execution_version():
    """Test version logic coverage."""
    # Just test that the version is accessible and is a string
    # The actual __main__ case is hard to test without breaking the module
    assert hasattr(agentsystems_sdk, "__version__")
    assert isinstance(agentsystems_sdk.__version__, str)
    assert len(agentsystems_sdk.__version__) > 0
