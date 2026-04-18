"""Tests for model id normalization + tier resolution."""

import pytest

from jcodemunch_mcp.tier_resolver import normalize_model_id


class TestNormalizeModelId:
    def test_lowercase(self):
        assert normalize_model_id("Claude-Opus") == "claude-opus"

    def test_strip_double_provider_prefix(self):
        assert normalize_model_id("openrouter/anthropic/claude-opus-4-7") == "claude-opus-4-7"

    def test_strip_single_provider_prefix(self):
        assert normalize_model_id("anthropic/claude-haiku-4-5") == "claude-haiku-4-5"

    def test_strip_bracket_suffix(self):
        assert normalize_model_id("claude-opus-4-7[1m]") == "claude-opus-4-7"

    def test_strip_bracket_beta(self):
        assert normalize_model_id("claude-sonnet-4-6[beta]") == "claude-sonnet-4-6"

    def test_strip_date_suffix(self):
        assert normalize_model_id("claude-haiku-4-5-20251001") == "claude-haiku-4-5"

    def test_strip_combined(self):
        assert normalize_model_id("anthropic/claude-opus-4-7[1m]") == "claude-opus-4-7"

    def test_empty_string(self):
        assert normalize_model_id("") == ""

    def test_whitespace_trimmed(self):
        assert normalize_model_id("  claude-opus  ") == "claude-opus"

    def test_non_string_returns_empty(self):
        assert normalize_model_id(None) == ""  # type: ignore[arg-type]
        assert normalize_model_id(123) == ""  # type: ignore[arg-type]
