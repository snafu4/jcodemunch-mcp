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
