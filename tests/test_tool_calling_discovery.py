"""llama-server'ın tool-calling davranışını doğrulayan keşif/regresyon testleri.

Bağlam (bkz. DECISIONS.md K1/K11 güncellemeleri ve PROGRESS.md Task 3 notları):
K1, llama.cpp resmi dokümantasyonuna dayanarak `--jinja` ile native
`tool_calls` alanının güvenilir şekilde dolacağını varsayıyordu.

İlk test modeli Qwen2.5-Coder-14B-Instruct ile bu doğrulanamadı: native
`tool_calls` alanı hep boş geliyordu, model `content` içine tool-call
JSON'unu üç farklı formattan biriyle gömüyordu. KV cache quantization
şüpheliydi ama flag'ler kaldırılınca da davranış değişmedi.

Kullanıcı test modelini `gemma4-coding-Q4_K_M.gguf` ile değiştirdi - bu
modelle native `tool_calls` çok daha güvenilir doluyor. Bu testler artık
her iki durumu da (native dolu / content'e gömülü) kabul edip hangisinin
gerçekleştiğini raporluyor; fallback parser (agent/tool_parsing.py) hem
nadir non-determinism durumu hem de ileride model değişirse diye korunuyor.

Bu testler skip edilir (llama-server yoksa) ama çalıştığında sunucunun
gerçek davranışını doğrular.
"""

from __future__ import annotations

import json

import pytest

from agent.llm_client import create_client, get_model_id
from tests._server_check import server_available

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Bir dosyanın içeriğini okur",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Dosya yolu"}},
            "required": ["path"],
        },
    },
}


requires_server = pytest.mark.skipif(
    not server_available(),
    reason="llama-server http://localhost:8079 adresinde çalışmıyor",
)


@requires_server
def test_native_tool_calls_field_is_not_reliable() -> None:
    """Bilinen durum (regresyon kaydı): native `tool_calls` alanı bu ortamda
    dolu gelmiyor (KV cache q4_0 quantization nedeniyle, K1 uyarısı).

    Bu test, davranış İYİLEŞİRSE (yani native tool_calls çalışmaya
    başlarsa) de kırılmaz - sadece iki olası durumu da kabul edip
    hangisinin gerçekleştiğini raporlar. Asıl amaç: `message.content`
    içinde tool-call'a benzer bir JSON'un mutlaka bulunması (model
    tool'u bir şekilde çağırmaya çalışıyor olmalı).
    """
    client = create_client()
    model_id = get_model_id(client)

    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": "README.md dosyasının içeriğini oku"}],
        tools=[READ_FILE_TOOL],
    )
    message = response.choices[0].message

    if message.tool_calls:
        # Native tool-calling çalışıyor - beklenen alanları doğrula.
        call = message.tool_calls[0]
        assert call.function.name == "read_file"
        args = json.loads(call.function.arguments)
        assert "path" in args
    else:
        # Bilinen durum: content içinde JSON gömülü geliyor.
        assert message.content is not None
        assert "read_file" in message.content
        assert "path" in message.content


@requires_server
def test_tool_call_json_embedded_in_content_is_extractable() -> None:
    """content içine gömülü tool-call JSON'unun (markdown blok veya <tools>
    etiketi içinde) regex/parse ile çıkarılabilir olduğunu doğrular.

    Bu, Task 3'te yazılacak fallback parser'ın üzerine kuracağı temel
    varsayımı kanıtlar: JSON, ya ```json ... ``` bloğu içinde ya da
    <tools>...</tools> etiketi içinde, tek bir JSON nesnesi olarak geliyor.
    """
    from agent.tool_parsing import extract_tool_call_from_content

    client = create_client()
    model_id = get_model_id(client)

    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": "README.md dosyasının içeriğini oku"}],
        tools=[READ_FILE_TOOL],
    )
    message = response.choices[0].message

    if message.tool_calls:
        pytest.skip("Bu çalıştırmada native tool_calls doldu, fallback parser test edilemedi.")

    extracted = extract_tool_call_from_content(message.content or "")
    assert extracted is not None
    assert extracted["name"] == "read_file"
    assert "path" in extracted["arguments"]
