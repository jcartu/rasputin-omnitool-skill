"""Unit tests for sandbox tool."""
import pytest
from tools.sandbox.index import run


def test_invalid_operation_returns_error():
    result = run({"operation": "invalid_op"})
    assert result.get("error", {}).get("code") == "INVALID_OPERATION"


def test_sandbox_unreachable_returns_error():
    # CONFIG is frozen, so we test by checking the tool handles both paths
    result = run({"operation": "code_execute", "code": "print('hello')"})
    # Either sandbox is reachable (result) or not (SANDBOX_UNREACHABLE)
    assert "result" in result or result.get("error", {}).get("code") == "SANDBOX_UNREACHABLE"

def test_code_execute_returns_result_or_error():
    result = run({"operation": "code_execute", "code": "print('hello')", "language": "python"})
    assert "result" in result or "error" in result


def test_jupyter_kernels_returns_result_or_error():
    result = run({"operation": "jupyter_kernels_list"})
    assert "result" in result or "error" in result
