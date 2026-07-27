"""Context/geçmiş yönetimi - özetleme (K13).

Karar referansı (bkz. DECISIONS.md):
- K13: Context limiti yaklaşınca geçmiş, ayrı bir LLM çağrısıyla özetlenir.
  Basit kesme (sliding window) veya sabit tur limiti + manuel `/clear`
  elendi - bağlamı otomatik ve öngörülebilir şekilde korumak isteniyor.

Yaklaşım:
1. Mesaj geçmişinin YAKLAŞIK token sayısı tahmin edilir (tam bir tokenizer
   bağımlılığı eklemek yerine basit bir karakter/4 heuristiği kullanılır -
   İngilizce/Türkçe metin için kabaca doğru bir yaklaşım, kesin olması
   gerekmiyor çünkü amaç "limite yaklaşıyoruz" sinyali, kesin sayım değil).
2. Tahmini token sayısı, sunucudan alınan `n_ctx` değerinin belirli bir
   oranını (SUMMARIZE_THRESHOLD_RATIO) geçerse özetleme tetiklenir.
3. Özetleme: en son SYSTEM mesajı (varsa) ve en son KEEP_RECENT_MESSAGES
   mesaj korunur; aradaki eski mesajlar ayrı bir LLM çağrısıyla tek bir
   özet mesajına dönüştürülür ve geçmişe (system mesajından sonra) eklenir.
"""

from __future__ import annotations

from openai import OpenAI

# Token tahmini: kabaca 1 token ~ 4 karakter (İngilizce/Türkçe için makul
# bir yaklaşım - kesin tokenizer sayımı değil, sadece eşik sinyali içindir).
CHARS_PER_TOKEN_ESTIMATE = 4

# Context limitinin (n_ctx) yüzde kaçına ulaşınca özetleme tetiklensin.
SUMMARIZE_THRESHOLD_RATIO = 0.75

# Özetleme sonrası korunacak (özetlenmeyecek) en son mesaj sayısı - bu
# mesajlar ham haliyle kalır, konuşmanın "taze" bağlamını korur.
KEEP_RECENT_MESSAGES = 4

DEFAULT_N_CTX = 8192  # n_ctx alınamazsa kullanılacak muhafazakar varsayılan.


def estimate_tokens(messages: list[dict]) -> int:
    """Mesaj listesinin YAKLAŞIK token sayısını tahmin eder.

    Kesin bir tokenizer kullanmaz (bağımlılık eklememek için); sadece
    eşik kontrolü için "kabaca ne kadar yer kaplıyor" bilgisini verir.
    """
    total_chars = 0
    for message in messages:
        content = message.get("content") or ""
        total_chars += len(str(content))
        # tool_calls gibi ek alanlar da yer kaplar, kabaca dahil edelim.
        if message.get("tool_calls"):
            total_chars += len(str(message["tool_calls"]))
    return total_chars // CHARS_PER_TOKEN_ESTIMATE


def get_context_limit(client: OpenAI, model_id: str, default: int = DEFAULT_N_CTX) -> int:
    """Sunucudan modelin `n_ctx` (context penceresi boyutu) değerini alır.

    llama-server'ın `/v1/models` yanıtındaki `meta.n_ctx` alanını okur.
    Alınamazsa (alan yoksa/hata olursa) `default` döner.
    """
    try:
        models = client.models.list()
        for model in models.data:
            if model.id == model_id:
                meta = getattr(model, "meta", None)
                if meta is not None:
                    n_ctx = getattr(meta, "n_ctx", None) or (meta.get("n_ctx") if isinstance(meta, dict) else None)
                    if n_ctx:
                        return int(n_ctx)
    except Exception:
        pass
    return default


def should_summarize(messages: list[dict], context_limit: int) -> bool:
    """Geçmişin özetlenmesi gerekip gerekmediğine karar verir (K13)."""
    if len(messages) <= KEEP_RECENT_MESSAGES:
        return False
    estimated = estimate_tokens(messages)
    return estimated >= context_limit * SUMMARIZE_THRESHOLD_RATIO


def _split_for_summarization(messages: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Mesajları üç gruba ayırır: system mesajları, özetlenecek eski
    mesajlar, korunacak son mesajlar."""
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= KEEP_RECENT_MESSAGES:
        return system_messages, [], non_system

    to_summarize = non_system[: -KEEP_RECENT_MESSAGES]
    to_keep = non_system[-KEEP_RECENT_MESSAGES:]
    return system_messages, to_summarize, to_keep


def _format_messages_for_summary_prompt(messages: list[dict]) -> str:
    """Özetlenecek mesajları, özetleme isteğine gömülecek düz metne çevirir."""
    lines = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content") or ""
        if message.get("tool_calls"):
            content += f" [tool_calls: {message['tool_calls']}]"
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def summarize_messages(client: OpenAI, model_id: str, messages: list[dict]) -> list[dict]:
    """Gerekirse geçmişi özetler, yeni (kısaltılmış) mesaj listesini döner.

    `messages` mutasyona uğratılmaz - yeni bir liste döner. System
    mesajları ve en son `KEEP_RECENT_MESSAGES` mesaj olduğu gibi korunur;
    aradaki mesajlar tek bir özet mesajına indirilir.
    """
    system_messages, to_summarize, to_keep = _split_for_summarization(messages)

    if not to_summarize:
        return list(messages)

    summary_prompt = (
        "Aşağıda bir kullanıcı-asistan konuşmasının geçmişi var. Bu geçmişi, "
        "sonraki konuşmanın bağlamını kaybetmeden devam edebilmesi için "
        "kısa ve öz bir şekilde özetle. Önemli kararları, yapılan "
        "değişiklikleri, dosya adlarını ve sonuçları koru:\n\n"
        f"{_format_messages_for_summary_prompt(to_summarize)}"
    )

    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": summary_prompt}],
    )
    summary_text = response.choices[0].message.content or "(özet üretilemedi)"

    summary_message = {
        "role": "user",
        "content": f"[Önceki konuşmanın özeti]\n{summary_text}",
    }

    return system_messages + [summary_message] + to_keep


def maybe_summarize(
    client: OpenAI,
    model_id: str,
    messages: list[dict],
    context_limit: int | None = None,
) -> list[dict]:
    """`should_summarize()` True dönerse özetler, aksi halde değiştirmeden döner.

    `context_limit` verilmezse `get_context_limit()` ile sunucudan alınır.
    """
    if context_limit is None:
        context_limit = get_context_limit(client, model_id)

    if should_summarize(messages, context_limit):
        return summarize_messages(client, model_id, messages)
    return list(messages)
