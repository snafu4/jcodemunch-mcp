"""Tests for summarizer module."""

import pytest
from unittest.mock import MagicMock, patch
from jcodemunch_mcp.parser import Symbol
from jcodemunch_mcp.summarizer import (
    extract_summary_from_docstring,
    signature_fallback,
    summarize_symbols_simple,
    GeminiBatchSummarizer,
)


def test_extract_summary_from_docstring_simple():
    """Test extracting first sentence from docstring."""
    doc = "Do something cool.\n\nMore details here."
    assert extract_summary_from_docstring(doc) == "Do something cool."


def test_extract_summary_from_docstring_no_period():
    """Test extracting summary without period."""
    doc = "Do something cool"
    assert extract_summary_from_docstring(doc) == "Do something cool"


def test_extract_summary_from_docstring_empty():
    """Test extracting from empty docstring."""
    assert extract_summary_from_docstring("") == ""
    assert extract_summary_from_docstring("   ") == ""


def test_signature_fallback_function():
    """Test signature fallback for functions."""
    sym = Symbol(
        id="test::foo",
        file="test.py",
        name="foo",
        qualified_name="foo",
        kind="function",
        language="python",
        signature="def foo(x: int) -> str:",
    )
    assert signature_fallback(sym) == "def foo(x: int) -> str:"


def test_signature_fallback_class():
    """Test signature fallback for classes."""
    sym = Symbol(
        id="test::MyClass",
        file="test.py",
        name="MyClass",
        qualified_name="MyClass",
        kind="class",
        language="python",
        signature="class MyClass(Base):",
    )
    assert signature_fallback(sym) == "Class MyClass"


def test_signature_fallback_constant():
    """Test signature fallback for constants."""
    sym = Symbol(
        id="test::MAX_SIZE",
        file="test.py",
        name="MAX_SIZE",
        qualified_name="MAX_SIZE",
        kind="constant",
        language="python",
        signature="MAX_SIZE = 100",
    )
    assert signature_fallback(sym) == "Constant MAX_SIZE"


def test_simple_summarize_uses_docstring():
    """Test that summarize uses docstring when available."""
    symbols = [
        Symbol(
            id="test::foo",
            file="test.py",
            name="foo",
            qualified_name="foo",
            kind="function",
            language="python",
            signature="def foo():",
            docstring="Does something useful.",
        )
    ]
    
    result = summarize_symbols_simple(symbols)
    assert result[0].summary == "Does something useful."


def test_simple_summarize_fallback_to_signature():
    """Test fallback to signature when no docstring."""
    symbols = [
        Symbol(
            id="test::foo",
            file="test.py",
            name="foo",
            qualified_name="foo",
            kind="function",
            language="python",
            signature="def foo(x: int) -> str:",
            docstring="",
        )
    ]

    result = summarize_symbols_simple(symbols)
    assert "def foo" in result[0].summary


def test_gemini_summarizer_no_api_key():
    """GeminiBatchSummarizer falls back to signature when no API key is set."""
    with patch.dict("os.environ", {}, clear=True):
        summarizer = GeminiBatchSummarizer()
        assert summarizer.client is None

    symbols = [
        Symbol(
            id="test::bar",
            file="test.py",
            name="bar",
            qualified_name="bar",
            kind="function",
            language="python",
            signature="def bar():",
        )
    ]
    summarizer.summarize_batch(symbols)
    assert symbols[0].summary == "def bar():"


def test_gemini_summarizer_with_mock_client():
    """GeminiBatchSummarizer uses Gemini response when client is available."""
    mock_response = MagicMock()
    mock_response.text = "1. Computes the sum of two integers."

    mock_client = MagicMock()
    mock_client.generate_content.return_value = mock_response

    summarizer = GeminiBatchSummarizer()
    summarizer.client = mock_client

    symbols = [
        Symbol(
            id="test::add",
            file="test.py",
            name="add",
            qualified_name="add",
            kind="function",
            language="python",
            signature="def add(a: int, b: int) -> int:",
        )
    ]
    summarizer.summarize_batch(symbols)
    assert symbols[0].summary == "Computes the sum of two integers."

