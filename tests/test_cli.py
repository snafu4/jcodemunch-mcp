"""CLI behavior tests."""

import json

import pytest

from jcodemunch_mcp.server import main


def test_main_help_exits_without_starting_server(capsys):
    """`--help` should print usage and exit cleanly."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "jcodemunch-mcp" in out
    assert "Run the jCodeMunch MCP stdio server" in out


def test_main_version_exits_with_version(capsys):
    """`--version` should print package version and exit cleanly."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("jcodemunch-mcp ")


def test_main_token_stats_outputs_pretty_json(capsys, monkeypatch, tmp_path):
    """`--token-stats` should print enriched savings JSON and exit."""
    monkeypatch.setenv("CODE_INDEX_PATH", str(tmp_path))
    (tmp_path / "_savings.json").write_text(json.dumps({"total_tokens_saved": 12345}))

    main(["--token-stats"])

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["total_tokens_saved"] == 12345
    assert parsed["equivalent_context_windows"]["32k"] > 0


def test_main_token_stats_json_outputs_compact_json(capsys, monkeypatch, tmp_path):
    """`--token-stats-json` should print compact JSON and exit."""
    monkeypatch.setenv("CODE_INDEX_PATH", str(tmp_path))
    (tmp_path / "_savings.json").write_text(json.dumps({"total_tokens_saved": 42}))

    main(["--token-stats-json"])

    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["total_tokens_saved"] == 42
    assert "\n" not in out


def test_main_token_stats_text_outputs_human_readable(capsys, monkeypatch, tmp_path):
    """`--token-stats-text` should print readable text and exit."""
    monkeypatch.setenv("CODE_INDEX_PATH", str(tmp_path))
    (tmp_path / "_savings.json").write_text(json.dumps({"total_tokens_saved": 98765}))

    main(["--token-stats-text"])

    out = capsys.readouterr().out
    assert "jCodeMunch Token Savings" in out
    assert "Total tokens saved: 98,765" in out
    assert "Savings file:" in out
