"""agent.tool_parsing için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

from agent.tool_parsing import extract_tool_call_from_content


def test_extracts_from_markdown_json_block() -> None:
    content = '```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    result = extract_tool_call_from_content(content)
    assert result == {"name": "read_file", "arguments": {"path": "a.py"}}


def test_extracts_from_tools_tag() -> None:
    content = '<tools>{"name": "read_file", "arguments": {"path": "a.py"}}</tools>'
    result = extract_tool_call_from_content(content)
    assert result == {"name": "read_file", "arguments": {"path": "a.py"}}


def test_extracts_from_call_tag() -> None:
    content = '<call>{"name": "read_file", "arguments": {"path": "a.py"}}</call>'
    result = extract_tool_call_from_content(content)
    assert result == {"name": "read_file", "arguments": {"path": "a.py"}}


def test_returns_none_for_plain_text() -> None:
    assert extract_tool_call_from_content("Merhaba, nasıl yardımcı olabilirim?") is None


def test_returns_none_for_empty_content() -> None:
    assert extract_tool_call_from_content("") is None
    assert extract_tool_call_from_content(None) is None  # type: ignore[arg-type]


def test_returns_none_for_invalid_json_in_block() -> None:
    content = "```json\n{invalid json}\n```"
    assert extract_tool_call_from_content(content) is None


def test_returns_none_when_missing_required_keys() -> None:
    content = '```json\n{"foo": "bar"}\n```'
    assert extract_tool_call_from_content(content) is None
