"""Tests for token tracker behavior and path consistency."""

import importlib.util
import uuid
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "jcodemunch_mcp" / "storage" / "token_tracker.py"


def _load_token_tracker_module():
    module_name = f"token_tracker_module_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


TOKEN_TRACKER = _load_token_tracker_module()


def test_savings_report_uses_code_index_path_env(monkeypatch, tmp_path):
    """When CODE_INDEX_PATH is set, record/report should use the same savings file."""
    monkeypatch.setenv("CODE_INDEX_PATH", str(tmp_path))

    total = TOKEN_TRACKER.record_savings(123)
    report = TOKEN_TRACKER.get_savings_report()

    assert total == 123
    assert report["total_tokens_saved"] == 123
    assert report["savings_file"] == str(tmp_path / "_savings.json")


def test_record_savings_reads_utf8_bom_file(tmp_path):
    """Existing UTF-8 BOM JSON should be readable before incrementing totals."""
    savings_file = tmp_path / "_savings.json"
    savings_file.write_bytes('{"total_tokens_saved": 10}'.encode("utf-8-sig"))

    total = TOKEN_TRACKER.record_savings(5, str(tmp_path))

    assert total == 15
    assert TOKEN_TRACKER.get_total_saved(str(tmp_path)) == 15


def test_record_savings_reads_cp1252_file(tmp_path):
    """Legacy Windows cp1252 JSON should not reset totals on read."""
    savings_file = tmp_path / "_savings.json"
    # Include a cp1252-only byte in anon_id so UTF-8 decode fails.
    savings_file.write_bytes(b'{"total_tokens_saved": 10, "anon_id": "caf\xe9"}')

    total = TOKEN_TRACKER.record_savings(5, str(tmp_path))

    assert total == 15
    assert TOKEN_TRACKER.get_total_saved(str(tmp_path)) == 15


def test_pricing_env_valid_decimal_and_integer(monkeypatch):
    """JCODEMUNCH_*_PRICE accepts integer or decimal numeric values."""
    monkeypatch.setenv("JCODEMUNCH_OPUS_PRICE", "20")
    monkeypatch.setenv("JCODEMUNCH_GPT_PRICE", "7.5")

    module = _load_token_tracker_module()

    assert module.PRICING["claude_opus"] == 20.0 / 1_000_000
    assert module.PRICING["gpt5_latest"] == 7.5 / 1_000_000


def test_pricing_env_invalid_uses_defaults(monkeypatch):
    """Invalid JCODEMUNCH_*_PRICE values should fall back to defaults."""
    monkeypatch.setenv("JCODEMUNCH_OPUS_PRICE", "abc")
    monkeypatch.setenv("JCODEMUNCH_GPT_PRICE", "NaN")

    module = _load_token_tracker_module()

    assert module.PRICING["claude_opus"] == 15.0 / 1_000_000
    assert module.PRICING["gpt5_latest"] == 10.0 / 1_000_000


def test_cost_outputs_are_rounded_to_two_decimals():
    """Cost outputs should be rounded to 2 decimal places."""
    costs = TOKEN_TRACKER.cost_avoided(tokens_saved=333_333, total_tokens_saved=999_999)

    assert costs["cost_avoided"]["claude_opus"] == 5.0
    assert costs["cost_avoided"]["gpt5_latest"] == 3.33
    assert costs["total_cost_avoided"]["claude_opus"] == 15.0
    assert costs["total_cost_avoided"]["gpt5_latest"] == 10.0
