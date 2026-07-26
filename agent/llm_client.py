"""llama-server (OpenAI-uyumlu API) ile konuşan basit LLM istemcisi.

Karar referansları (bkz. DECISIONS.md):
- K1: llama.cpp `llama-server`, OpenAI-uyumlu `/v1/chat/completions`, `--jinja`.
- K11: Test modeli Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf.

Bu modül, Task 1 kapsamında sadece temel bağlantı/sohbet fonksiyonelliğini
sağlar. Tool-calling, loop detection vb. sonraki task'larda eklenecek.
"""

from __future__ import annotations

import sys

from openai import APIConnectionError, OpenAI

DEFAULT_BASE_URL = "http://localhost:8080/v1"
# llama-server API key doğrulaması yapmaz; SDK'nın boş key ile şikayet
# etmemesi için placeholder bir değer veriyoruz.
DEFAULT_API_KEY = "not-needed"


def create_client(base_url: str = DEFAULT_BASE_URL, api_key: str = DEFAULT_API_KEY) -> OpenAI:
    """llama-server'a bağlanan bir OpenAI istemcisi oluşturur."""
    return OpenAI(base_url=base_url, api_key=api_key)


def get_model_id(client: OpenAI) -> str:
    """Sunucuda yüklü olan modelin id'sini döner.

    llama-server tek bir modeli aynı anda serve eder; /v1/models genelde
    tek kayıt içerir, ilkini kullanıyoruz.
    """
    models = client.models.list()
    if not models.data:
        raise RuntimeError("llama-server /v1/models boş liste döndü.")
    return models.data[0].id


def chat(message: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Verilen kullanıcı mesajını modele gönderir, yanıt metnini döner."""
    client = create_client(base_url=base_url)
    model_id = get_model_id(client)

    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content or ""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Kullanım: python -m agent.llm_client \"<mesaj>\"", file=sys.stderr)
        return 1

    message = " ".join(argv)
    try:
        reply = chat(message)
    except APIConnectionError:
        print(
            f"Hata: llama-server'a bağlanılamadı ({DEFAULT_BASE_URL}). "
            "Sunucunun çalıştığından emin olun.",
            file=sys.stderr,
        )
        return 1

    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
