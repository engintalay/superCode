"""agent.llm_client için entegrasyon testleri.

llama-server çalışmıyorsa testler skip edilir (bkz. PROGRESS.md - Task 1
gereksinimi: "server yoksa skip").
"""

from __future__ import annotations

import httpx
import pytest

from agent.llm_client import DEFAULT_BASE_URL, chat, create_client, get_model_id


def _server_available() -> bool:
    try:
        httpx.get(f"{DEFAULT_BASE_URL}/models", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


requires_server = pytest.mark.skipif(
    not _server_available(),
    reason="llama-server http://localhost:8080 adresinde çalışmıyor",
)


@requires_server
def test_get_model_id_returns_nonempty_string() -> None:
    client = create_client()
    model_id = get_model_id(client)
    assert isinstance(model_id, str)
    assert model_id != ""


@requires_server
def test_chat_returns_nonempty_reply() -> None:
    reply = chat("merhaba de")
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
