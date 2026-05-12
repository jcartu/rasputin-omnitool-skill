"""Unit tests for sandbox tool."""
from unittest.mock import MagicMock, patch
from tools.sandbox.index import run


def test_invalid_operation_returns_error():
    result = run({"operation": "invalid_op"})
    assert result.get("error", {}).get("code") == "INVALID_OPERATION"


@patch("httpx.post")
def test_sandbox_unreachable_returns_error(mock_post):
    import httpx
    mock_post.side_effect = httpx.ConnectError("Connection refused")
    result = run({"operation": "code_execute", "code": "print('hello')", "session_id": None})
    assert result.get("error", {}).get("code") == "SANDBOX_UNREACHABLE"


@patch("httpx.post")
def test_code_execute_returns_result(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "stdout": "hello\n",
        "stderr": "",
        "exit_code": 0,
        "artifacts": [],
    }
    mock_post.return_value = mock_response

    result = run({"operation": "code_execute", "code": "print('hello')", "language": "python", "session_id": None})
    assert "result" in result
    assert result["result"]["stdout"] == "hello\n"
    assert result["result"]["exit_code"] == 0


@patch("httpx.get")
def test_jupyter_kernels_returns_result(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"kernelspecs": ["python3", "bash"]}
    mock_get.return_value = mock_response

    result = run({"operation": "jupyter_kernels_list"})
    assert "result" in result
    kernels = [a["name"] for a in result["result"]["artifacts"]]
    assert "python3" in kernels
    assert "bash" in kernels


@patch("httpx.post")
def test_code_execute_5xx_returns_sandbox_unreachable(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_post.return_value = mock_response

    result = run({"operation": "code_execute", "code": "print('hello')", "session_id": None})
    assert result.get("error", {}).get("code") == "SANDBOX_UNREACHABLE"


def test_file_upload_outside_allowed_path():
    result = run({"operation": "file_upload", "file": "/etc/passwd", "session_id": None})
    assert result.get("error", {}).get("code") == "OUTSIDE_ALLOWED_PATH"


@patch("httpx.get")
def test_file_download_returns_result(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"file content"
    mock_get.return_value = mock_response

    result = run({"operation": "file_download", "file": "test.txt", "session_id": None})
    assert "result" in result
    assert len(result["result"]["artifacts"]) == 1
    assert result["result"]["artifacts"][0]["name"] == "test.txt"


@patch("httpx.post")
def test_timeout_returns_error(mock_post):
    import httpx
    mock_post.side_effect = httpx.TimeoutException("Request timed out")
    result = run({"operation": "code_execute", "code": "print('hello')", "session_id": None})
    assert result.get("error", {}).get("code") == "TIMEOUT"
