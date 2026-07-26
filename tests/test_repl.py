"""agent.repl için testler.

llama-server çalışmıyorsa sunucu-bağımlı testler skip edilir.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent.llm_client import DEFAULT_BASE_URL, create_client, get_model_id
from agent.repl import EXIT_COMMANDS, repl, run_turn


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


def test_exit_commands_contains_expected_aliases() -> None:
    assert "/exit" in EXIT_COMMANDS
    assert "/quit" in EXIT_COMMANDS


@requires_server
def test_run_turn_returns_nonempty_reply() -> None:
    client = create_client()
    model_id = get_model_id(client)
    messages = [{"role": "user", "content": "merhaba de"}]
    reply = run_turn(client, model_id, messages)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0


@requires_server
def test_repl_preserves_history_and_exits_on_command(capsys, monkeypatch) -> None:
    """İki tur boyunca geçmişin korunduğunu ve /exit ile temiz çıkışı doğrular."""
    inputs = iter(["merhaba", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    exit_code = repl()

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Bağlandı:" in output
    assert "Görüşürüz." in output


def test_repl_eof_exits_cleanly_with_mocked_client(capsys, monkeypatch) -> None:
    """Sunucu gerektirmeden: model_id alınabildiğini varsayıp, input() EOFError
    fırlattığında repl()'in 0 döndürüp temiz çıkış mesajı bastığını doğrular."""
    fake_client = MagicMock()

    def _raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    with (
        patch("agent.repl.create_client", return_value=fake_client),
        patch("agent.repl.get_model_id", return_value="fake-model"),
    ):
        exit_code = repl()

    assert exit_code == 0
    assert "Görüşürüz." in capsys.readouterr().out


def test_repl_connection_error_returns_nonzero(capsys, monkeypatch) -> None:
    """llama-server'a bağlanılamazsa (get_model_id hata fırlatırsa) repl()
    kullanıcıya net bir hata mesajı basıp 1 döndürmeli."""
    from openai import APIConnectionError

    fake_client = MagicMock()
    fake_request = MagicMock()

    with (
        patch("agent.repl.create_client", return_value=fake_client),
        patch(
            "agent.repl.get_model_id",
            side_effect=APIConnectionError(request=fake_request),
        ),
    ):
        exit_code = repl()

    assert exit_code == 1
    assert "bağlanılamadı" in capsys.readouterr().out
