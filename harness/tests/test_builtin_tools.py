from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aegis_harness.tools.calculator import CalculatorTool
from aegis_harness.tools.delete_database import DeleteDatabaseTool
from aegis_harness.tools.http_get import HttpGetTool
from aegis_harness.tools.read_file import (
    PathEscapesSandboxError,
    ReadFileTool,
    resolve_within_sandbox,
)
from aegis_harness.tools.search_docs import SearchDocsTool
from aegis_harness.tools.send_email import SendEmailTool
from aegis_harness.tools.write_file import WriteFileTool


def test_search_docs_finds_match():
    tool = SearchDocsTool()
    result = tool.execute({"query": "onboarding"})
    assert "agent-gate" in result


def test_search_docs_no_match():
    tool = SearchDocsTool()
    result = tool.execute({"query": "nonexistent-keyword-xyz"})
    assert "No documents matched" in result


def test_search_docs_empty_query():
    tool = SearchDocsTool()
    assert "No query" in tool.execute({})


def test_send_email_writes_to_sandboxed_outbox(tmp_path: Path):
    outbox = tmp_path / "outbox.jsonl"
    tool = SendEmailTool(outbox_path=outbox)
    result = tool.execute({"to": "a@b.com", "subject": "hi", "body": "hello"})
    assert "Queued email to a@b.com" in result
    assert outbox.exists()
    content = outbox.read_text()
    assert "a@b.com" in content
    assert "hello" in content


def test_send_email_requires_to(tmp_path: Path):
    tool = SendEmailTool(outbox_path=tmp_path / "outbox.jsonl")
    result = tool.execute({"subject": "hi"})
    assert "Error" in result
    assert not (tmp_path / "outbox.jsonl").exists()


def test_delete_database_deletes_sandboxed_file(tmp_path: Path):
    sandbox_file = tmp_path / "fake_db.txt"
    sandbox_file.parent.mkdir(parents=True, exist_ok=True)
    sandbox_file.write_text("pretend data")
    tool = DeleteDatabaseTool(sandbox_path=sandbox_file)

    result = tool.execute({"database_name": "prod"})
    assert "Deleted" in result
    assert not sandbox_file.exists()


def test_delete_database_idempotent_when_already_gone(tmp_path: Path):
    sandbox_file = tmp_path / "fake_db.txt"
    tool = DeleteDatabaseTool(sandbox_path=sandbox_file)
    result = tool.execute({"database_name": "prod"})
    assert "no sandboxed placeholder" in result


def test_delete_database_requires_name(tmp_path: Path):
    tool = DeleteDatabaseTool(sandbox_path=tmp_path / "fake_db.txt")
    result = tool.execute({})
    assert "Error" in result


# --- calculator (phase 2) ------------------------------------------------


def test_calculator_basic_arithmetic():
    tool = CalculatorTool()
    result = tool.execute({"expression": "(3 + 4) * 2"})
    assert result == "(3 + 4) * 2 = 14"


def test_calculator_division_by_zero():
    tool = CalculatorTool()
    result = tool.execute({"expression": "1 / 0"})
    assert "Error: division by zero" in result


def test_calculator_rejects_non_arithmetic_syntax():
    tool = CalculatorTool()
    # the exact attack this tool exists to refuse -- eval() would run this
    result = tool.execute({"expression": "__import__('os').system('echo pwned')"})
    assert result.startswith("Error:")


def test_calculator_requires_expression():
    tool = CalculatorTool()
    assert "Error" in tool.execute({})


# --- read_file / write_file sandbox containment (phase 2) ---------------


def test_write_then_read_file_round_trip(tmp_path: Path):
    write_tool = WriteFileTool(sandbox_root=tmp_path)
    read_tool = ReadFileTool(sandbox_root=tmp_path)

    write_result = write_tool.execute({"path": "notes.txt", "content": "hello sandbox"})
    assert "Created 'notes.txt'" in write_result

    read_result = read_tool.execute({"path": "notes.txt"})
    assert read_result == "hello sandbox"


def test_write_file_reports_overwrite_vs_create(tmp_path: Path):
    tool = WriteFileTool(sandbox_root=tmp_path)
    first = tool.execute({"path": "a.txt", "content": "v1"})
    second = tool.execute({"path": "a.txt", "content": "v2"})
    assert "Created 'a.txt'" in first
    assert "Overwrote 'a.txt'" in second


def test_read_file_missing_file(tmp_path: Path):
    tool = ReadFileTool(sandbox_root=tmp_path)
    result = tool.execute({"path": "does-not-exist.txt"})
    assert "does not exist" in result


def test_read_file_rejects_path_traversal_outside_sandbox(tmp_path: Path):
    tool = ReadFileTool(sandbox_root=tmp_path)
    result = tool.execute({"path": "../../etc/passwd"})
    assert "resolves outside the sandbox root" in result


def test_write_file_rejects_path_traversal_outside_sandbox(tmp_path: Path):
    tool = WriteFileTool(sandbox_root=tmp_path)
    result = tool.execute({"path": "../escape.txt", "content": "x"})
    assert "resolves outside the sandbox root" in result
    # the file must genuinely not have been created anywhere
    assert not (tmp_path.parent / "escape.txt").exists()


def test_read_file_rejects_absolute_path_traversal(tmp_path: Path):
    tool = ReadFileTool(sandbox_root=tmp_path)
    result = tool.execute({"path": "/etc/passwd"})
    assert "resolves outside the sandbox root" in result


def test_resolve_within_sandbox_allows_nested_subdirectories(tmp_path: Path):
    # a legitimate nested path must still work -- containment shouldn't
    # be so strict it breaks ordinary subdirectory usage
    target = resolve_within_sandbox(tmp_path, "sub/dir/file.txt")
    assert target == (tmp_path / "sub" / "dir" / "file.txt").resolve()


def test_resolve_within_sandbox_raises_on_escape(tmp_path: Path):
    with pytest.raises(PathEscapesSandboxError):
        resolve_within_sandbox(tmp_path, "../outside.txt")


def test_read_file_requires_path(tmp_path: Path):
    tool = ReadFileTool(sandbox_root=tmp_path)
    assert "Error" in tool.execute({})


def test_write_file_requires_path(tmp_path: Path):
    tool = WriteFileTool(sandbox_root=tmp_path)
    assert "Error" in tool.execute({"content": "x"})


# --- http_get (phase 2) --------------------------------------------------


def test_http_get_rejects_disallowed_domain():
    tool = HttpGetTool(allowed_domains=["example.com"])
    result = tool.execute({"url": "https://evil.example.org/steal"})
    assert "is not on the allowed domain list" in result


def test_http_get_rejects_non_https_scheme():
    tool = HttpGetTool(allowed_domains=["example.com"])
    result = tool.execute({"url": "http://example.com/"})
    assert "only https:// URLs are allowed" in result


def test_http_get_requires_url():
    tool = HttpGetTool()
    assert "Error" in tool.execute({})


def test_http_get_default_allowlist_is_example_com_only():
    tool = HttpGetTool()
    result = tool.execute({"url": "https://not-example.com/"})
    assert "is not on the allowed domain list" in result


@patch("aegis_harness.tools.http_get.httpx.get")
def test_http_get_allowed_domain_returns_body(mock_get: Mock):
    mock_get.return_value = Mock(status_code=200, text="hello from example.com")
    tool = HttpGetTool(allowed_domains=["example.com"])

    result = tool.execute({"url": "https://example.com/"})

    assert "HTTP 200 from example.com" in result
    assert "hello from example.com" in result
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["follow_redirects"] is False


@patch("aegis_harness.tools.http_get.httpx.get")
def test_http_get_truncates_long_response(mock_get: Mock):
    mock_get.return_value = Mock(status_code=200, text="x" * 5000)
    tool = HttpGetTool(allowed_domains=["example.com"])

    result = tool.execute({"url": "https://example.com/"})

    assert "[truncated]" in result
    assert len(result) < 5000
