from __future__ import annotations

from pathlib import Path

from aegis_harness.tools.delete_database import DeleteDatabaseTool
from aegis_harness.tools.search_docs import SearchDocsTool
from aegis_harness.tools.send_email import SendEmailTool


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
