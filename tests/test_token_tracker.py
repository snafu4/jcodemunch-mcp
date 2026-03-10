"""Tests for token savings persistence."""

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path("src/jcodemunch_mcp/storage/token_tracker.py").resolve()


def _load_tracker(monkeypatch):
    monkeypatch.setenv("JCODEMUNCH_SHARE_SAVINGS", "0")
    module_name = "test_token_tracker_module"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_record_savings_persists_tokens_used(tmp_path, monkeypatch):
    tracker = _load_tracker(monkeypatch)

    total_saved = tracker.record_savings(120, base_path=str(tmp_path), tokens_used=30)
    assert total_saved == 120

    tracker._state.flush()

    data = json.loads((tmp_path / "_savings.json").read_text())
    assert data["total_tokens_saved"] == 120
    assert data["total_tokens_used"] == 30


def test_record_savings_defaults_tokens_used_to_zero(tmp_path, monkeypatch):
    tracker = _load_tracker(monkeypatch)

    (tmp_path / "_savings.json").write_text(json.dumps({"total_tokens_saved": 50}))

    total_saved = tracker.record_savings(10, base_path=str(tmp_path))
    assert total_saved == 60

    tracker._state.flush()

    data = json.loads((tmp_path / "_savings.json").read_text())
    assert data["total_tokens_saved"] == 60
    assert data["total_tokens_used"] == 0
