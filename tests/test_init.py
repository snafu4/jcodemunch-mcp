"""Tests for jcodemunch-mcp init command."""

import json
import os
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from jcodemunch_mcp.cli.init import (
    MCPClient,
    _detect_clients,
    _has_jcodemunch_entry,
    _patch_mcp_config,
    _read_json,
    _write_json,
    configure_client,
    install_claude_md,
    install_hooks,
    run_init,
    _CLAUDE_MD_MARKER,
    _CLAUDE_MD_POLICY,
    _MCP_ENTRY,
)


# ---------------------------------------------------------------------------
# _read_json / _write_json
# ---------------------------------------------------------------------------

def test_read_json_missing(tmp_path):
    assert _read_json(tmp_path / "nope.json") == {}


def test_read_json_invalid(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json", encoding="utf-8")
    assert _read_json(f) == {}


def test_read_write_json_roundtrip(tmp_path):
    f = tmp_path / "test.json"
    data = {"foo": "bar", "nested": {"a": 1}}
    _write_json(f, data, backup=False)
    assert _read_json(f) == data


def test_write_json_creates_backup(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text('{"old": true}', encoding="utf-8")
    _write_json(f, {"new": True}, backup=True)
    bak = f.with_suffix(".json.bak")
    assert bak.exists()
    assert json.loads(bak.read_text(encoding="utf-8")) == {"old": True}
    assert json.loads(f.read_text(encoding="utf-8")) == {"new": True}


def test_write_json_creates_parent_dirs(tmp_path):
    f = tmp_path / "a" / "b" / "c.json"
    _write_json(f, {"x": 1}, backup=False)
    assert f.exists()


# ---------------------------------------------------------------------------
# _has_jcodemunch_entry / _patch_mcp_config
# ---------------------------------------------------------------------------

def test_has_jcodemunch_entry_false():
    assert not _has_jcodemunch_entry({})
    assert not _has_jcodemunch_entry({"mcpServers": {"other": {}}})


def test_has_jcodemunch_entry_true():
    assert _has_jcodemunch_entry({"mcpServers": {"jcodemunch": {}}})


def test_patch_mcp_config_new(tmp_path):
    f = tmp_path / "mcp.json"
    msg = _patch_mcp_config(f, backup=False)
    assert "added" in msg
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["mcpServers"]["jcodemunch"] == _MCP_ENTRY


def test_patch_mcp_config_existing_servers(tmp_path):
    f = tmp_path / "mcp.json"
    f.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    _patch_mcp_config(f, backup=False)
    data = json.loads(f.read_text(encoding="utf-8"))
    assert "other" in data["mcpServers"]
    assert "jcodemunch" in data["mcpServers"]


def test_patch_mcp_config_already_present(tmp_path):
    f = tmp_path / "mcp.json"
    f.write_text(json.dumps({"mcpServers": {"jcodemunch": {}}}), encoding="utf-8")
    msg = _patch_mcp_config(f, backup=False)
    assert "already" in msg


def test_patch_mcp_config_dry_run(tmp_path):
    f = tmp_path / "mcp.json"
    msg = _patch_mcp_config(f, backup=False, dry_run=True)
    assert "would" in msg
    assert not f.exists()


# ---------------------------------------------------------------------------
# configure_client
# ---------------------------------------------------------------------------

def test_configure_client_json_patch(tmp_path):
    client = MCPClient("Test", tmp_path / "mcp.json", "json_patch")
    msg = configure_client(client, backup=False)
    assert "added" in msg


def test_configure_client_cli_dry_run():
    client = MCPClient("Claude Code", None, "cli")
    msg = configure_client(client, dry_run=True)
    assert "would run" in msg


@patch("jcodemunch_mcp.cli.init.subprocess.run")
def test_configure_client_cli_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
    client = MCPClient("Claude Code", None, "cli")
    msg = configure_client(client, dry_run=False)
    assert "ran" in msg
    mock_run.assert_called_once()


@patch("jcodemunch_mcp.cli.init.subprocess.run")
def test_configure_client_cli_already_exists(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="Server already exists", stdout="")
    client = MCPClient("Claude Code", None, "cli")
    msg = configure_client(client, dry_run=False)
    assert "already" in msg


# ---------------------------------------------------------------------------
# install_claude_md
# ---------------------------------------------------------------------------

def test_install_claude_md_new(tmp_path, monkeypatch):
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: tmp_path / "CLAUDE.md")
    msg = install_claude_md("global")
    assert "appended" in msg
    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert _CLAUDE_MD_MARKER in content


def test_install_claude_md_appends(tmp_path, monkeypatch):
    f = tmp_path / "CLAUDE.md"
    f.write_text("# Existing content\n", encoding="utf-8")
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: f)
    install_claude_md("project", backup=False)
    content = f.read_text(encoding="utf-8")
    assert content.startswith("# Existing content")
    assert _CLAUDE_MD_MARKER in content


def test_install_claude_md_idempotent(tmp_path, monkeypatch):
    f = tmp_path / "CLAUDE.md"
    f.write_text(_CLAUDE_MD_POLICY, encoding="utf-8")
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: f)
    msg = install_claude_md("global")
    assert "already" in msg


def test_install_claude_md_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: tmp_path / "CLAUDE.md")
    msg = install_claude_md("global", dry_run=True)
    assert "would" in msg
    assert not (tmp_path / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# install_hooks
# ---------------------------------------------------------------------------

def test_install_hooks_new(tmp_path, monkeypatch):
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: tmp_path / "settings.json")
    msg = install_hooks(backup=False)
    assert "WorktreeCreate" in msg
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "WorktreeCreate" in data["hooks"]
    assert "WorktreeRemove" in data["hooks"]


def test_install_hooks_merge_existing(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({
        "hooks": {
            "SomeOther": [{"matcher": "", "hooks": []}],
        }
    }), encoding="utf-8")
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: f)
    install_hooks(backup=False)
    data = json.loads(f.read_text(encoding="utf-8"))
    assert "SomeOther" in data["hooks"]
    assert "WorktreeCreate" in data["hooks"]


def test_install_hooks_idempotent(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: f)
    install_hooks(backup=False)
    msg = install_hooks(backup=False)
    assert "already" in msg


def test_install_hooks_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: tmp_path / "settings.json")
    msg = install_hooks(dry_run=True)
    assert "would" in msg
    assert not (tmp_path / "settings.json").exists()


# ---------------------------------------------------------------------------
# run_init (non-interactive --yes mode)
# ---------------------------------------------------------------------------

def test_run_init_dry_run_yes(tmp_path, monkeypatch, capsys):
    """Full dry-run with --yes should print actions without modifying anything."""
    monkeypatch.setattr("jcodemunch_mcp.cli.init._detect_clients", lambda: [
        MCPClient("TestClient", tmp_path / "mcp.json", "json_patch"),
    ])
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: tmp_path / "CLAUDE.md")
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: tmp_path / "settings.json")

    rc = run_init(dry_run=True, yes=True)
    assert rc == 0

    out = capsys.readouterr().out
    assert "would" in out
    assert "Dry run" in out
    # No files should be created
    assert not (tmp_path / "mcp.json").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_run_init_full_yes(tmp_path, monkeypatch, capsys):
    """Full run with --yes should configure everything."""
    monkeypatch.setattr("jcodemunch_mcp.cli.init._detect_clients", lambda: [
        MCPClient("TestClient", tmp_path / "mcp.json", "json_patch"),
    ])
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: tmp_path / "CLAUDE.md")
    monkeypatch.setattr("jcodemunch_mcp.cli.init._settings_json_path", lambda: tmp_path / "settings.json")

    rc = run_init(yes=True, no_backup=True)
    assert rc == 0

    # MCP config created
    assert (tmp_path / "mcp.json").exists()
    data = json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))
    assert "jcodemunch" in data["mcpServers"]

    # CLAUDE.md created
    assert (tmp_path / "CLAUDE.md").exists()
    assert _CLAUDE_MD_MARKER in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


def test_run_init_explicit_client_none(tmp_path, monkeypatch, capsys):
    """--client none should skip client configuration."""
    monkeypatch.setattr("jcodemunch_mcp.cli.init._detect_clients", lambda: [
        MCPClient("TestClient", tmp_path / "mcp.json", "json_patch"),
    ])
    monkeypatch.setattr("jcodemunch_mcp.cli.init._claude_md_path", lambda scope: tmp_path / "CLAUDE.md")

    rc = run_init(clients=["none"], claude_md="global", yes=True, no_backup=True)
    assert rc == 0
    assert not (tmp_path / "mcp.json").exists()


# ---------------------------------------------------------------------------
# _detect_clients smoke test
# ---------------------------------------------------------------------------

def test_detect_clients_returns_list():
    """Detection should return a list (may be empty in CI)."""
    result = _detect_clients()
    assert isinstance(result, list)
    for c in result:
        assert isinstance(c, MCPClient)
        assert c.name
        assert c.method in ("cli", "json_patch")
