"""Temel etkileşimli REPL döngüsü (tool'suz).

Karar referansları (bkz. DECISIONS.md):
- K12: Etkileşimli REPL/chat modu (Kiro CLI deneyimine yakın).
- K13: Context/geçmiş yönetimi (bu task'ta henüz özetleme yok; sadece
  mesaj listesinin turlar arası korunması - özetleme Task 8'de gelecek).

Bu modül henüz tool-calling içermez (bkz. Task 3+). Sadece kullanıcı ile
model arasında, geçmişi koruyan basit bir sohbet döngüsü sağlar.
"""

from __future__ import annotations

from openai import APIConnectionError, OpenAI

from agent.llm_client import DEFAULT_BASE_URL, create_client, get_model_id

EXIT_COMMANDS = {"/exit", "/quit"}


def run_turn(client: OpenAI, model_id: str, messages: list[dict[str, str]]) -> str:
    """Mevcut mesaj geçmişiyle modele bir istek gönderir, yanıtı döner.

    Yanıt, çağıran tarafından `messages` listesine eklenmelidir (bu fonksiyon
    listeyi salt-okunur kullanır, side-effect yapmaz).
    """
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def repl(base_url: str = DEFAULT_BASE_URL) -> int:
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

    messages: list[dict[str, str]] = []

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
            reply = run_turn(client, model_id, messages)
        except APIConnectionError:
            print(f"Hata: llama-server'a bağlanılamadı ({base_url}).")
            # Başarısız turu geçmişten çıkar, kullanıcı tekrar deneyebilsin.
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": reply})
        print(reply)


def main() -> int:
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
