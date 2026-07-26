"""Etkileşimli REPL döngüsü + read-only tool-calling agent loop.

Karar referansları (bkz. DECISIONS.md):
- K12: Etkileşimli REPL/chat modu.
- K13: Context/geçmiş yönetimi (mesaj listesi turlar arası korunuyor).
- K1/K11 güncellemeleri: native `tool_calls` alanı öncelikli denenir,
  boşsa `agent.tool_parsing` ile content'ten fallback çıkarım yapılır.
- K7: Read-only tool'lar (read_file, glob_search, grep_search) onay
  gerektirmeden otomatik çalıştırılır (yazma/shell tool'ları Task 4+'ta
  onay mekanizmasıyla gelecek).

Agent loop akışı (her kullanıcı turunda):
1. Kullanıcı mesajı `messages`'a eklenir.
2. Modelden `tools=TOOL_DEFINITIONS` ile yanıt istenir.
3. Yanıtta native `tool_calls` varsa onlar kullanılır; yoksa
   `extract_tool_call_from_content` ile fallback denenir.
4. Tool-call bulunursa: ilgili tool çalıştırılır, sonucu bir "tool" rolü
   mesajı (native durumda) veya kullanıcıya özetlenmiş bir sistem notu
   (fallback durumunda, çünkü fallback'te gerçek bir tool_call_id yok)
   olarak modele geri verilir, model tekrar çağrılır (nihai yanıt için).
5. Tool-call yoksa: `content` doğrudan kullanıcıya gösterilir.
"""

from __future__ import annotations

import json

from openai import APIConnectionError, OpenAI

from agent.llm_client import DEFAULT_BASE_URL, create_client, get_model_id
from agent.tool_parsing import extract_tool_call_from_content
from agent.tools import TOOL_DEFINITIONS, ToolError, execute_tool

EXIT_COMMANDS = {"/exit", "/quit"}
MAX_TOOL_HOPS = 5  # Aynı turda art arda kaç tool-call zincirine izin verilir.


def _execute_and_format(name: str, arguments: dict, root: str = ".") -> str:
    """Tool'u çalıştırır, sonucu modele gösterilecek bir metne çevirir."""
    try:
        result = execute_tool(name, arguments, root=root)
    except ToolError as exc:
        return f"HATA: {exc}"
    except TypeError as exc:
        return f"HATA: geçersiz argümanlar ({exc})"

    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_turn(
    client: OpenAI,
    model_id: str,
    messages: list[dict],
    root: str = ".",
) -> str:
    """Bir kullanıcı turunu, gerekirse tool-call zinciriyle işler.

    `messages` listesi bu fonksiyon tarafından tool-call/tool-response
    mesajlarıyla genişletilir (side-effect). Son asistan yanıtının metni
    döner.
    """
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
            # Tool-call yok: bu, turun nihai yanıtı.
            messages.append({"role": "assistant", "content": message.content or ""})
            return message.content or ""

        # Tool-call var: çalıştır, sonucu geçmişe ekle, döngüye devam et.
        tool_result = _execute_and_format(tool_call["name"], tool_call["arguments"], root=root)

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

    return "Hata: Çok fazla ardışık tool çağrısı yapıldı (olası döngü), durduruldu."


def repl(base_url: str = DEFAULT_BASE_URL, root: str = ".") -> int:
    """Etkileşimli sohbet döngüsünü başlatır.

    Çıkış: `/exit`, `/quit`, veya Ctrl+D (EOFError) / Ctrl+C (KeyboardInterrupt).
    """
    client = create_client(base_url=base_url)
    try:
        model_id = get_model_id(client)
    except APIConnectionError:
        print(f"Hata: llama-server'a bağlanılamadı ({base_url}).")
        return 1

    print(f"Bağlandı: {model_id}")
    print("Çıkmak için /exit, /quit veya Ctrl+D kullanabilirsiniz.\n")

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

        messages.append({"role": "user", "content": user_input})

        try:
            reply = run_turn(client, model_id, messages, root=root)
        except APIConnectionError:
            print(f"Hata: llama-server'a bağlanılamadı ({base_url}).")
            messages.pop()
            continue

        print(reply)


def main() -> int:
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
