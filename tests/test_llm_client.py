"""agent.llm_client için entegrasyon testleri.

llama-server çalışmıyorsa testler skip edilir (bkz. PROGRESS.md - Task 1
gereksinimi: "server yoksa skip").
"""

from __future__ import annotations

import pytest

from agent.llm_client import chat, create_client, get_model_id
from tests._server_check import server_available

requires_server = pytest.mark.skipif(
    not server_available(),
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
