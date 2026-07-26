"""agent.repl için testler.

llama-server çalışmıyorsa sunucu-bağımlı testler skip edilir.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.llm_client import create_client, get_model_id
from agent.repl import EXIT_COMMANDS, repl, run_turn
from tests._server_check import server_available

requires_server = pytest.mark.skipif(
    not server_available(),
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
def test_run_turn_executes_read_file_tool_and_summarizes(tmp_path) -> None:
    """Gerçek sunucuyla: model 'X dosyasını oku' isteğine tool-call üretip,
    agent'ın gerçek dosya içeriğini okuyup modele geri verdiğini doğrular.

    Not: Küçük/kısıtlı modelin tool-call üretmesi %100 garanti değil (bazen
    doğrudan halüsinasyon yapabiliyor, bkz. DECISIONS.md K11 model
    non-determinism notu). Bu test bu nedenle iki kabul kriterinden birini
    kontrol eder: (a) agent gerçekten `read_file` tool'unu çalıştırdıysa,
    gerçek dosya içeriği tool mesajında bulunmalı VE nihai yanıt bunu
    içermeli; (b) model tool-call üretmediyse (nadir durum), test skip edilir
    - bu, agent kodunun bir hatası değil, modelin davranışsal kararsızlığıdır.
    """
    (tmp_path / "gizli_kelime.txt").write_text("PORTAKAL42")

    client = create_client()
    model_id = get_model_id(client)
    messages = [
        {
            "role": "user",
            "content": "gizli_kelime.txt dosyasını read_file tool'u ile oku ve içeriğini birebir yaz.",
        }
    ]
    reply = run_turn(client, model_id, messages, root=str(tmp_path))

    tool_messages = [m for m in messages if m.get("role") == "tool"]
    if not tool_messages:
        pytest.skip(
            "Model bu çalıştırmada tool-call üretmedi (davranışsal "
            "non-determinism) - agent loop kodu test edilemedi."
        )

    assert "PORTAKAL42" in tool_messages[0]["content"]
    assert "PORTAKAL42" in reply


def test_run_turn_executes_tool_via_native_tool_call(tmp_path) -> None:
    """Mock client ile: native tool_calls alanı dolu geldiğinde agent loop'un
    tool'u çalıştırıp sonucu ikinci bir istekte modele ilettiğini doğrular.
    Sunucu gerektirmez."""
    (tmp_path / "not.txt").write_text("merhaba dunya")

    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "read_file"
    tool_call.function.arguments = '{"path": "not.txt"}'

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]

    final_response = MagicMock()
    final_response.choices = [
        MagicMock(message=MagicMock(content="Dosyada 'merhaba dunya' yazıyor.", tool_calls=None))
    ]

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first_response, final_response]

    messages = [{"role": "user", "content": "not.txt dosyasını oku"}]
    reply = run_turn(fake_client, "fake-model", messages, root=str(tmp_path))

    assert reply == "Dosyada 'merhaba dunya' yazıyor."
    # Tool sonucu gerçekten geçmişe eklenmiş olmalı.
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "merhaba dunya" in tool_messages[0]["content"]
    assert fake_client.chat.completions.create.call_count == 2


def _make_shell_tool_call_response(command: str, call_id: str = "call_shell_1") -> MagicMock:
    tool_call = MagicMock()
    tool_call.id = call_id
    tool_call.function.name = "run_shell"
    tool_call.function.arguments = json.dumps({"command": command})
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
    return response


def _make_final_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content, tool_calls=None))]
    return response


def test_run_turn_prompts_for_approval_before_running_shell(tmp_path) -> None:
    """run_shell çağrısı, autonomous_mode=False iken confirm() fonksiyonunu
    çağırmalı ve onaylanırsa komutu gerçekten çalıştırmalı."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _make_shell_tool_call_response("echo hello"),
        _make_final_response("Komut çalıştırıldı."),
    ]

    confirm_calls = []

    def fake_confirm(name, arguments, reason):
        confirm_calls.append((name, arguments, reason))
        return True

    messages = [{"role": "user", "content": "echo hello çalıştır"}]
    reply = run_turn(
        fake_client, "fake-model", messages, root=str(tmp_path),
        autonomous_mode=False, confirm=fake_confirm,
    )

    assert reply == "Komut çalıştırıldı."
    assert len(confirm_calls) == 1
    assert confirm_calls[0][0] == "run_shell"
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert "hello" in tool_messages[0]["content"]


def test_run_turn_does_not_execute_shell_when_approval_denied(tmp_path) -> None:
    """Kullanıcı onayı reddederse, komut ÇALIŞTIRILMAMALI - sonuç mesajı
    reddedildiğini belirtmeli."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _make_shell_tool_call_response("echo should-not-run"),
        _make_final_response("Anladım, çalıştırmadım."),
    ]

    def deny_confirm(name, arguments, reason):
        return False

    messages = [{"role": "user", "content": "echo should-not-run çalıştır"}]
    reply = run_turn(
        fake_client, "fake-model", messages, root=str(tmp_path),
        autonomous_mode=False, confirm=deny_confirm,
    )

    assert reply == "Anladım, çalıştırmadım."
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "REDDEDİLDİ" in tool_messages[0]["content"]
    assert "should-not-run" not in tool_messages[0]["content"]


def test_run_turn_skips_approval_for_shell_in_autonomous_mode(tmp_path) -> None:
    """autonomous_mode=True iken normal (yıkıcı olmayan) shell komutu
    confirm() çağrılmadan direkt çalışmalı."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _make_shell_tool_call_response("echo autonomous"),
        _make_final_response("Tamamlandı."),
    ]

    def failing_confirm(name, arguments, reason):
        raise AssertionError("Otonom modda confirm() çağrılmamalıydı.")

    messages = [{"role": "user", "content": "echo autonomous çalıştır"}]
    reply = run_turn(
        fake_client, "fake-model", messages, root=str(tmp_path),
        autonomous_mode=True, confirm=failing_confirm,
    )

    assert reply == "Tamamlandı."
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert "autonomous" in tool_messages[0]["content"]


def test_run_turn_still_prompts_for_destructive_command_in_autonomous_mode(tmp_path) -> None:
    """K8 mutlak sınırı: otonom modda bile yıkıcı komut confirm() çağırmalı."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _make_shell_tool_call_response("rm -rf /tmp/foo"),
        _make_final_response("Anladım, çalıştırmadım."),
    ]

    confirm_calls = []

    def tracking_confirm(name, arguments, reason):
        confirm_calls.append(reason)
        return False

    messages = [{"role": "user", "content": "rm -rf /tmp/foo çalıştır"}]
    run_turn(
        fake_client, "fake-model", messages, root=str(tmp_path),
        autonomous_mode=True, confirm=tracking_confirm,
    )

    assert len(confirm_calls) == 1
    assert "yıkıcı" in confirm_calls[0].lower() or "geri alınamaz" in confirm_calls[0].lower()


def test_run_turn_prompts_for_approval_before_editing_file(tmp_path) -> None:
    """edit_file çağrısı da run_shell gibi onay istemeli (K7: yazma işlemi)."""
    (tmp_path / "target.py").write_text("x = 1\n")

    tool_call = MagicMock()
    tool_call.id = "call_edit_1"
    tool_call.function.name = "edit_file"
    tool_call.function.arguments = json.dumps(
        {"path": "target.py", "diff": "<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE"}
    )

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
    final_response = _make_final_response("Dosya güncellendi.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first_response, final_response]

    confirm_calls = []

    def fake_confirm(name, arguments, reason):
        confirm_calls.append(name)
        return True

    messages = [{"role": "user", "content": "target.py'de x=1'i x=2 yap"}]
    reply = run_turn(
        fake_client, "fake-model", messages, root=str(tmp_path),
        autonomous_mode=False, confirm=fake_confirm,
    )

    assert reply == "Dosya güncellendi."
    assert confirm_calls == ["edit_file"]
    assert (tmp_path / "target.py").read_text() == "x = 2\n"


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
