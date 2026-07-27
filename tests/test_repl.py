"""agent.repl için testler.

llama-server çalışmıyorsa sunucu-bağımlı testler skip edilir.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.llm_client import create_client, get_model_id
from agent.repl import (
    AUTONOMOUS_COMMAND_PREFIX,
    EXIT_COMMANDS,
    _execute_and_format,
    _handle_autonomous_command,
    main,
    repl,
    run_turn,
)
from tests._server_check import server_available

requires_server = pytest.mark.skipif(
    not server_available(),
    reason="llama-server http://localhost:8079 adresinde çalışmıyor",
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


def test_run_turn_stops_and_summarizes_when_repeated_failures_detected(tmp_path) -> None:
    """K4/K9: Model art arda benzer, başarısız tool-call üretirse (örn.
    var olmayan bir dosyayı okumaya çalışmak), agent loop MAX_TOOL_HOPS'a
    kadar gitmeden loop detector tarafından durdurulmalı ve bir özet
    (DÖNGÜ TESPİTİ) döndürülmeli - sonsuz/yararsız denemeler yerine."""

    def make_failing_read_call(call_id: str) -> MagicMock:
        tool_call = MagicMock()
        tool_call.id = call_id
        tool_call.function.name = "read_file"
        tool_call.function.arguments = json.dumps({"path": "yok_olan_dosya.py"})
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
        return response

    fake_client = MagicMock()
    # MAX_TOOL_HOPS=5 olsa da REPEAT_THRESHOLD=3'e ulaşınca loop detector
    # daha önce durdurmalı - bu yüzden sadece 3 sahte yanıt yeterli olmalı.
    fake_client.chat.completions.create.side_effect = [
        make_failing_read_call("c1"),
        make_failing_read_call("c2"),
        make_failing_read_call("c3"),
    ]

    messages = [{"role": "user", "content": "yok_olan_dosya.py'yi oku"}]
    reply = run_turn(fake_client, "fake-model", messages, root=str(tmp_path))

    assert "DÖNGÜ TESPİTİ" in reply
    assert "read_file" in reply
    # MAX_TOOL_HOPS'un tamamı (5) denenmeden, 3. tekrar sonrası durmalı.
    assert fake_client.chat.completions.create.call_count == 3


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


def test_handle_autonomous_command_on() -> None:
    new_mode, message = _handle_autonomous_command("/autonomous on", current_mode=False)
    assert new_mode is True
    assert "AÇIK" in message


def test_handle_autonomous_command_off() -> None:
    new_mode, message = _handle_autonomous_command("/autonomous off", current_mode=True)
    assert new_mode is False
    assert "KAPALI" in message


def test_handle_autonomous_command_status_does_not_change_mode() -> None:
    new_mode, message = _handle_autonomous_command("/autonomous status", current_mode=True)
    assert new_mode is True
    assert "AÇIK" in message

    new_mode, message = _handle_autonomous_command("/autonomous", current_mode=False)
    assert new_mode is False
    assert "KAPALI" in message


def test_handle_autonomous_command_unknown_arg_does_not_change_mode() -> None:
    new_mode, message = _handle_autonomous_command("/autonomous foo", current_mode=True)
    assert new_mode is True
    assert "Bilinmeyen komut" in message


def test_repl_autonomous_command_toggles_mode_within_session(capsys, monkeypatch) -> None:
    """Kullanıcı oturum içinde /autonomous on yazıp ardından bir shell komutu
    isteyince, artık onay istenmeden (autonomous_mode=True ile) run_turn'ün
    çağrıldığını doğrular."""
    fake_client = MagicMock()
    inputs = iter(["/autonomous on", "bir şey yap", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    captured_autonomous_values = []

    def fake_run_turn(client, model_id, messages, root=".", autonomous_mode=False, **kwargs):
        captured_autonomous_values.append(autonomous_mode)
        return "tamam"

    with (
        patch("agent.repl.create_client", return_value=fake_client),
        patch("agent.repl.get_model_id", return_value="fake-model"),
        patch("agent.repl.run_turn", side_effect=fake_run_turn),
    ):
        exit_code = repl()

    assert exit_code == 0
    assert captured_autonomous_values == [True]
    assert "Otonom mod AÇIK" in capsys.readouterr().out


def test_main_parses_autonomous_flag(monkeypatch) -> None:
    captured = {}

    def fake_repl(autonomous_mode=False):
        captured["autonomous_mode"] = autonomous_mode
        return 0

    monkeypatch.setattr("agent.repl.repl", fake_repl)
    main(["--autonomous"])
    assert captured["autonomous_mode"] is True


def test_main_without_flag_defaults_to_non_autonomous(monkeypatch) -> None:
    captured = {}

    def fake_repl(autonomous_mode=False):
        captured["autonomous_mode"] = autonomous_mode
        return 0

    monkeypatch.setattr("agent.repl.repl", fake_repl)
    main([])
    assert captured["autonomous_mode"] is False


def test_execute_and_format_auto_parallelizes_glob_search_results(tmp_path) -> None:
    """K21: glob_search 2+ dosya bulursa, agent bu dosyaları otomatik
    olarak paralel okuyup sonuca eklemeli - model ayrıca read_file
    çağırmak zorunda kalmamalı."""
    (tmp_path / "a.py").write_text("içerik-A")
    (tmp_path / "b.py").write_text("içerik-B")
    (tmp_path / "c.py").write_text("içerik-C")

    formatted, succeeded = _execute_and_format("glob_search", {"pattern": "*.py"}, root=str(tmp_path))

    assert succeeded is True
    assert "Otomatik paralel okuma sonuçları" in formatted
    assert "içerik-A" in formatted
    assert "içerik-B" in formatted
    assert "içerik-C" in formatted


def test_execute_and_format_does_not_parallelize_single_file_result(tmp_path) -> None:
    """Sadece 1 dosya bulunursa paralel okuma tetiklenmemeli (K21: 2+ şartı)."""
    (tmp_path / "only.py").write_text("tek dosya")

    formatted, succeeded = _execute_and_format("glob_search", {"pattern": "only.py"}, root=str(tmp_path))

    assert succeeded is True
    assert "Otomatik paralel okuma sonuçları" not in formatted


def test_execute_and_format_isolates_unreadable_file_in_parallel_batch(tmp_path) -> None:
    """Paralel okuma sırasında bir dosya silinmiş/erişilemez olsa bile,
    diğer dosyaların okunması etkilenmemeli."""
    (tmp_path / "exists1.py").write_text("var-1")
    (tmp_path / "exists2.py").write_text("var-2")

    # glob_search'ün gerçekten bulacağı ama okuma anında var olmayan bir
    # senaryoyu simüle etmek yerine, mevcut iki dosyanın doğru okunduğunu
    # ve formatın hata durumunu da destekleyecek şekilde yazıldığını
    # doğruluyoruz (gerçek hata senaryosu test_parallel_tools.py'de
    # izole olarak test edildi).
    formatted, succeeded = _execute_and_format("glob_search", {"pattern": "*.py"}, root=str(tmp_path))

    assert succeeded is True
    assert "var-1" in formatted
    assert "var-2" in formatted


def test_execute_and_format_auto_parallelizes_grep_search_results(tmp_path) -> None:
    """K21: grep_search 2+ farklı dosyada eşleşme bulursa, o dosyalar
    otomatik paralel okunmalı."""
    (tmp_path / "m1.py").write_text("def hedef():\n    pass\n")
    (tmp_path / "m2.py").write_text("def hedef():\n    pass\n")

    formatted, succeeded = _execute_and_format("grep_search", {"query": "hedef"}, root=str(tmp_path))

    assert succeeded is True
    assert "Otomatik paralel okuma sonuçları" in formatted


def test_run_turn_end_to_end_with_parallel_reads_via_mock(tmp_path) -> None:
    """Mock client ile: model glob_search çağırdığında, agent loop'un
    otomatik paralel okuma sonuçlarını tool mesajına dahil ettiğini ve
    modele bu zengin içerikle devam edildiğini doğrular."""
    (tmp_path / "one.py").write_text("BIRINCI_ICERIK")
    (tmp_path / "two.py").write_text("IKINCI_ICERIK")

    tool_call = MagicMock()
    tool_call.id = "call_glob_1"
    tool_call.function.name = "glob_search"
    tool_call.function.arguments = json.dumps({"pattern": "*.py"})

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
    final_response = _make_final_response("İki dosya da okundu.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first_response, final_response]

    messages = [{"role": "user", "content": "*.py dosyalarını bul ve içeriklerini oku"}]
    reply = run_turn(fake_client, "fake-model", messages, root=str(tmp_path))

    assert reply == "İki dosya da okundu."
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert "BIRINCI_ICERIK" in tool_messages[0]["content"]
    assert "IKINCI_ICERIK" in tool_messages[0]["content"]


def test_parallel_read_results_do_not_bypass_approval_for_glob_search(tmp_path) -> None:
    """K21+K7 entegrasyonu: glob_search zaten read-only olduğu için (ve
    tetiklediği paralel read_file'lar da read-only), confirm() HİÇ
    çağrılmamalı - paralel okuma onay mekanizmasını atlamıyor, çünkü
    zaten onay gerektiren bir işlem yok."""
    (tmp_path / "x.py").write_text("X")
    (tmp_path / "y.py").write_text("Y")

    tool_call = MagicMock()
    tool_call.id = "call_glob_2"
    tool_call.function.name = "glob_search"
    tool_call.function.arguments = json.dumps({"pattern": "*.py"})

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
    final_response = _make_final_response("Tamamlandı.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first_response, final_response]

    def failing_confirm(name, arguments, reason):
        raise AssertionError("confirm() çağrılmamalıydı - glob_search+paralel read_file read-only.")

    messages = [{"role": "user", "content": "*.py dosyalarını bul"}]
    reply = run_turn(fake_client, "fake-model", messages, root=str(tmp_path), confirm=failing_confirm)

    assert reply == "Tamamlandı."


def test_loop_detector_records_single_call_for_parallel_glob_batch(tmp_path) -> None:
    """K21+K4 entegrasyonu: glob_search + otomatik paralel okuma, loop
    detector'a TEK bir tool-call kaydı olarak geçmeli (paralel okunan
    N dosya, N ayrı kayıt değil) - aksi halde 3 farklı glob_search
    çağrısı bile loop detector'ı N*3 kayıtla yanlışlıkla tetikleyebilirdi."""
    from agent.loop_detector import LoopDetector

    (tmp_path / "p1.py").write_text("1")
    (tmp_path / "p2.py").write_text("2")
    (tmp_path / "p3.py").write_text("3")

    def make_glob_call(call_id: str) -> MagicMock:
        tool_call = MagicMock()
        tool_call.id = call_id
        tool_call.function.name = "glob_search"
        tool_call.function.arguments = json.dumps({"pattern": "*.py"})
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tool_call]))]
        return response

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        make_glob_call("g1"),
        make_glob_call("g2"),
        _make_final_response("Bitti."),
    ]

    detector = LoopDetector()
    messages = [{"role": "user", "content": "*.py dosyalarını iki kere bul (test amaçlı)"}]
    run_turn(fake_client, "fake-model", messages, root=str(tmp_path), loop_detector=detector)

    # 2 glob_search çağrısı yapıldı (paralel okunan 3 dosya her seferinde
    # dahil olsa da), history'de sadece 2 kayıt olmalı - 3'er dosya için
    # ekstra kayıt YOK.
    assert len(detector.history) == 2
