import json
from pathlib import Path

from jcodemunch_mcp.stats_app import build_stats_payload


def test_build_stats_payload_reads_saved_totals(tmp_path: Path) -> None:
    savings_file = tmp_path / "_savings.json"
    savings_file.write_text(json.dumps({"total_tokens_saved": 120, "anon_id": "abc"}), encoding="utf-8")

    payload = build_stats_payload(str(tmp_path))

    assert payload["total_tokens_saved"] == 120
    assert payload["approx_raw_bytes_avoided"] == 480
    assert payload["anon_id_present"] is True
    assert "generated_at" in payload
    assert payload["savings_file"].endswith("_savings.json")


def test_build_stats_payload_price_env_overrides(monkeypatch, tmp_path: Path) -> None:
    savings_file = tmp_path / "_savings.json"
    savings_file.write_text(json.dumps({"total_tokens_saved": 1000000}), encoding="utf-8")
    monkeypatch.setenv("JCODEMUNCH_OPUS_PRICE", "0.00002")
    monkeypatch.setenv("JCODEMUNCH_GPT_PRICE", "0.00003")

    payload = build_stats_payload(str(tmp_path))

    assert payload["pricing_usd_per_token"]["claude_opus"] == 0.00002
    assert payload["pricing_usd_per_token"]["gpt5_latest"] == 0.00003
    assert payload["total_cost_avoided"]["claude_opus"] == 20.0
    assert payload["total_cost_avoided"]["gpt5_latest"] == 30.0


def test_build_stats_payload_invalid_price_env_falls_back(monkeypatch, tmp_path: Path) -> None:
    savings_file = tmp_path / "_savings.json"
    savings_file.write_text(json.dumps({"total_tokens_saved": 1000000}), encoding="utf-8")
    monkeypatch.setenv("JCODEMUNCH_OPUS_PRICE", "abc")
    monkeypatch.setenv("JCODEMUNCH_GPT_PRICE", "-1")

    payload = build_stats_payload(str(tmp_path))

    assert payload["pricing_usd_per_token"]["claude_opus"] == 15.00 / 1_000_000
    assert payload["pricing_usd_per_token"]["gpt5_latest"] == 10.00 / 1_000_000
