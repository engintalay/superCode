"""Model yanıtının `content` alanına gömülü tool-call JSON'unu ayrıştırma.

Bağlam: Bu ortamda llama-server'ın native `tool_calls` alanı güvenilir
şekilde dolmuyor (bkz. tests/test_tool_calling_discovery.py, DECISIONS.md
K1 uyarısı). Bu davranış, KV cache quantization (`-ctk/-ctv q4_0`)
kaldırıldıktan (sunucu yeniden başlatıldıktan) SONRA da devam ettiği için
kök neden muhtemelen bu llama-server derlemesinin jinja şablonu/tool-call
parser eşleşmesiyle ilgili, sadece quantization ile sınırlı değil.

Model, tool-call JSON'unu `content` içine, gözlenen üç farklı formattan
biriyle gömüyor:

1. Markdown kod bloğu: ```json\n{...}\n```
2. `<tools>` etiketi: <tools>{...}</tools>
3. `<call>` etiketi: <call>{...}</call>

Bu modül, bilinen formatları tanıyıp `{"name": ..., "arguments": {...}}`
şeklinde bir sözlük döndüren bir fallback parser sağlar.
"""

from __future__ import annotations

import json
import re
from typing import Any

_MARKDOWN_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_TOOLS_TAG_BLOCK = re.compile(r"<tools?>\s*(\{.*?\})\s*</tools?>", re.DOTALL)
_CALL_TAG_BLOCK = re.compile(r"<call>\s*(\{.*?\})\s*</call>", re.DOTALL)

_KNOWN_PATTERNS = (_MARKDOWN_JSON_BLOCK, _TOOLS_TAG_BLOCK, _CALL_TAG_BLOCK)


def extract_tool_call_from_content(content: str) -> dict[str, Any] | None:
    """`content` içinde gömülü bir tool-call JSON'u varsa ayrıştırıp döner.

    Dönen sözlük `{"name": str, "arguments": dict}` şeklindedir. Hiçbir
    bilinen formatla eşleşme bulunamazsa veya JSON geçersizse `None` döner.
    """
    if not content:
        return None

    for pattern in _KNOWN_PATTERNS:
        match = pattern.search(content)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
            return parsed

    return None
