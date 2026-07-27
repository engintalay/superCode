"""Etkileşimli REPL döngüsü + tool-calling agent loop + onay mekanizması
+ loop/hata tespiti.

Karar referansları (bkz. DECISIONS.md):
- K12: Etkileşimli REPL/chat modu.
- K13: Context/geçmiş yönetimi (mesaj listesi turlar arası korunuyor).
- K1/K11 güncellemeleri: native `tool_calls` alanı öncelikli denenir,
  boşsa `agent.tool_parsing` ile content'ten fallback çıkarım yapılır.
- K7: Read-only tool'lar onay gerektirmez; yazma/shell (`run_shell`) tool'ları
  varsayılan olarak kullanıcı onayı ister (bkz. `agent/approval.py`).
- K8/K14: Otonom mod (`autonomous_mode=True`) açıkken bile yıkıcı komutlar
  ve proje-dışı erişimler onay ister - mutlak sınır, bypass edilemez.
- K4/K19: Loop detector, her tool-call hop'unda tekrar/belirsizlik/ilerleme
  sinyallerini izler (bkz. `agent/loop_detector.py`).
- K9: Döngü tespit edilirse DUR, özetle, alternatif öner, kullanıcı yönü
  bekle - bu davranış otonom modda da değişmez (mutlak).

Agent loop akışı (her kullanıcı turunda):
1. Kullanıcı mesajı `messages`'a eklenir.
2. Modelden `tools=TOOL_DEFINITIONS` ile yanıt istenir.
3. Yanıtta native `tool_calls` varsa onlar kullanılır; yoksa
   `extract_tool_call_from_content` ile fallback denenir.
4. Tool-call bulunursa: `requires_approval()` ile onay gerekip gerekmediği
   kontrolü yapılır; gerekiyorsa `prompt_user_confirmation()` ile kullanıcıya
   sorulur. Reddedilirse tool ÇALIŞTIRILMAZ, model bu bilgiyle devam eder.
   Onaylanır/gerekmezse tool çalıştırılır, sonucu modele geri verilir.
   Her tool-call, `LoopDetector`'a kaydedilir (K4/K19).
5. Tool-call yoksa: model belirsizlik ifade ediyorsa (`contains_uncertainty_phrase`)
   bu da loop detector'a kaydedilir; aksi halde ilerleme kaydedilir.
   `content` doğrudan kullanıcıya gösterilir.
6. Her hop sonunda `LoopDetector.check()` çağrılır; tetiklenirse döngü
   DURUR ve `summarize_loop_detection()` ile özet döner (K9).
"""

from __future__ import annotations

import json

from openai import APIConnectionError, OpenAI

from agent.approval import prompt_user_confirmation, requires_approval
from agent.llm_client import DEFAULT_BASE_URL, create_client, get_model_id
from agent.loop_detector import LoopDetector, contains_uncertainty_phrase, summarize_loop_detection
from agent.tool_parsing import extract_tool_call_from_content
from agent.tools import TOOL_DEFINITIONS, ToolError, execute_tool

EXIT_COMMANDS = {"/exit", "/quit"}
AUTONOMOUS_COMMAND_PREFIX = "/autonomous"
MAX_TOOL_HOPS = 5  # Aynı turda art arda kaç tool-call zincirine izin verilir.


def _execute_and_format(name: str, arguments: dict, root: str = ".") -> tuple[str, bool]:
    """Tool'u çalıştırır, sonucu modele gösterilecek bir metne çevirir.

    Döner: `(sonuç_metni, başarılı_mı)`. Loop detector'ın tekrarlanan
    BAŞARISIZ çağrıları ayırt edebilmesi için başarı durumu da döndürülür.
    """
    try:
        result = execute_tool(name, arguments, root=root)
    except ToolError as exc:
        return f"HATA: {exc}", False
    except TypeError as exc:
        return f"HATA: geçersiz argümanlar ({exc})", False

    if isinstance(result, str):
        return result, True
    return json.dumps(result, ensure_ascii=False, indent=2), True


def _handle_tool_call(
    tool_call: dict,
    root: str,
    autonomous_mode: bool,
    confirm: callable,
) -> tuple[str, bool]:
    """Onay kontrolünden geçirip (gerekirse) tool'u çalıştırır.

    Döner: `(sonuç_metni, başarılı_mı)`. Kullanıcı reddederse başarısız
    sayılır (tool fiilen çalışmadı).
    """
    needs_approval, reason = requires_approval(
        tool_call["name"],
        tool_call["arguments"],
        autonomous_mode=autonomous_mode,
        project_root=root,
    )

    if needs_approval:
        approved = confirm(tool_call["name"], tool_call["arguments"], reason)
        if not approved:
            return (
                f"REDDEDİLDİ: Kullanıcı '{tool_call['name']}' çağrısını onaylamadı. "
                "Bu işlem çalıştırılmadı.",
                False,
            )

    return _execute_and_format(tool_call["name"], tool_call["arguments"], root=root)


def run_turn(
    client: OpenAI,
    model_id: str,
    messages: list[dict],
    root: str = ".",
    autonomous_mode: bool = False,
    confirm: callable = prompt_user_confirmation,
    loop_detector: LoopDetector | None = None,
) -> str:
    """Bir kullanıcı turunu, gerekirse tool-call zinciriyle işler.

    `messages` listesi bu fonksiyon tarafından tool-call/tool-response
    mesajlarıyla genişletilir (side-effect). Son asistan yanıtının metni
    döner.

    `confirm`: test edilebilirlik için enjekte edilebilir onay fonksiyonu
    (varsayılan: gerçek `input()` ile soran `prompt_user_confirmation`).
    `loop_detector`: verilmezse bu tur için yeni bir `LoopDetector`
    oluşturulur (turlar arası kalıcı tespit isteniyorsa çağıran taraf aynı
    instance'ı tekrar geçirebilir).
    """
    detector = loop_detector if loop_detector is not None else LoopDetector()
    attempted_actions: list[str] = []

    for _ in range(MAX_TOOL_HOPS):
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        message = response.choices[0].message

        tool_call = None
        tool_call_id = None
        if message.tool_calls:
            call = message.tool_calls[0]
            tool_call = {
                "name": call.function.name,
                "arguments": json.loads(call.function.arguments or "{}"),
            }
            tool_call_id = call.id
        else:
            fallback = extract_tool_call_from_content(message.content or "")
            if fallback is not None:
                tool_call = fallback

        if tool_call is None:
            # Tool-call yok: K4'ün belirsizlik sinyalini kontrol et.
            content = message.content or ""
            if contains_uncertainty_phrase(content):
                detector.record_ambiguous_response()
            else:
                detector.record_progress()

            check_result = detector.check()
            if check_result.triggered:
                summary = summarize_loop_detection(check_result, attempted_actions)
                messages.append({"role": "assistant", "content": summary})
                return summary

            # Bu, turun nihai yanıtı.
            messages.append({"role": "assistant", "content": content})
            return content

        # Tool-call var: onay kontrolünden geçir, çalıştır, sonucu geçmişe ekle.
        tool_result, succeeded = _handle_tool_call(tool_call, root, autonomous_mode, confirm)
        detector.record_tool_call(tool_call["name"], tool_call["arguments"], succeeded=succeeded)
        attempted_actions.append(f"{tool_call['name']}({tool_call['arguments']}) -> {'OK' if succeeded else 'HATA'}")

        if tool_call_id is not None:
            # Native tool-calling: OpenAI formatına uygun assistant + tool mesajları.
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": json.dumps(tool_call["arguments"], ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": tool_result})
        else:
            # Fallback (content'e gömülü) tool-call: gerçek tool_call_id yok,
            # bu yüzden sonucu bir sistem notu olarak ekleyip modele geri veriyoruz.
            messages.append({"role": "assistant", "content": message.content or ""})
            messages.append(
                {
                    "role": "user",
                    "content": f"[Tool sonucu - {tool_call['name']}]\n{tool_result}",
                }
            )

        # K4/K9: her tool-call hop'u sonrası döngü/çuvallama tespiti kontrolü.
        check_result = detector.check()
        if check_result.triggered:
            summary = summarize_loop_detection(check_result, attempted_actions)
            messages.append({"role": "user", "content": summary})
            return summary

    return "Hata: Çok fazla ardışık tool çağrısı yapıldı (olası döngü), durduruldu."


def _handle_autonomous_command(user_input: str, current_mode: bool) -> tuple[bool, str]:
    """`/autonomous on|off|status` komutunu işler.

    Döner: `(yeni_mod, kullanıcıya_gösterilecek_mesaj)`.
    """
    parts = user_input.split()
    arg = parts[1].lower() if len(parts) > 1 else "status"

    if arg == "on":
        return True, (
            "Otonom mod AÇIK: yazma/shell işlemleri onay istemeden çalışacak "
            "(yıkıcı komutlar ve proje-dışı erişimler hariç - bunlar her zaman onay ister, K8)."
        )
    if arg == "off":
        return False, "Otonom mod KAPALI: yazma/shell işlemleri tekrar onay isteyecek."
    if arg == "status":
        state = "AÇIK" if current_mode else "KAPALI"
        return current_mode, f"Otonom mod şu an: {state}."

    return current_mode, (
        f"Bilinmeyen komut: '{user_input}'. Kullanım: {AUTONOMOUS_COMMAND_PREFIX} on|off|status"
    )


def repl(base_url: str = DEFAULT_BASE_URL, root: str = ".", autonomous_mode: bool = False) -> int:
    """Etkileşimli sohbet döngüsünü başlatır.

    Çıkış: `/exit`, `/quit`, veya Ctrl+D (EOFError) / Ctrl+C (KeyboardInterrupt).
    `autonomous_mode`: başlangıç durumu. Oturum içinde `/autonomous on|off|status`
    komutuyla değiştirilebilir. AÇIKKEN de yazma/shell tool'ları için K8'in
    mutlak sınırları (yıkıcı komut / proje-dışı erişim) geçerliliğini korur.
    """
    client = create_client(base_url=base_url)
    try:
        model_id = get_model_id(client)
    except APIConnectionError:
        print(f"Hata: llama-server'a bağlanılamadı ({base_url}).")
        return 1

    print(f"Bağlandı: {model_id}")
    if autonomous_mode:
        print("Otonom mod AÇIK: yazma/shell işlemleri onay istemeden çalışacak")
        print("(yıkıcı komutlar ve proje-dışı erişimler hariç - bunlar her zaman onay ister).")
    print("Çıkmak için /exit, /quit veya Ctrl+D kullanabilirsiniz.")
    print(f"Otonom modu değiştirmek için: {AUTONOMOUS_COMMAND_PREFIX} on|off|status\n")

    messages: list[dict] = []

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print("\nGörüşürüz.")
            return 0
        except KeyboardInterrupt:
            print("\nGörüşürüz.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in EXIT_COMMANDS:
            print("Görüşürüz.")
            return 0
        if user_input.lower().startswith(AUTONOMOUS_COMMAND_PREFIX):
            autonomous_mode, message = _handle_autonomous_command(user_input, autonomous_mode)
            print(message)
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            reply = run_turn(client, model_id, messages, root=root, autonomous_mode=autonomous_mode)
        except APIConnectionError:
            print(f"Hata: llama-server'a bağlanılamadı ({base_url}).")
            messages.pop()
            continue

        print(reply)


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    autonomous_mode = "--autonomous" in argv
    return repl(autonomous_mode=autonomous_mode)


if __name__ == "__main__":
    raise SystemExit(main())

