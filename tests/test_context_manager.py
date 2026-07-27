"""agent.context_manager için testler.

Birim testleri sunucu gerektirmez (mock ile). Özetleme entegrasyon testi
gerçek sunucu gerektirir, yoksa skip edilir.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.context_manager import (
    KEEP_RECENT_MESSAGES,
    estimate_tokens,
    get_context_limit,
    maybe_summarize,
    should_summarize,
    summarize_messages,
)
from tests._server_check import server_available

requires_server = pytest.mark.skipif(
    not server_available(),
    reason="llama-server http://localhost:8079 adresinde çalışmıyor",
)


def test_estimate_tokens_scales_with_content_length() -> None:
    short = [{"role": "user", "content": "a" * 40}]
    long = [{"role": "user", "content": "a" * 4000}]
    assert estimate_tokens(long) > estimate_tokens(short)


def test_estimate_tokens_handles_empty_messages() -> None:
    assert estimate_tokens([]) == 0
    assert estimate_tokens([{"role": "user", "content": ""}]) == 0


def test_should_summarize_false_when_below_threshold() -> None:
    messages = [{"role": "user", "content": "kısa mesaj"}] * (KEEP_RECENT_MESSAGES + 1)
    assert should_summarize(messages, context_limit=100_000) is False


def test_should_summarize_false_when_message_count_is_low() -> None:
    """Mesaj sayısı KEEP_RECENT_MESSAGES'ın altındaysa, token sayısı ne
    olursa olsun özetleme tetiklenmemeli (korunacak çok az mesaj var)."""
    messages = [{"role": "user", "content": "x" * 100_000}]
    assert should_summarize(messages, context_limit=1000) is False


def test_should_summarize_true_when_above_threshold() -> None:
    # Her mesaj ~250 token (1000 karakter / 4). context_limit=1000 ise
    # eşik = 750 token. 6 mesaj * 250 = 1500 token, eşiği aşar.
    messages = [{"role": "user", "content": "a" * 1000}] * (KEEP_RECENT_MESSAGES + 2)
    assert should_summarize(messages, context_limit=1000) is True


def test_get_context_limit_returns_default_on_error() -> None:
    fake_client = MagicMock()
    fake_client.models.list.side_effect = Exception("boom")
    limit = get_context_limit(fake_client, "some-model", default=4096)
    assert limit == 4096


def test_get_context_limit_reads_n_ctx_from_model_meta() -> None:
    fake_model = MagicMock()
    fake_model.id = "my-model"
    fake_model.meta.n_ctx = 65536
    fake_client = MagicMock()
    fake_client.models.list.return_value = MagicMock(data=[fake_model])

    limit = get_context_limit(fake_client, "my-model")
    assert limit == 65536


def test_summarize_messages_preserves_system_and_recent_messages() -> None:
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="Özet: X yapıldı, Y kararlaştırıldı."))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    system_msg = {"role": "system", "content": "Sen yardımcı bir asistansın."}
    old_messages = [{"role": "user", "content": f"eski mesaj {i}"} for i in range(10)]
    recent_messages = [{"role": "user", "content": f"yeni mesaj {i}"} for i in range(KEEP_RECENT_MESSAGES)]
    messages = [system_msg] + old_messages + recent_messages

    result = summarize_messages(fake_client, "fake-model", messages)

    assert result[0] == system_msg
    assert "Özet" in result[1]["content"]
    assert result[-KEEP_RECENT_MESSAGES:] == recent_messages
    assert len(result) == 1 + 1 + KEEP_RECENT_MESSAGES


def test_summarize_messages_noop_when_nothing_to_summarize() -> None:
    fake_client = MagicMock()
    messages = [{"role": "user", "content": "tek mesaj"}]

    result = summarize_messages(fake_client, "fake-model", messages)

    assert result == messages
    fake_client.chat.completions.create.assert_not_called()


def test_maybe_summarize_returns_unchanged_when_not_needed() -> None:
    fake_client = MagicMock()
    messages = [{"role": "user", "content": "kısa"}]

    result = maybe_summarize(fake_client, "fake-model", messages, context_limit=100_000)

    assert result == messages
    fake_client.chat.completions.create.assert_not_called()


def test_maybe_summarize_triggers_summary_when_needed() -> None:
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="özet"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    messages = [{"role": "user", "content": "a" * 1000}] * (KEEP_RECENT_MESSAGES + 2)

    result = maybe_summarize(fake_client, "fake-model", messages, context_limit=1000)

    assert len(result) < len(messages)
    fake_client.chat.completions.create.assert_called_once()


@requires_server
def test_maybe_summarize_end_to_end_with_real_server() -> None:
    """Gerçek sunucuyla: küçük bir context_limit zorlayarak özetlemenin
    gerçekten LLM çağrısı yapıp anlamlı bir özet ürettiğini doğrular."""
    from agent.llm_client import create_client, get_model_id

    client = create_client()
    model_id = get_model_id(client)

    messages = [{"role": "user", "content": f"Bu {i}. mesajdır, dolgu metin. " * 5} for i in range(10)]

    result = maybe_summarize(client, model_id, messages, context_limit=50)

    assert len(result) < len(messages)
    assert any("özet" in (m.get("content") or "").lower() for m in result)
