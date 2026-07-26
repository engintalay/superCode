"""Loop/hata tespiti (Loop Detector) - üç katmanlı koruma.

Karar referansları (bkz. DECISIONS.md):
- K4: Katmanlı koruma - üç sinyal birlikte çalışır:
  1. Tekrar sayacı (aynı/benzer tool çağrısı art arda).
  2. Adım/tur limiti (toplam X turda ilerleme yoksa dur).
  3. Belirsizlik tespiti (model "bilmiyorum" der veya tool çağrısı
     parse edilemezse).
- K19: Tekrar tespiti fuzzy/benzerlik tabanlı olmalı - tam eşleşme değil
  (aynı dosyada farklı satırı düzenlemeye çalışmak gibi ufak varyasyonları
  da yakalamalı).
- K9: Tespit sonrası davranış - DUR, durumu özetle (ne denendi, neden
  çuvalladı), 2-3 alternatif öner, kullanıcı onayı/yönü bekle. Otonom
  modda da bu davranış değişmez (mutlak).

Bu modül, `agent/repl.py`'nin agent loop'una entegre edilecek durum takibi
(`LoopDetector` sınıfı) ve tespit sonrası özet üretimini içerir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

# K4/K19: Art arda kaç BENZER tool-call'dan sonra "tekrar" sayılır.
REPEAT_THRESHOLD = 3
# İki tool-call'ın "benzer" sayılması için gereken minimum benzerlik skoru
# (0.0-1.0 arası, SequenceMatcher.ratio() ile hesaplanır).
SIMILARITY_THRESHOLD = 0.85
# K4: Toplam kaç turda (tool-call zinciri dahil) ilerleme olmazsa dur.
MAX_TURNS_WITHOUT_PROGRESS = 8
# K4: Art arda kaç belirsiz/parse edilemeyen yanıttan sonra dur.
AMBIGUITY_THRESHOLD = 3

# Belirsizlik/çuvallama sinyali veren ifadeler (model kendi belirsizliğini
# doğal dilde ifade ettiğinde) - basit anahtar kelime tabanlı heuristik.
_UNCERTAINTY_PHRASES = [
    "bilmiyorum",
    "emin değilim",
    "nasıl yapacağımı bilmiyorum",
    "i don't know",
    "i'm not sure",
    "i am not sure",
    "unclear",
    "clarify",
    "açıklayabilir misiniz",
    "clarification",
]


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict
    succeeded: bool


@dataclass
class LoopDetectionResult:
    triggered: bool
    reason: str | None
    signal: str | None


@dataclass
class LoopDetector:
    """Bir konuşma turu/oturumu boyunca tool-call geçmişini izler ve
    döngü/çuvallama sinyallerini tespit eder.

    Kullanım: her tool-call sonrası `record_tool_call()`, her ayrıştırma
    hatası/belirsizlik sonrası `record_ambiguous_response()` çağrılır.
    `check()` mevcut durumu değerlendirip bir `LoopDetectionResult` döner.
    """

    history: list[ToolCallRecord] = field(default_factory=list)
    ambiguous_count: int = 0
    turns_without_progress: int = 0

    def record_tool_call(self, name: str, arguments: dict, succeeded: bool) -> None:
        self.history.append(ToolCallRecord(name=name, arguments=arguments, succeeded=succeeded))
        if succeeded:
            self.turns_without_progress = 0
        else:
            self.turns_without_progress += 1

    def record_ambiguous_response(self) -> None:
        self.ambiguous_count += 1
        self.turns_without_progress += 1

    def record_progress(self) -> None:
        """Model net bir ilerleme gösteren bir yanıt verdiğinde (tool-call
        olmadan, belirsizlik de göstermeden) çağrılır - sayaçları sıfırlar."""
        self.turns_without_progress = 0

    def _is_similar(self, a: ToolCallRecord, b: ToolCallRecord) -> bool:
        """K19: Fuzzy benzerlik - tool adı aynı olmalı, argümanlar
        birebir aynı olmasa bile (örn. farklı satır numarası) yüksek
        benzerlikte olabilir."""
        if a.name != b.name:
            return False
        ratio = SequenceMatcher(None, str(a.arguments), str(b.arguments)).ratio()
        return ratio >= SIMILARITY_THRESHOLD

    def detect_repeated_tool_calls(self) -> tuple[bool, str | None]:
        """K4/K19: Son N tool-call art arda birbirine benziyor ve
        BAŞARISIZ oluyorsa, tekrar/döngü tespit edilmiş sayılır."""
        if len(self.history) < REPEAT_THRESHOLD:
            return False, None

        recent = self.history[-REPEAT_THRESHOLD:]
        if any(record.succeeded for record in recent):
            return False, None

        first = recent[0]
        if all(self._is_similar(first, record) for record in recent[1:]):
            return True, (
                f"Aynı tool ('{first.name}') art arda {REPEAT_THRESHOLD} kez "
                "benzer argümanlarla çağrıldı ve her seferinde başarısız oldu."
            )
        return False, None

    def detect_ambiguity(self) -> tuple[bool, str | None]:
        """K4: Art arda AMBIGUITY_THRESHOLD kadar belirsiz/parse edilemeyen
        yanıt gelirse tespit edilmiş sayılır."""
        if self.ambiguous_count >= AMBIGUITY_THRESHOLD:
            return True, (
                f"Model art arda {self.ambiguous_count} kez belirsiz veya "
                "ayrıştırılamayan bir yanıt üretti."
            )
        return False, None

    def detect_no_progress(self) -> tuple[bool, str | None]:
        """K4: Toplam MAX_TURNS_WITHOUT_PROGRESS turda ilerleme olmazsa
        tespit edilmiş sayılır."""
        if self.turns_without_progress >= MAX_TURNS_WITHOUT_PROGRESS:
            return True, (
                f"{self.turns_without_progress} tur boyunca somut bir ilerleme "
                "sağlanamadı (başarılı tool-call veya net bir yanıt yok)."
            )
        return False, None

    def check(self) -> LoopDetectionResult:
        """Üç sinyali de kontrol eder, herhangi biri tetiklenirse durur."""
        for detector in (self.detect_repeated_tool_calls, self.detect_ambiguity, self.detect_no_progress):
            triggered, reason = detector()
            if triggered:
                return LoopDetectionResult(triggered=True, reason=reason, signal=detector.__name__)
        return LoopDetectionResult(triggered=False, reason=None, signal=None)


def contains_uncertainty_phrase(text: str) -> bool:
    """Modelin yanıtında belirsizlik ifade eden bir kalıp olup olmadığını
    kontrol eder (K4'ün belirsizlik tespiti sinyali)."""
    if not text:
        return False
    lowered = text.lower()
    return any(phrase in lowered for phrase in _UNCERTAINTY_PHRASES)


def summarize_loop_detection(
    result: LoopDetectionResult,
    attempted_actions: list[str],
) -> str:
    """K9: Tespit sonrası kullanıcıya gösterilecek özet + alternatif öneriler.

    Format: ne denendi, neden çuvalladı, 2-3 alternatif, kullanıcı yönü
    bekleniyor mesajı. Bu davranış otonom modda da değişmez (K9, mutlak).
    """
    lines = [
        "[DÖNGÜ TESPİTİ] İşlem durduruldu - devam etmeden önce yönünüzü bekliyorum.",
        "",
        f"Sebep: {result.reason}",
        "",
    ]

    if attempted_actions:
        lines.append("Denenenler:")
        for action in attempted_actions:
            lines.append(f"  - {action}")
        lines.append("")

    lines.extend(
        [
            "Öneriler:",
            "  1. Görevi daha küçük/spesifik bir adıma bölerek tekrar deneyin.",
            "  2. Farklı bir yaklaşım veya ek bağlam (örn. hangi dosya/fonksiyon) belirtin.",
            "  3. Bu adımı atlayıp manuel olarak siz devam edin.",
            "",
            "Nasıl ilerlemek istersiniz?",
        ]
    )
    return "\n".join(lines)
