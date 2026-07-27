"""agent.system_prompt için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

from agent.system_prompt import SYSTEM_PROMPT, build_initial_messages


def test_build_initial_messages_adds_system_prompt_when_empty() -> None:
    messages = build_initial_messages()
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_build_initial_messages_prepends_to_existing_messages() -> None:
    existing = [{"role": "user", "content": "merhaba"}]
    messages = build_initial_messages(existing)
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "merhaba"}


def test_build_initial_messages_does_not_duplicate_system_message() -> None:
    existing = [{"role": "system", "content": "özel bir prompt"}, {"role": "user", "content": "merhaba"}]
    messages = build_initial_messages(existing)
    system_messages = [m for m in messages if m["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"] == "özel bir prompt"


def test_system_prompt_mentions_key_behavioral_rules() -> None:
    """K9'un öncelikli hedefi (döngüye girmeden durma) ve K7/K8'in onay
    kuralı sistem promptunda açıkça yer almalı."""
    assert "döngüye girme" in SYSTEM_PROMPT.lower() or "durup kullanıcıya" in SYSTEM_PROMPT.lower()
    assert "onay" in SYSTEM_PROMPT.lower()
    assert "edit_file" in SYSTEM_PROMPT
    assert "run_shell" in SYSTEM_PROMPT
